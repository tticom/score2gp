"""TABRHY-01: read the rhythm a staffless TAB prints under its strings (reading strategy 2).

A TAB printed with no notation staff above it still carries rhythm marks under the strings: a stem per
note or chord, beams (one per eighth, two per sixteenth), augmentation dots, tuplet brackets with their
number, a circle around a stemless chord (a whole note) and a rest glyph. This module reads those marks
into the same ``note-duration-records`` shape the notation reader produces, so the one PDF-only route
(``pdf_tab_bar_assembler``) writes or refuses each bar by its single rule: the bar's durations must add
up to the printed meter's capacity.

What is never done here: a duration is never counted from the number of columns, never taken from
horizontal spacing, never defaulted. A column with no printed rhythm mark, a mark that cannot be
attached to exactly one column, a tuplet whose events disagree with its number, a mark class this
reader does not read, or a bar whose marks do not add up, is an unread record with a located reason.
The only value not printed is an IMPLIED trailing rest: where the printed notes total less than the
meter and nothing else is printed for the remainder it is written as a rest, labelled implied, and is
never allowed to rescue a bar that is over, contradicted or unread.

Technique marks (bend arrows and labels, vibrato, slide lines, hammer-on and pull-off arcs) are not
rhythm. They are read by no function here: a digit-less arc is a tie only when its two ends are the same
string and fret (or it ends at a digit-less stem), and nothing a technique draws can become a note.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from .meter import bar_capacity_ticks
from .notation_omr.note_duration import (
    SCHEMA,
    WRITTEN_VALUES,
    _flag_hooks,
    _frac,
    _governing_signature,
    _signature_basis,
    _tuplet_ratio,
    extract_page_symbols,
)
from .notation_omr.time_signature import VALID_DENOMINATORS, classify_common_cut_contour, classify_numeral, glyph_raster

TAB_RHYTHM_SCHEMA = "tab-rhythm.v0.1"

# Every limit below is a multiple of the TAB staff's own line spacing (one "space"), never points.
COLUMN_SPACES = 0.75  # digits closer than this in x are one column (the assembler's rule)
STEM_COLUMN_SPACES = 0.6  # a stem this close to a column's x belongs to it
STEM_MIN_BELOW_SPACES = 0.5  # a stem reaches at least this far below the bottom string
STEM_MAX_TOP_ABOVE_SPACES = 2.0
STEM_MAX_TOP_BELOW_SPACES = 3.0  # a short stem under a circled digit starts just below the staff
BEAM_MAX_HEIGHT_SPACES = 0.5
BEAM_MIN_WIDTH_SPACES = 0.6
BEAM_COVER_SPACES = 0.2  # a beam covers a stem standing at its end, give or take this
BEAM_END_SPACES = 0.12  # the first beam ends where the stem ends, give or take this
BEAM_PITCH_SPACES = 0.12  # the gaps between a stem's beams agree within this
BEAM_MAX_REACH_SPACES = 2.5
DOT_MIN_SPACES, DOT_MAX_SPACES = 0.12, 0.45
DOT_X_MIN_SPACES, DOT_X_MAX_SPACES = 0.2, 2.2  # a dot stands right of its stem
DOT_Y_REACH_SPACES = 2.4  # and level with the stem's lower end
ZONE_BELOW_SPACES = 7.0  # the rhythm zone under the bottom string
BRACKET_TICK_MAX_SPACES = 0.6
BRACKET_Y_SPACES = 0.15
BRACKET_END_SPACES = 0.35  # a bracket reaches its first and last stem within this
REST_MAX_HEIGHT_SPACES = 0.5
REST_ASPECT = (1.6, 2.6)  # a whole or half rest is a bar about twice as wide as high
REST_LINE_SPACES = 0.15
CIRCLE_MIN_SPACES = 1.0
CIRCLE_PAD_SPACES = 0.2
TIE_END_SPACES = 1.6  # a tie arc ends this close to its digit or stem
TIE_Y_SPACES = 1.2
NUMERAL_ROW_TOLERANCE_SPACES = 0.35
NUMERAL_MIN_HEIGHT_SPACES = 1.2
NUMERAL_MAX_HEIGHT_SPACES = 2.5
NUMERAL_MAX_WIDTH_SPACES = 2.4
SIGNATURE_REACH_SPACES = 6.0
# TSIG-01: a common-time (C) or cut-time (C with a stroke) contour in the meter's place. The C is as wide as it is
# tall less its stroke's overhang, so a cut glyph may stand taller than a numeral (it stood 3.5 spaces on the source).
COMMON_CUT_MIN_HEIGHT_SPACES, COMMON_CUT_MAX_HEIGHT_SPACES = 2.0, 4.5
COMMON_CUT_MIN_WIDTH_SPACES = 1.4
COMMON_CUT_CENTRE_SPACES = 0.5  # centred on the staff's middle, give or take this
ENABLE_COMMON_CUT_GLYPH = True  # TSIG-01: False restores numerals-only reading
COMMON_CUT_VALUES = {"common": (4, 4), "cut": (2, 2)}  # the printed symbol's own meter: C is 4/4, cut C is 2/2

FLAG_BOX_MATCH_PT = 0.05  # a flag box and its drawn glyph share one drawing rectangle
DURATION_BY_BEAMS = ["quarter", "eighth", "16th", "32nd", "64th"]


@dataclass
class _Stem:
    x: float
    y0: float
    y1: float
    ident: str
    bar: int | None = None
    beams: int = 0
    dots: int = 0
    column: int | None = None
    flag: bool = False
    flag_boxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    beam_ok: bool = True


@dataclass
class _Beam:
    x0: float
    x1: float
    y0: float
    y1: float
    ident: str


@dataclass
class _Arc:
    x0: float
    y0: float
    x1: float
    y1: float
    ident: str


@dataclass
class _Half:
    x0: float
    x1: float
    y: float
    left: bool
    ident: str


@dataclass
class _Staff:
    page: int
    index: int
    first_bar: int
    lines: list[float]
    x0: float
    x1: float
    bars: list[tuple[float, float]]
    stems: list[_Stem] = field(default_factory=list)
    beams: list[_Beam] = field(default_factory=list)
    dots: list[tuple[float, float, str]] = field(default_factory=list)
    circles: list[tuple[float, float, float, float, str]] = field(default_factory=list)
    arcs: list[_Arc] = field(default_factory=list)
    halves: list[_Half] = field(default_factory=list)
    rests: list[tuple[float, float, float, float, str]] = field(default_factory=list)
    other: list[tuple[str, tuple[float, float, float, float]]] = field(default_factory=list)
    tuplet_words: list[tuple[float, float, str]] = field(default_factory=list)
    labels: list[tuple[tuple[float, float, float, float], str]] = field(default_factory=list)
    glyphs: list[Any] = field(default_factory=list)  # the page's drawn glyphs, to count a flag's hooks (REFUSE-09)
    header: tuple[float, float] | None = None

    @property
    def space(self) -> float:
        return (self.lines[-1] - self.lines[0]) / (len(self.lines) - 1)

    @property
    def top(self) -> float:
        return self.lines[0]

    @property
    def bottom(self) -> float:
        return self.lines[-1]


def _round(box: Sequence[float]) -> list[float]:
    return [round(float(v), 3) for v in box]


def _is_black(drawing: dict[str, Any]) -> bool:
    colour = drawing.get("fill") if drawing.get("type") != "s" else drawing.get("color")
    return colour is None or all(v < 0.2 for v in colour)


def _is_boxed_text_label(drawing: dict[str, Any], box: tuple[float, float, float, float],
                         words: Sequence[Any]) -> bool:
    """REFUSE-10: an unfilled rectangle outline that frames printed text (a rehearsal or section label).

    The frame is one stroked rectangle with no fill, and the text it frames is read from the PDF text layer:
    a word spanning no more than the frame's width whose centre lies inside it (a font's line box runs a
    little past the stroke vertically, so its height is not compared). A rest is a filled block and a stem or barline is a thin stroke, so neither
    can be matched; an empty frame, or a frame with no text inside it, is not matched and stays unread.
    """
    items = drawing["items"]
    if drawing.get("type") != "s" or len(items) != 1 or items[0][0] != "re" or drawing.get("fill") is not None:
        return False
    return any(box[0] <= word[0] and word[2] <= box[2] and box[1] <= (word[1] + word[3]) / 2 <= box[3]
               and str(word[4]).strip() for word in words)


def _classify_page(page: Any, staves: list[_Staff], offset_free: bool = True) -> dict[str, int]:
    """Sort the page's drawings into the marks each TAB staff owns; return a count per class (this page)."""
    counts: dict[str, int] = {}

    def count(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    ordered = sorted(staves, key=lambda s: s.top)
    zones: list[tuple[float, float]] = []
    for i, s in enumerate(ordered):
        nxt = ordered[i + 1].top - 2.5 * s.space if i + 1 < len(ordered) else float("inf")
        zones.append((s.top - STEM_MAX_TOP_ABOVE_SPACES * s.space, min(s.bottom + ZONE_BELOW_SPACES * s.space, nxt)))

    def owner(box: tuple[float, float, float, float]) -> _Staff | None:
        cy = (box[1] + box[3]) / 2
        best, best_d = None, None
        for s, (lo, hi) in zip(ordered, zones):
            if not (s.x0 - 2 <= (box[0] + box[2]) / 2 <= s.x1 + 2):
                continue
            if lo <= cy <= hi:
                d = abs(cy - (s.top + s.bottom) / 2)
                if best is None or d < best_d:
                    best, best_d = s, d
        return best

    seen_stems: set[tuple[float, float, float]] = set()
    page_words = page.get_text("words")
    for index, drawing in enumerate(page.get_drawings()):
        rect = drawing["rect"]
        box = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
        items = drawing["items"]
        kind = drawing.get("type")
        ident = f"drawing_{index}"
        if rect.width > 150 and rect.height < 1.0:
            continue  # a string line
        curves = [i for i in items if i[0] == "c"]
        is_circle = kind == "s" and len(items) == 4 and len(curves) == 4
        if curves and not is_circle:
            for item in curves:
                p1, p4 = item[1], item[4]
                for staff in ordered:
                    reach = 3 * staff.space
                    if all(staff.top - reach <= p.y <= staff.bottom + reach and staff.x0 - 2 <= p.x <= staff.x1 + 2 for p in (p1, p4)):
                        staff.arcs.append(_Arc(min(p1.x, p4.x), p1.y if p1.x <= p4.x else p4.y,
                                               max(p1.x, p4.x), p4.y if p1.x <= p4.x else p1.y, ident))
                        break
        s = owner(box)
        if s is None:
            continue
        sp = s.space
        w, h = box[2] - box[0], box[3] - box[1]
        black = _is_black(drawing)
        # --- vertical strokes: stems and barlines
        if len(items) == 1 and ((items[0][0] == "l" and abs(items[0][1].x - items[0][2].x) < 0.05)
                                or (items[0][0] == "re" and w < 0.2 * sp and h > 0.5 * sp)):
            x = (box[0] + box[2]) / 2
            if box[3] < s.bottom + STEM_MIN_BELOW_SPACES * sp:
                continue  # entirely within the string band or above it: a barline or a technique stroke, never a stem
            if box[1] < s.top - STEM_MAX_TOP_ABOVE_SPACES * sp or box[1] > s.bottom + STEM_MAX_TOP_BELOW_SPACES * sp:
                s.other.append(("vertical_stroke_off_staff", box))
                count("vertical_stroke_off_staff")
                continue
            key = (round(x, 1), round(box[1], 1), round(box[3], 1))
            if key in seen_stems:
                continue
            seen_stems.add(key)
            s.stems.append(_Stem(x=x, y0=box[1], y1=box[3], ident=ident))
            count("stem")
            continue
        if box[1] < s.bottom - 0.2 * sp:
            # inside or above the string band: tuplet halves cannot be there, technique marks and the
            # circle around a chord are
            if kind == "s" and len(items) == 4 and all(i[0] == "c" for i in items) and min(w, h) >= CIRCLE_MIN_SPACES * sp:
                s.circles.append((*box, ident))
                count("circle")
            continue
        # --- below the strings
        if kind == "f" and black and h <= BEAM_MAX_HEIGHT_SPACES * sp and w >= BEAM_MIN_WIDTH_SPACES * sp and w >= 2 * h \
                and all(i[0] in ("l", "re") for i in items):
            s.beams.append(_Beam(box[0], box[2], box[1], box[3], ident))
            count("beam")
            continue
        if kind == "f" and black and DOT_MIN_SPACES * sp <= w <= DOT_MAX_SPACES * sp and DOT_MIN_SPACES * sp <= h <= DOT_MAX_SPACES * sp:
            s.dots.append(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, ident))
            count("dot")
            continue
        if kind == "s" and len(items) == 2 and all(i[0] == "l" for i in items):
            horizontals = [i for i in items if abs(i[1].y - i[2].y) < 0.05]
            verticals = [i for i in items if abs(i[1].x - i[2].x) < 0.05]
            if len(horizontals) == 1 and len(verticals) == 1 and h <= BRACKET_TICK_MAX_SPACES * sp:
                tick_x = verticals[0][1].x
                s.halves.append(_Half(box[0], box[2], horizontals[0][1].y, abs(tick_x - box[0]) < abs(tick_x - box[2]), ident))
                count("tuplet_bracket_half")
                continue
        if all(i[0] == "c" for i in items) and 2 <= len(items) <= 4 and w >= 1.2 * sp and w >= 2.5 * h:
            continue  # a slur, tie or hammer-on/pull-off crescent: an arc (read above), not a rhythm mark
        if _is_boxed_text_label(drawing, box, page_words):
            count("boxed_text_label")  # REFUSE-10: a section name in a frame is text, never a rhythm mark
            continue
        s.labels.append((box, ident))
    # tuplet numerals and any rest rectangles inside the string band are read below, per staff
    words = page.get_text("words")
    for s in staves:
        lo, hi = s.bottom, s.bottom + ZONE_BELOW_SPACES * s.space
        for word in words:
            if word[4].isdigit() and lo <= (word[1] + word[3]) / 2 <= hi and s.x0 <= word[0] <= s.x1:
                s.tuplet_words.append((float(word[0]), float(word[2]), str(word[4])))
    return counts


def _string_line_start(page: Any, line_y: float, fallback: float) -> float:
    """The leftmost x of the drawn string line at ``line_y`` (lines are broken round chords and digits)."""
    best = fallback
    for drawing in page.get_drawings():
        if drawing["rect"].width < 100:
            continue
        for item in drawing["items"]:
            if item[0] == "l" and abs(item[1].y - line_y) < 0.2 and abs(item[2].y - line_y) < 0.2:
                best = min(best, item[1].x, item[2].x)
    return best


def _find_rests(page: Any, staves: list[_Staff]) -> None:
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        box = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
        w, h = box[2] - box[0], box[3] - box[1]
        if drawing.get("type") != "f" or h <= 0 or not _is_black(drawing):
            continue
        for s in staves:
            sp = s.space
            if s.top <= (box[1] + box[3]) / 2 <= s.bottom and s.x0 <= box[0] and box[2] <= s.x1 \
                    and h <= REST_MAX_HEIGHT_SPACES * sp and REST_ASPECT[0] <= w / h <= REST_ASPECT[1] \
                    and w >= 0.4 * sp and not any(abs(box[0] - bx) < 1.5 for bar in s.bars for bx in bar):
                s.rests.append((*box, f"rest_{rect.x0:.1f}_{rect.y0:.1f}"))


def _numerals(page_symbols: Any, staff: _Staff, x_lo: float, x_hi: float) -> tuple[list[tuple[Any, str]], list[tuple[Any, str]], list[Any]]:
    sp = staff.space
    mid = (staff.top + staff.bottom) / 2
    tol = NUMERAL_ROW_TOLERANCE_SPACES * sp
    rows: dict[str, list[tuple[Any, str]]] = {"top": [], "bottom": []}
    bad: list[Any] = []
    for g in sorted(page_symbols.glyphs, key=lambda g: g.bbox[0]):
        if not (x_lo <= g.bbox[0] < x_hi) or not g.filled:
            continue
        sized = NUMERAL_MIN_HEIGHT_SPACES * sp <= g.h <= NUMERAL_MAX_HEIGHT_SPACES * sp and g.w <= NUMERAL_MAX_WIDTH_SPACES * sp
        if not sized:
            continue
        if g.bbox[1] >= staff.top - tol and g.bbox[3] <= mid + tol:
            row = "top"
        elif g.bbox[1] >= mid - tol and g.bbox[3] <= staff.bottom + tol:
            row = "bottom"
        else:
            continue
        digit, _ = classify_numeral(glyph_raster(g), narrow_one_only=True)
        if digit is None:
            bad.append(g)
        else:
            rows[row].append((g, digit))
    return rows["top"], rows["bottom"], bad


def _common_cut_signature(page_symbols: Any, staff: _Staff, x_lo: float, x_hi: float) -> dict[str, Any] | None:
    """A common-time or cut-time glyph standing where a meter is printed, read by its contour alone (TSIG-01).

    Cut time is written 2/2 and common time 4/4 as printed; the bar totals are never consulted. A C-sized
    contour that is neither (a closed form, a stroke that does not pass the C) is unread with a located reason.
    """
    if not ENABLE_COMMON_CUT_GLYPH:
        return None
    sp = staff.space
    mid = (staff.top + staff.bottom) / 2
    for g in sorted(page_symbols.glyphs, key=lambda g: g.bbox[0]):
        if not (x_lo <= g.bbox[0] < x_hi) or not g.filled or not g.curved:
            continue
        if not (COMMON_CUT_MIN_HEIGHT_SPACES * sp <= g.h <= COMMON_CUT_MAX_HEIGHT_SPACES * sp
                and g.w >= COMMON_CUT_MIN_WIDTH_SPACES * sp and abs(g.cy - mid) <= COMMON_CUT_CENTRE_SPACES * sp):
            continue
        kind, why = classify_common_cut_contour(g, sp)
        if kind is None:
            return {"value": None, "reason": why or "common_cut_time_unread", "sources": [g.ident]}
        return {"value": COMMON_CUT_VALUES[kind], "sources": [g.ident], "shape": f"{kind}_time"}
    return None


def _read_signatures(page_symbols: Any, staff: _Staff, first_x: dict[int, float]) -> dict[int, dict[str, Any]]:
    """Printed time signatures at a bar's start: {bar_in_staff: {'value': (n, d), 'sources': [...]}}."""
    out: dict[int, dict[str, Any]] = {}
    sp = staff.space
    for b, (a, _) in enumerate(staff.bars):
        lo = staff.x0 if b == 0 else a
        hi = min(first_x.get(b, lo + SIGNATURE_REACH_SPACES * sp), lo + SIGNATURE_REACH_SPACES * sp)
        top, bottom, bad = _numerals(page_symbols, staff, lo, hi)
        if not top and not bottom and not bad:
            symbol = _common_cut_signature(page_symbols, staff, lo, hi)
            if symbol is not None:
                out[b] = symbol
            continue
        if not top and not bottom:
            continue
        if not top or not bottom or bad:
            out[b] = {"value": None, "reason": "time_signature_numeral_unread" if bad else "time_signature_half_staff",
                      "sources": [g.ident for g, _ in top + bottom] + [g.ident for g in bad]}
            continue
        n = int("".join(d for _, d in sorted(top, key=lambda t: t[0].bbox[0])))
        d = int("".join(d for _, d in sorted(bottom, key=lambda t: t[0].bbox[0])))
        if d not in VALID_DENOMINATORS or not 1 <= n <= 32:
            out[b] = {"value": None, "reason": "time_signature_value_invalid", "sources": [g.ident for g, _ in top + bottom]}
            continue
        out[b] = {"value": (n, d), "sources": [g.ident for g, _ in top + bottom], "shape": "numerals"}
    return out


def _same_positions(left: list[tuple[int, int]], right: list[tuple[int, int]]) -> bool:
    """A tie joins one pitch to itself: the two columns hold the same strings and frets. An arc between different
    frets is a hammer-on or pull-off (or a slide's curve), which is technique and not rhythm."""
    return bool(left) and left == right


def _columns(digits: Sequence[Any], space: float) -> list[list[Any]]:
    columns: list[list[Any]] = []
    for digit in sorted(digits, key=lambda c: c.x):
        if columns and digit.x - columns[-1][-1].x <= COLUMN_SPACES * space:
            columns[-1].append(digit)
        else:
            columns.append([digit])
    return columns


def _rests_for_remainder(remainder: Fraction) -> list[tuple[str, int, Fraction]] | None:
    """Greedy rests (value name, dots, quarters) filling ``remainder``; None when not representable in 3 or fewer."""
    out: list[tuple[str, int, Fraction]] = []
    left = remainder
    options = []
    for name, value in sorted(WRITTEN_VALUES.items(), key=lambda kv: -kv[1]):
        for dots in (1, 0):
            options.append((name, dots, value * (2 - Fraction(1, 2 ** dots))))
    while left > 0:
        pick = next((o for o in options if o[2] <= left), None)
        if pick is None or len(out) >= 3:
            return None
        out.append(pick)
        left -= pick[2]
    return out


class _Reader:
    def __init__(self, digits_by_page: dict[int, list[Any]], page_heights: list[float]) -> None:
        self.digits_by_page = digits_by_page
        self.page_heights = page_heights
        self.records: list[dict[str, Any]] = []
        self.systems: list[dict[str, Any]] = []
        self.counts: dict[str, int] = {}
        self.bar_reports: list[dict[str, Any]] = []

    def bump(self, name: str, n: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + n

    # ------------------------------------------------------------------------------------
    def read_staff(self, staff: _Staff, system_index: int, system_number: int, bar_offset: int, digits: list[Any]) -> int:
        sp = staff.space
        by_bar: list[list[Any]] = [[] for _ in staff.bars]
        for digit in digits:
            for b, (a, z) in enumerate(staff.bars):
                if a <= digit.x <= z:
                    by_bar[b].append(digit)
                    break
        for stem in staff.stems:
            for b, (a, z) in enumerate(staff.bars):
                if a < stem.x < z:
                    stem.bar = b
        self.bump("arc_candidates", len(staff.arcs))
        self.bump("rest_glyph_candidates", len(staff.rests))
        # curved glyphs under the strings: a flag (touching a stem's lower end), a fingering label (standing clear
        # beneath a stem), or a mark this reader does not read
        for box, _ident in staff.labels:
            cx, w, h = (box[0] + box[2]) / 2, box[2] - box[0], box[3] - box[1]
            flagged = next((st for st in staff.stems if st.x - 0.3 * sp <= box[0] <= st.x + 0.5 * sp
                            and box[1] <= st.y1 + 0.3 * sp and box[3] >= st.y1 - 2.2 * sp and h > 0.45 * sp), None)
            labelled = any(abs(cx - st.x) <= 1.0 * sp and box[1] >= st.y1 + 0.3 * sp for st in staff.stems)
            if flagged is not None and not labelled:
                flagged.flag = True
                flagged.flag_boxes.append(box)
                self.bump("flag_glyph")
            elif labelled and h <= 1.2 * sp and w <= 1.0 * sp:
                self.bump("fingering_label_glyph")
            elif box[3] > staff.bottom - 0.2 * sp and (box[2] <= staff.x0 + 1.3 * sp or box[0] >= staff.x1 - 1.3 * sp):
                self.bump("system_end_bracket_glyph")  # the curl of a system's repeat bracket: not rhythm (repeats are unread)
            else:
                staff.other.append(("unclassified_mark_below_strings", box))
                self.bump("unclassified_mark_below_strings")
        # beams, dots per stem
        for stem in staff.stems:
            covering = [bm for bm in staff.beams
                        if bm.x0 - BEAM_COVER_SPACES * sp <= stem.x <= bm.x1 + BEAM_COVER_SPACES * sp
                        and stem.y1 - BEAM_MAX_REACH_SPACES * sp <= bm.y1 <= stem.y1 + BEAM_END_SPACES * sp]
            covering.sort(key=lambda bm: -bm.y1)
            stem.beams = len(covering)
            stem.beam_ok = True
            if covering:
                if abs(covering[0].y1 - stem.y1) > BEAM_END_SPACES * sp:
                    stem.beam_ok = False
                gaps = [covering[i].y1 - covering[i + 1].y1 for i in range(len(covering) - 1)]
                if gaps and max(gaps) - min(gaps) > BEAM_PITCH_SPACES * sp:
                    stem.beam_ok = False
            near_dots = [d for d in staff.dots
                         if DOT_X_MIN_SPACES * sp <= d[0] - stem.x <= DOT_X_MAX_SPACES * sp
                         and stem.y1 - DOT_Y_REACH_SPACES * sp <= d[1] <= stem.y1 + 0.5 * sp]
            stem.dots = len(near_dots)
        bar_total = 0
        for b, (a, z) in enumerate(staff.bars):
            self.read_bar(staff, b, system_index, system_number, bar_offset + b, by_bar[b])
            bar_total += 1
        return bar_total

    # ------------------------------------------------------------------------------------
    def read_bar(self, staff: _Staff, b: int, system_index: int, system_number: int, bar_index: int, digits: list[Any]) -> None:
        sp = staff.space
        a, z = staff.bars[b]
        page = staff.page
        columns = _columns(digits, sp)
        col_x = [sum(c.x for c in col) / len(col) for col in columns]
        stems = [s for s in staff.stems if s.bar == b]
        circles = [c for c in staff.circles if a <= (c[0] + c[2]) / 2 <= z]
        rests = [r for r in staff.rests if a <= (r[0] + r[2]) / 2 <= z]
        halves = [hf for hf in staff.halves if a - sp <= (hf.x0 + hf.x1) / 2 <= z + sp]
        events: list[dict[str, Any]] = []
        problems: list[dict[str, Any]] = []

        def problem(reason: str, box: Sequence[float], extra: dict[str, Any] | None = None) -> None:
            problems.append({"reason": reason, "bbox": _round(box), **(extra or {})})

        # marks this reader does not read, located in this bar
        for kind, box in staff.other:
            if a - 0.2 * sp <= (box[0] + box[2]) / 2 <= z + 0.2 * sp:
                problem(kind, box)
        # attach stems to columns
        stem_of: dict[int, list[_Stem]] = {i: [] for i in range(len(columns))}
        loose: list[_Stem] = []
        for stem in stems:
            near = [i for i, x in enumerate(col_x) if abs(x - stem.x) <= STEM_COLUMN_SPACES * sp]
            if len(near) == 1:
                stem_of[near[0]].append(stem)
            elif len(near) > 1:
                problem("stem_between_two_columns", (stem.x, stem.y0, stem.x, stem.y1))
            else:
                loose.append(stem)
        for i, ss in stem_of.items():
            if len(ss) > 1:
                problem("two_stems_on_one_column", (col_x[i], columns[i][0].y, col_x[i], columns[i][-1].y))
        # circles to columns
        circle_of: dict[int, tuple[float, float, float, float, str]] = {}
        for c in circles:
            cx = (c[0] + c[2]) / 2
            hit = [i for i, col in enumerate(columns) if abs(col_x[i] - cx) <= STEM_COLUMN_SPACES * sp]
            if len(hit) != 1:
                problem("circle_without_one_column", c[:4])
                continue
            i = hit[0]
            pad = CIRCLE_PAD_SPACES * sp
            inside = all(c[0] - pad <= d.bbox.x0 and d.bbox.x1 <= c[2] + pad and c[1] - pad <= d.y and d.y <= c[3] + pad for d in columns[i])
            if not inside or i in circle_of:
                problem("circle_does_not_enclose_column", c[:4])
                continue
            circle_of[i] = c
        # tuplet groups
        groups: list[dict[str, Any]] = []
        lefts = sorted([h for h in halves if h.left], key=lambda h: h.x0)
        rights = sorted([h for h in halves if not h.left], key=lambda h: h.x0)
        used_rights: set[int] = set()
        for lh in lefts:
            match = next(((j, rh) for j, rh in enumerate(rights) if j not in used_rights and rh.x0 > lh.x1 - 0.1
                          and abs(rh.y - lh.y) <= BRACKET_Y_SPACES * sp), None)
            if match is None:
                problem("tuplet_bracket_half_unpaired", (lh.x0, lh.y, lh.x1, lh.y))
                continue
            used_rights.add(match[0])
            rh = match[1]
            words = [w for w in staff.tuplet_words if lh.x1 - 0.5 <= w[0] and w[1] <= rh.x0 + 0.5]
            if len(words) != 1:
                problem("tuplet_bracket_number_unread", (lh.x0, lh.y, rh.x1, lh.y))
                continue
            ratio = _tuplet_ratio(words[0][2])
            if ratio is None:
                problem("tuplet_ratio_unsupported", (lh.x0, lh.y, rh.x1, lh.y), {"number": words[0][2]})
                continue
            groups.append({"x0": lh.x0, "x1": rh.x1, "actual": ratio[0], "normal": ratio[1], "box": (lh.x0, lh.y, rh.x1, lh.y)})
        for j, rh in enumerate(rights):
            if j not in used_rights:
                problem("tuplet_bracket_half_unpaired", (rh.x0, rh.y, rh.x1, rh.y))
        # whole-bar rest glyphs
        rest_events: list[dict[str, Any]] = []
        for r in rests:
            line = min(staff.lines, key=lambda y: min(abs(y - r[1]), abs(y - r[3])))
            top_touch = abs(r[1] - line) <= REST_LINE_SPACES * sp
            bottom_touch = abs(r[3] - line) <= REST_LINE_SPACES * sp
            if top_touch and not bottom_touch:  # hangs from a line: a whole rest
                rest_events.append({"x": (r[0] + r[2]) / 2, "kind": "rest", "written": "whole", "box": r[:4], "source": r[4]})
            else:
                problem("rest_glyph_not_a_whole_rest", r[:4])
        # events from columns
        for i, col in enumerate(columns):
            x = col_x[i]
            ys = [d.y for d in col]
            box = (min(d.bbox.x0 for d in col), min(ys) - 0.5 * sp, max(d.bbox.x1 for d in col), max(ys) + 0.5 * sp)
            ss = stem_of[i]
            ev: dict[str, Any] = {"x": x, "kind": "chord" if len(col) > 1 else "note", "digits": col, "box": box,
                                  "stem": ss[0] if len(ss) == 1 else None, "circle": circle_of.get(i), "reason": None}
            if len(ss) > 1:
                ev["reason"] = "two_stems_on_one_column"
            elif ev["circle"] is not None:
                st = ev["stem"]
                if st is not None and st.beams:
                    ev["reason"] = "circle_with_beam"
                else:
                    ev["written"] = "half" if st is not None else "whole"
                    ev["dots"] = st.dots if st is not None else 0
            elif ev["stem"] is None:
                ev["reason"] = "tab_column_without_rhythm_mark"
            else:
                st = ev["stem"]
                if not st.beam_ok:
                    ev["reason"] = "beam_levels_inconsistent"
                elif st.beams >= len(DURATION_BY_BEAMS):
                    ev["reason"] = "more_than_four_beams"
                elif self._flag_near(staff, st):
                    hooks = self._flag_hooks_of(staff, st)
                    if hooks is None:
                        ev["reason"] = "flag_glyph_unread"
                    else:
                        ev["written"] = DURATION_BY_BEAMS[hooks]
                        ev["dots"] = st.dots
                else:
                    ev["written"] = DURATION_BY_BEAMS[st.beams]
                    ev["dots"] = st.dots
            events.append(ev)
        # digit-less stems: a tie end if an arc ends there
        for st in loose:
            ev = {"x": st.x, "kind": "note", "digits": [], "box": (st.x - 0.3 * sp, st.y0, st.x + 0.3 * sp, st.y1), "stem": st,
                  "circle": None, "reason": None, "digitless": True}
            if not st.beam_ok:
                ev["reason"] = "beam_levels_inconsistent"
            elif st.beams >= len(DURATION_BY_BEAMS):
                ev["reason"] = "more_than_four_beams"
            elif self._flag_near(staff, st):
                hooks = self._flag_hooks_of(staff, st)
                if hooks is None:
                    ev["reason"] = "flag_glyph_unread"
                else:
                    ev["written"] = DURATION_BY_BEAMS[hooks]
                    ev["dots"] = st.dots
            else:
                ev["written"] = DURATION_BY_BEAMS[st.beams]
                ev["dots"] = st.dots
            events.append(ev)
        for r in rest_events:
            if any(abs(ev["x"] - r["x"]) <= STEM_COLUMN_SPACES * sp for ev in events):
                problem("rest_glyph_over_tab_digit", r["box"])
                continue
            events.append({"x": r["x"], "kind": "rest", "digits": [], "box": r["box"], "stem": None, "circle": None,
                           "reason": None, "written": "whole", "dots": 0, "rest_source": r["source"]})
        events.sort(key=lambda e: e["x"])
        # ties: arcs whose two ends are the same positions, or whose end is a digit-less stem
        tie_next: set[int] = set()
        tie_prev: set[int] = set()
        for arc in staff.arcs:
            if not (a - 0.2 * sp <= arc.x0 and arc.x1 <= z + 0.2 * sp):
                continue
            left = self._event_at(events, staff, arc.x0, arc.y0, side="left")
            right = self._event_at(events, staff, arc.x1, arc.y1, side="right")
            if left is None or right is None or left is right:
                continue
            li, ri = events.index(left), events.index(right)
            if ri != li + 1:
                continue
            if right.get("digitless"):
                tie_next.add(li)
                tie_prev.add(ri)
                continue
            if any(d.kind == "percussive-strike" for d in (*left["digits"], *right["digits"])):
                continue  # a strike carries no pitch to hold: an arc beside one is not a tie
            lp = sorted((d.string, d.parsed_fret) for d in left["digits"])
            rp = sorted((d.string, d.parsed_fret) for d in right["digits"])
            if _same_positions(lp, rp):
                tie_next.add(li)
                tie_prev.add(ri)
        # tuplets
        for g in groups:
            members = [e for e in events if g["x0"] - BRACKET_END_SPACES * sp <= e["x"] <= g["x1"] + BRACKET_END_SPACES * sp]
            if len(members) != g["actual"]:
                problem("tuplet_event_count_mismatch", g["box"], {"events": len(members), "number": g["actual"]})
                for e in members:
                    e["reason"] = e["reason"] or "tuplet_event_count_mismatch"
                continue
            for e in members:
                e["tuplet"] = {"actual": g["actual"], "normal": g["normal"]}
        # records
        records: list[dict[str, Any]] = []
        for k, e in enumerate(events):
            records.append(self._record(staff, system_index, system_number, bar_index, b, k, e, k in tie_next, k in tie_prev))
        # problems become unread records at their location (each bar keeps every located reason)
        for p in problems:
            records.append(self._unread_record(staff, system_index, system_number, bar_index, b, len(records), p["reason"], p["bbox"], p))
        # implied trailing rest
        self.records.extend(records)
        self.bar_reports.append({"bar_index": bar_index, "page_index": page, "system_index": system_index,
                                 "events": len(events), "problems": [p["reason"] for p in problems],
                                 "digits": len(digits), "stems": len(stems),
                                 "beams_by_level": {str(n): sum(1 for s in stems if s.beams == n) for n in range(0, 5)},
                                 "dots": sum(s.dots for s in stems), "circles": len(circle_of),
                                 "tuplets": len(groups), "rests": len(rest_events), "ties": len(tie_next)})
        for name, n in (("stem", len(stems)), ("circled_chord", len(circle_of)), ("tuplet_bracket", len(groups)),
                        ("whole_rest_glyph", len(rest_events)), ("tie", len(tie_next)), ("dot", sum(s.dots for s in stems))):
            self.bump(name, n)
        for s in stems:
            self.bump(f"stems_with_{s.beams}_beams")

    @staticmethod
    def _flag_near(staff: _Staff, stem: _Stem) -> bool:
        return stem.flag

    @staticmethod
    def _flag_hooks_of(staff: _Staff, stem: _Stem) -> int | None:
        """REFUSE-09: the hooks of the flag glyphs on a beamless stem, counted from the drawn blades.

        Each flag box is matched to the one drawn glyph that has that box; the glyph's hooks are the blades
        every scan through its outward stretch crosses (the notation reader's rule). A stem with a beam,
        a flag with no matching glyph, or a glyph whose scans disagree is not read (None): the value is
        never taken from spacing or the bar total.
        """
        if stem.beams or not stem.flag_boxes:
            return None
        total = 0
        for box in stem.flag_boxes:
            matches = [g for g in staff.glyphs if all(abs(a - b) <= FLAG_BOX_MATCH_PT for a, b in zip(g.bbox, box))]
            if len(matches) != 1:
                return None
            hooks = _flag_hooks(matches[0], stem, staff.space)
            if hooks == 0:
                return None
            total += hooks
        return total if 1 <= total < len(DURATION_BY_BEAMS) else None

    @staticmethod
    def _event_at(events: list[dict[str, Any]], staff: _Staff, x: float, y: float, side: str) -> dict[str, Any] | None:
        sp = staff.space
        best, best_d = None, None
        for e in events:
            if e["kind"] == "rest":
                continue
            if e.get("digitless"):
                if side != "right":
                    continue
                d = abs(e["x"] - x)
                if d > TIE_END_SPACES * sp:
                    continue
            else:
                x0 = min(dg.bbox.x0 for dg in e["digits"])
                x1 = max(dg.bbox.x1 for dg in e["digits"])
                edge = x1 if side == "left" else x0
                d = abs(edge - x)
                ys = [dg.y for dg in e["digits"]]
                if d > TIE_END_SPACES * sp or not (min(ys) - TIE_Y_SPACES * sp <= y <= max(ys) + TIE_Y_SPACES * sp):
                    continue
            if best is None or d < best_d:
                best, best_d = e, d
        return best

    # ------------------------------------------------------------------------------------
    def _location(self, staff: _Staff, system_index: int, bar_index: int, index: int, box: Sequence[float]) -> dict[str, Any]:
        return {"page_index": staff.page, "system_index": system_index, "bar_index": bar_index, "event_index": index, "bbox": _round(box)}

    def _unread_record(self, staff: _Staff, system_index: int, system_number: int, bar_index: int, b: int, index: int,
                       reason: str, box: Sequence[float], extra: dict[str, Any] | None = None) -> dict[str, Any]:
        location = self._location(staff, system_index, bar_index, index, box)
        return {"page_index": staff.page, "system_index": system_index, "system_number": system_number, "bar_index": bar_index,
                "bar_in_system": b, "event_index": index, "kind": "note", "status": "unread", "reason": reason,
                "location": location, "notehead": None, "stem": None, "flags": {"count": 0, "glyphs": []},
                "beams": {"count": 0, "sources": [], "group": None, "group_size": 0},
                "dots": {"count": 0, "sources": []}, "rest": None, "tuplet": None,
                "tie": {"start": False, "stop": False, "sources": []},
                "written": None, "value_quarters": None, "duration_quarters": None,
                "shape_class": reason, "source_form": "tab_rhythm", "width_spaces": None, "height_spaces": None}

    def _record(self, staff: _Staff, system_index: int, system_number: int, bar_index: int, b: int, index: int,
                e: dict[str, Any], tie_start: bool, tie_stop: bool) -> dict[str, Any]:
        if e["reason"]:
            return self._unread_record(staff, system_index, system_number, bar_index, b, index, e["reason"], e["box"])
        location = self._location(staff, system_index, bar_index, index, e["box"])
        written = e["written"]
        dots = e.get("dots", 0)
        value = WRITTEN_VALUES[written] * (2 - Fraction(1, 2 ** dots))
        tuplet = e.get("tuplet")
        duration = value * Fraction(tuplet["normal"], tuplet["actual"]) if tuplet else value
        st = e["stem"]
        record = self._unread_record(staff, system_index, system_number, bar_index, b, index, "x", e["box"])
        record.update(status="read", reason=None, location=location, shape_class=None, source_form=None)
        record.pop("shape_class"), record.pop("source_form"), record.pop("width_spaces"), record.pop("height_spaces")
        record["kind"] = e["kind"]
        if e["kind"] == "rest":
            record["rest"] = {"glyph": written, "source": e["rest_source"]}
        else:
            record["notehead"] = {"kind": "tab_digits", "count": len(e["digits"]) or 0, "sources": [d.id for d in e["digits"]]}
            if any(d.kind == "percussive-strike" for d in e["digits"]):
                # PERCX-01: the owning head of an X strike is its own TAB column's X. The index runs down the staff,
                # as the notation reader's does, so it grows with the string number.
                record["notehead"]["heads"] = [
                    {"kind": "cross" if d.kind == "percussive-strike" else "filled", "source": d.id,
                     "staff_position_index": d.string}
                    for d in sorted(e["digits"], key=lambda d: d.string)]
            if e.get("digitless"):
                record["notehead"]["count"] = 0  # set to the tied-from note's count below
            if st is not None:
                record["stem"] = {"source": st.ident, "direction": "down"}
                record["beams"] = {"count": st.beams, "sources": [], "group": None, "group_size": 0}
            if e.get("circle") is not None:
                record["circle"] = {"source": e["circle"][4]}
        record["dots"] = {"count": dots, "sources": []}
        record["tuplet"] = tuplet
        record["tie"] = {"start": tie_start, "stop": tie_stop, "sources": []}
        record["written"] = written
        record["value_quarters"] = _frac(value)
        record["duration_quarters"] = _frac(duration)
        record["tab_rhythm"] = {"basis": "printed_marks", "staff_space": round(staff.space, 4)}
        return record


def _fix_tie_heads(records: list[dict[str, Any]]) -> None:
    """A digit-less tie end takes the head count of the note it is tied from (the assembler checks it)."""
    last: dict[int, dict[str, Any]] = {}
    for r in sorted((r for r in records if r["status"] == "read" and r["kind"] != "rest"),
                    key=lambda r: (r["bar_index"], r["event_index"])):
        if r["notehead"]["count"] == 0 and last.get("prev") is not None:
            r["notehead"]["count"] = last["prev"]["notehead"]["count"]
        last["prev"] = r


def _implied_record(last: dict[str, Any], index: int, name: str, dots: int, quarters: Fraction,
                    box: Sequence[float]) -> dict[str, Any]:
    """A rest the printed marks do not show: the remainder of a bar whose printed notes total less than the meter."""
    rest = {k: (dict(v) if isinstance(v, dict) else v) for k, v in last.items()}
    rest.update(event_index=index, kind="rest", notehead=None, stem=None, tuplet=None,
                rest={"glyph": name, "source": "implied", "implied": True},
                dots={"count": dots, "sources": []}, tie={"start": False, "stop": False, "sources": []},
                beams={"count": 0, "sources": [], "group": None, "group_size": 0},
                written=name, value_quarters=_frac(quarters), duration_quarters=_frac(quarters),
                location={**last["location"], "event_index": index, "bbox": _round(box)},
                tab_rhythm={"basis": "implied_rest"})
    rest.pop("circle", None)
    return rest


def _bar_checks(records: list[dict[str, Any]], signatures: dict[int, dict[str, Any] | None],
                implied_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-bar totals; add an IMPLIED trailing rest where the printed notes total less than the meter and nothing
    else is printed (no unread record, no located problem)."""
    checks = []
    for bar, signature in sorted(signatures.items()):
        events = [r for r in records if r["bar_index"] == bar]
        unread = sum(1 for r in events if r["status"] != "read")
        total = sum((Fraction(r["duration_quarters"]) for r in events if r["status"] == "read"), Fraction(0))
        check: dict[str, Any] = {"bar_index": bar, "events": len(events), "unread_events": unread, "total_quarters": _frac(total),
                                 "time_signature": None, "time_signature_source": None, "expected_quarters": None}
        expected = None
        if signature:
            numerator, denominator = signature["value"]
            expected = bar_capacity_ticks(numerator, denominator, 1)
            check.update(time_signature=f"{numerator}/{denominator}", time_signature_source=signature["source"],
                         expected_quarters=_frac(expected))
        if signature and signature.get("conflict"):
            check["status"] = "signature_conflict"
        elif unread:
            check["status"] = "incomplete"
        elif not signature:
            check["status"] = "time_signature_unread"
        else:
            if events and total < expected:
                remainder = expected - total
                rests = _rests_for_remainder(remainder)
                last = max(events, key=lambda r: r["event_index"])
                if rests is not None and last["kind"] != "rest":
                    index = last["event_index"]
                    x0, y0, x1, y1 = last["location"]["bbox"]
                    gap = 1.1 * last["tab_rhythm"]["staff_space"]  # clear of the last column the assembler matches by x
                    x1 = (x0 + x1) / 2 + gap
                    for name, dots, quarters in rests:
                        index += 1
                        records.append(_implied_record(last, index, name, dots, quarters, (x1, y0, x1 + 0.1, y1)))
                    total += remainder
                    implied_log.append({"bar_index": bar, "quarters": _frac(remainder),
                                        "rests": [f"{n}{'.' * d}" for n, d, _ in rests]})
                    check.update(events=len(events) + len(rests), total_quarters=_frac(total), implied_rest_quarters=_frac(remainder))
            check["status"] = "match" if total == expected else "mismatch"
        checks.append(check)
    return checks


def _drop_header(staff: _Staff, digits: list[Any]) -> None:
    """A repeat sign or thick barline after the clef leaves a first interval that is the header, not a bar:
    no digit, stem, circle or rest in it, and narrower than a bar can be."""
    if len(staff.bars) < 2:
        return
    a, z = staff.bars[0]
    sp = staff.space
    if z - a >= 6 * sp:
        return
    inside = any(a <= d.x <= z for d in digits) or any(a <= st.x <= z for st in staff.stems)         or any(a <= (c[0] + c[2]) / 2 <= z for c in staff.circles) or any(a <= (r[0] + r[2]) / 2 <= z for r in staff.rests)
    if not inside:
        staff.header = (a, z)
        staff.bars = staff.bars[1:]


def _staves_of_page(page: Any, symbols: Any, page_index: int, bar_offset: int) -> list[_Staff]:
    """The page's TAB staves (six drawn string lines) with their bar edges: full-height vertical strokes, grouped.

    Staves come from the notation reader's staff finder and, for any the finder misses, from the PDF reader's
    own system detector (which also recovers lines interrupted at every digit). Strokes closer than a staff
    space are one edge (a double or thick barline, or a repeat sign). Each bar lies between one edge's right
    side and the next edge's left side.
    """
    from .notation_omr.note_duration import find_staves  # noqa: PLC0415 - avoid module import cycle
    from .pdf import _detect_tab_systems  # noqa: PLC0415 - avoid module import cycle

    _, tab = find_staves(symbols)
    found = [(list(t.lines), t.x0, t.x1) for t in tab if len(t.lines) == 6]
    for ts in _detect_tab_systems(page, page_index + 1):
        if len(ts.line_ys) == 6 and not any(abs(lines[0] - ts.line_ys[0]) <= 0.5 * (ts.line_ys[1] - ts.line_ys[0]) for lines, _, _ in found):
            found.append((list(ts.line_ys), ts.x0, ts.x1))
    drawings = page.get_drawings()
    staves: list[_Staff] = []
    for lines, x0, x1 in sorted(found, key=lambda f: f[0][0]):
        sp = (lines[-1] - lines[0]) / 5
        top, bottom = lines[0], lines[-1]
        xs: list[float] = []
        for drawing in drawings:
            rect = drawing["rect"]
            if len(drawing["items"]) != 1 or rect.width > 0.6 * sp:
                continue
            if rect.y0 <= top + 0.3 * sp and bottom - 0.3 * sp <= rect.y1 <= bottom + 0.3 * sp and x0 - 2 <= rect.x0 <= x1 + 2:
                xs.append((rect.x0 + rect.x1) / 2)
        edges: list[list[float]] = []
        for x in sorted(xs):
            if edges and x - edges[-1][-1] <= 1.0 * sp:
                edges[-1].append(x)
            else:
                edges.append([x])
        if len(edges) < 2:
            continue
        bars = [(left[-1], right[0]) for left, right in zip(edges, edges[1:])]
        staves.append(_Staff(page=page_index, index=len(staves), first_bar=bar_offset, lines=lines,
                             x0=min(x0, edges[0][0]), x1=max(x1, edges[-1][-1]), bars=bars))
    return staves


def read_tab_rhythm(pdf_path: str | Path, tabraw: Any, pages: tuple[int, int] | None = None,
                    time_signature: tuple[int, int] | None = None) -> dict[str, Any]:
    """Note-duration records for every bar of the PDF's staffless TAB systems, read from printed rhythm marks."""
    import pymupdf  # noqa: PLC0415 - PyMuPDF is only needed when reading a PDF

    path = Path(pdf_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    # PERCX-01: an X strike is a TAB column of its own (it has no notation staff to own it), so it is read with the digits.
    fret_digits = [c for c in tabraw.candidates
                   if ((c.kind == "fret" and c.parsed_fret is not None) or c.kind == "percussive-strike")
                   and c.string is not None and c.x is not None and c.y is not None and c.bbox is not None]
    signatures: dict[int, dict[str, Any] | None] = {}
    basis: dict[int, dict[str, Any] | None] = {}
    time_signatures: list[dict[str, Any]] = []
    declared = {"value": time_signature, "source": "caller_declared", "sources": []} if time_signature else None
    carried: dict[str, Any] | None = None
    unread_signature: dict[str, Any] | None = None
    marks_by_class: dict[str, int] = {}
    with pymupdf.open(path) as doc:
        heights = [round(float(page.rect.height), 3) for page in doc]
        reader = _Reader({}, heights)
        first, last = pages if pages else (1, len(doc))
        bar_offset = 0
        system_number = 0
        all_staves: list[tuple[int, _Staff]] = []
        for page_index in range(first - 1, min(last, len(doc))):
            page = doc[page_index]
            offset = sum(heights[:page_index])
            symbols = extract_page_symbols(page, page_index)
            staves = _staves_of_page(page, symbols, page_index, bar_offset)
            if not staves:
                continue
            for staff in staves:
                staff.glyphs = symbols.glyphs
            class_counts = _classify_page(page, staves)
            for name, n in class_counts.items():
                marks_by_class[name] = marks_by_class.get(name, 0) + n
            _find_rests(page, staves)
            page_digits = [c for c in fret_digits if (c.page_index or 1) - 1 == page_index]
            local = []
            for c in page_digits:
                y = c.y - offset
                local.append(_View(c, y))
            for position, staff in enumerate(staves):
                all_staves.append((page_index, staff))
                my = [d for d in local if staff.top - 3 * staff.space <= d.y <= staff.bottom + 3 * staff.space]
                _drop_header(staff, my)
                bar_sizes = len(staff.bars)
                first_x = {}
                for b, (a, z) in enumerate(staff.bars):
                    xs = [d.bbox.x0 for d in my if a <= d.x <= z]
                    if xs:
                        first_x[b] = min(xs)
                printed = _read_signatures(symbols, staff, first_x)
                for b in range(bar_sizes):
                    reading = printed.get(b)
                    origin = "carried"
                    if reading is not None and reading["value"] is not None:
                        carried = {"value": reading["value"], "source": "vector_glyphs", "sources": reading["sources"], "shape": reading["shape"]}
                        origin = "system_start" if b == 0 else "mid_system"
                        unread_signature = None
                        time_signatures.append({"first_bar_index": bar_offset + b, "page_index": page_index, "status": "read",
                                                "value": list(reading["value"]), "sources": reading["sources"], "reason": None})
                    elif reading is not None:
                        carried, origin = None, None
                        unread_signature = {"reason": reading["reason"], "location": {"page_index": page_index, "bar_index": bar_offset + b}}
                        time_signatures.append({"first_bar_index": bar_offset + b, "page_index": page_index, "status": "unreadable",
                                                "value": None, "sources": reading["sources"], "reason": reading["reason"]})
                    printed_signature, governing_unread = carried, unread_signature
                    if (carried is not None and declared is not None and carried.get("shape") in ("common_time", "cut_time")
                            and tuple(declared["value"]) != tuple(carried["value"])
                            and bar_capacity_ticks(*declared["value"], 1) == bar_capacity_ticks(*carried["value"], 1)):
                        # TSIG-01: a C or cut-C glyph and the caller's explicit meter of equal bar capacity (4/4 for
                        # 2/2): the caller's choice governs and the glyph reading stays on record, so it is no conflict.
                        printed_signature = None
                        governing_unread = {"reason": "meter_glyph_overridden_by_declared_equal_capacity",
                                            "glyph_value": list(carried["value"]), "sources": carried["sources"]}
                    signature = _governing_signature(printed_signature, origin, declared, governing_unread)
                    signatures[bar_offset + b] = signature
                    basis[bar_offset + b] = _signature_basis(signature)
                bars_read = reader.read_staff(staff, system_index=position, system_number=system_number, bar_offset=bar_offset,
                                              digits=my)
                reader.systems.append({"page_index": page_index, "system_index": position, "system_number": system_number,
                                       "first_bar_index": bar_offset, "bar_count": bars_read, "staff_space": round(staff.space, 4),
                                       "staff": {"top": round(staff.top - 0.01, 3), "bottom": round(staff.top - 0.01, 3),
                                                 "x0": round(staff.x0, 3), "x1": round(staff.x1, 3)},
                                       "bars": [[round(a, 3), round(z, 3)] for a, z in staff.bars],
                                       "tab_staff": {"top": round(staff.top, 3), "bottom": round(staff.bottom, 3)}})
                bar_offset += bars_read
                system_number += 1
    unplaced = []
    for c in fret_digits:
        page_index = (c.page_index or 1) - 1
        if not first - 1 <= page_index < min(last, len(heights)):
            continue
        y = c.y - sum(heights[:page_index])
        if not any(pg == page_index and st.top - 3 * st.space <= y <= st.bottom + 3 * st.space
                   and any(a <= c.x <= z for a, z in st.bars) for pg, st in all_staves):
            unplaced.append({"candidate_id": c.id, "page_index": page_index, "bbox": _round([c.bbox.x0, y - (c.y - c.bbox.y0), c.bbox.x1, y + (c.bbox.y1 - c.y)])})
    _fix_tie_heads(reader.records)
    implied: list[dict[str, Any]] = []
    checks = _bar_checks(reader.records, signatures, implied)
    reasons: dict[str, int] = {}
    for r in reader.records:
        if r["reason"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    read = sum(1 for r in reader.records if r["status"] == "read")
    return {
        "schema": SCHEMA,
        "source": {"pdf_sha256": digest, "pages": list(pages) if pages else None, "page_heights": heights},
        "systems": reader.systems,
        "events": reader.records,
        "bar_checks": checks,
        "summary": {"events": len(reader.records), "read_events": read, "unread_events": len(reader.records) - read,
                    "unread_reasons": dict(sorted(reasons.items())), "bars": bar_offset,
                    "bar_check_status": _count(c["status"] for c in checks)},
        "diagnostics": {
            "ignored_symbols": 0, "ignored_symbols_by_reason": {}, "arcs_not_ties": 0, "unassociated_numbers": 0,
            "label_numbers": 0, "events_outside_bars": 0, "pages_without_notation_staff": len(heights),
            "non_events": [], "non_events_by_reason": {}, "key_signatures": [], "time_signatures": time_signatures,
            "bar_time_signatures": basis, "bar_key_signatures": {},
            "tab_rhythm": {"schema": TAB_RHYTHM_SCHEMA, "basis": "printed_rhythm_marks_under_staffless_tab",
                           "marks_by_class": dict(sorted(marks_by_class.items())), "reader_counts": dict(sorted(reader.counts.items())),
                           "implied_rest_bars": implied, "unplaced_digits": unplaced, "bars": reader.bar_reports},
        },
    }


class _View:
    """A TabRaw fret candidate with its y on the page (TabRaw y runs on down the document)."""

    def __init__(self, candidate: Any, y: float) -> None:
        self.id = candidate.id
        self.x = candidate.x
        self.y = y
        self.string = candidate.string
        self.parsed_fret = candidate.parsed_fret
        self.kind = candidate.kind
        self.bbox = candidate.bbox


def _count(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))
