"""Read a printed time signature in a notation staff header from painted PDF contours (TS-READ-01).

A printed signature is two stacked rows of numerals, each numeral one painted contour, or the common-time
(C) or cut-time (C with a vertical stroke) contour. It follows the clef and key signature and precedes the
first note. Numerals are told apart by their form alone: the number of enclosed counters, the share of the
glyph width covered by single flat bars at its top and bottom, the longest stroke on its left edge. Every
limit is a multiple of the staff space or a fraction of the glyph's own box; none is a point size.

A signature is read only when every glyph in its rows is recognised and the rows pair up. Anything else is
recorded as ``unreadable`` with a located reason and is never guessed; the caller decides what that allows.
"""

from __future__ import annotations

from typing import Any

from ..pdf import _inside_fill
from .note_duration import Glyph, PageSymbols, Staff, _is_notehead

VALID_DENOMINATORS = (1, 2, 4, 8, 16, 32, 64)
MAX_NUMERATOR = 32

# Header geometry, in staff spaces.
CLEF_MAX_START_SPACES = 1.5
CLEF_MAX_END_SPACES = 4.0
CLEF_MIN_HEIGHT_SPACES = 5.0
SIGNATURE_REACH_SPACES = 3.0  # the first numeral starts this close to the clef or last key accidental
ROW_TOLERANCE_SPACES = 0.35  # a numeral lies inside its half of the staff, give or take this much
NUMERAL_MIN_HEIGHT_SPACES = 1.2
NUMERAL_MAX_HEIGHT_SPACES = 2.5
NUMERAL_MAX_WIDTH_SPACES = 2.4  # a digit is about as wide as it is tall; a slur, bend or beam is far wider
DIGIT_GAP_SPACES = 0.6  # digits of one number are this close or closer
ROW_ALIGN_SPACES = 0.6  # centres of the two stacked numbers agree within this
COMMON_MIN_HEIGHT_SPACES = 2.0
COMMON_MAX_HEIGHT_SPACES = 3.4
COMMON_CENTRE_SPACES = 0.5  # a C is centred on the middle line within this
COMMON_MIN_WIDTH_SPACES = 1.4
COMMON_MIN_ASPECT = 0.55  # a C is nearly as wide as it is tall; a rest is a narrow stroke
CUT_STROKE_OVERHANG_SPACES = 0.2

# Form measures, as fractions of the glyph's own box.
RASTER_ROWS = 40
BAR_MIN_ROWS = 2  # a bar is flat and thick; the round foot of a 9 or a 3 is wide for a single scan only
BAR_SHARE = 0.85  # a flat bar covers at least this share of the glyph width in one run
EDGE_BAND = 0.15  # top band in which a flat bar is measured
BASE_BAND = 0.25  # bottom band in which a base bar is measured (a base may carry feet below it)
STEM_FULL = 0.75  # a stem runs this share of the glyph height without a break
LOWER_RIGHT = (0.6, 0.8, 0.8, 1.0)  # (rows from, to, columns from, to), as fractions of the glyph box
MID_LEFT = (0.38, 0.5, 0.0, 0.28)
INK_ABSENT, INK_PRESENT, INK_PRESENT_STEM = 0.1, 0.5, 0.3  # share of a region's cells that are painted
SIX_NINE_SPLIT = 0.5
SIX_NINE_MARGIN = 0.08
FOUR_BAR_BAND = (0.5, 0.82)  # a 4's crossbar lies here; a 2's base bar lies below it


def glyph_raster(glyph: Glyph, rows: int = RASTER_ROWS) -> list[list[bool]]:
    """The glyph's painted fill sampled on a grid that keeps its aspect (rows x columns)."""
    x0, y0, x1, y1 = glyph.bbox
    width, height = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    columns = max(6, min(2 * rows, round(rows * width / height)))
    return [[bool(_inside_fill(x0 + (c + 0.5) * width / columns, y0 + (r + 0.5) * height / rows, glyph.shape))
             for c in range(columns)] for r in range(rows)]


def _runs_of(flags: list[bool]) -> list[tuple[int, int]]:
    out, start = [], None
    for i, on in enumerate(flags + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            out.append((start, i))
            start = None
    return out


def _counters(raster: list[list[bool]]) -> list[tuple[float, float]]:
    """Centroids (x, y as fractions of the box) of background regions not connected to the outside."""
    rows, columns = len(raster), len(raster[0])
    seen = [[False] * columns for _ in range(rows)]
    found: list[tuple[float, float]] = []

    def flood(r0: int, c0: int) -> tuple[bool, list[tuple[int, int]]]:
        stack, cells, outside = [(r0, c0)], [], False
        seen[r0][c0] = True
        while stack:
            r, c = stack.pop()
            cells.append((r, c))
            if r in (0, rows - 1) or c in (0, columns - 1):
                outside = True
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < columns and not seen[nr][nc] and not raster[nr][nc]:
                    seen[nr][nc] = True
                    stack.append((nr, nc))
        return outside, cells

    for r in range(rows):
        for c in range(columns):
            if not raster[r][c] and not seen[r][c]:
                outside, cells = flood(r, c)
                if not outside and len(cells) >= 2:
                    found.append((sum(c for _, c in cells) / len(cells) / columns,
                                  sum(r for r, _ in cells) / len(cells) / rows))
    return found


def classify_numeral(raster: list[list[bool]]) -> tuple[str | None, str | None]:
    """The digit this painted form is, or (None, why not). Ambiguous forms are not read."""
    rows, columns = len(raster), len(raster[0])
    row_runs = [_runs_of(row) for row in raster]
    counters = _counters(raster)

    def widest_single_run(lo: float, hi: float) -> float:
        """Widest share of the box covered by one unbroken run, if a flat bar is that wide for BAR_MIN_ROWS rows."""
        best, streak = 0.0, 0
        for r in range(int(lo * rows), max(int(lo * rows) + 1, int(hi * rows))):
            wide = r < rows and len(row_runs[r]) == 1 and (row_runs[r][0][1] - row_runs[r][0][0]) / columns >= BAR_SHARE
            streak = streak + 1 if wide else 0
            if streak >= BAR_MIN_ROWS:
                best = max(best, (row_runs[r][0][1] - row_runs[r][0][0]) / columns)
        return best

    top_bar = widest_single_run(0.0, EDGE_BAND)
    bottom_bar = widest_single_run(1 - BASE_BAND, 1.0)
    crossbar = widest_single_run(*FOUR_BAR_BAND) >= BAR_SHARE
    stem_full = any(len(runs) == 1 and (runs[0][1] - runs[0][0]) / rows >= STEM_FULL
                    for runs in (_runs_of([raster[r][c] for r in range(rows)]) for c in range(columns)))
    if len(counters) > 2:
        return None, "numeral_more_than_two_counters"
    if len(counters) == 2:
        upper, lower = sorted(counters, key=lambda p: p[1])
        return ("8", None) if upper[1] < 0.5 < lower[1] else (None, "numeral_two_counters_misplaced")
    if len(counters) <= 1 and stem_full and crossbar:
        return "4", None  # a full-height stem crossed by a full-width bar; the apex may be open or closed
    if len(counters) == 1:
        centre = counters[0][1]
        if centre >= SIX_NINE_SPLIT + SIX_NINE_MARGIN:
            return "6", None
        if centre <= SIX_NINE_SPLIT - SIX_NINE_MARGIN:
            return "9", None
        return None, "numeral_six_nine_ambiguous"
    if stem_full and top_bar < BAR_SHARE:
        return "1", None  # a lone stem, with a flag or a base serif at most
    if not stem_full and all(len(runs) <= 1 for runs in row_runs):
        return ("7", None) if top_bar >= BAR_SHARE else (None, "numeral_stroke_ambiguous")
    # No counter and some scan crosses two strokes: 2, 3, 5 or a serifed 7.
    def ink(r0: float, r1: float, c0: float, c1: float) -> float:
        cells = [raster[r][c] for r in range(int(r0 * rows), max(int(r0 * rows) + 1, int(r1 * rows)))
                 for c in range(int(c0 * columns), max(int(c0 * columns) + 1, int(c1 * columns)))]
        return sum(cells) / len(cells)

    lower_right = ink(*LOWER_RIGHT)  # the lower bowl of a 3 or 5; a 2's diagonal leaves this region empty
    mid_left = ink(*MID_LEFT)  # the stem of a 5 comes down this far; a 3 is open here
    flat_top = top_bar >= BAR_SHARE
    if flat_top and lower_right < INK_ABSENT and bottom_bar < BAR_SHARE:
        return "7", None
    if bottom_bar >= BAR_SHARE and not flat_top and not stem_full:
        return "2", None
    if lower_right < INK_ABSENT and mid_left < INK_ABSENT and not flat_top:
        return "2", None
    if lower_right >= INK_PRESENT:
        if mid_left >= INK_PRESENT_STEM:
            return "5", None
        if mid_left <= INK_ABSENT and not flat_top:
            return "3", None
    return None, "numeral_two_three_five_ambiguous"


def classify_common_cut(glyph: Glyph, raster: list[list[bool]], strokes: list[Any], space: float
                        ) -> tuple[str | None, str | None]:
    """'common' for an open C, 'cut' for a C with a vertical stroke through it."""
    rows, columns = len(raster), len(raster[0])
    if _counters(raster):
        return None, "common_time_closed_counter"
    right = [raster[r][columns - 1 - c] for r in range(rows) for c in range(max(1, columns // 6))]
    mid_rows = range(int(0.4 * rows), int(0.6 * rows))
    centre_column = columns // 2
    middle = [bool(raster[r][centre_column]) for r in range(rows)]
    middle_runs = _runs_of(middle)
    right_mid_open = not any(raster[r][c] for r in mid_rows for c in range(columns - max(1, columns // 6), columns))
    left_bowl = any(raster[r][0] for r in mid_rows) or any(raster[r][1] for r in mid_rows)
    if not (right_mid_open and left_bowl and any(right)):
        return None, "common_time_not_an_open_c"
    x0, y0, x1, y1 = glyph.bbox
    through = [s for s in strokes if x0 <= (s.x0 + s.x1) / 2 <= x1
               and min(s.y0, s.y1) <= y0 - CUT_STROKE_OVERHANG_SPACES * space
               and max(s.y0, s.y1) >= y1 + CUT_STROKE_OVERHANG_SPACES * space]
    if through or (len(middle_runs) == 1 and (middle_runs[0][1] - middle_runs[0][0]) / rows >= 0.9):
        return "cut", None
    if len(middle_runs) == 2:
        return "common", None
    return None, "common_time_cut_time_ambiguous"


def _clef(staff: Staff, symbols: PageSymbols) -> Glyph | None:
    s = staff.space
    clefs = [g for g in symbols.glyphs if g.bbox[0] <= staff.x0 + CLEF_MAX_START_SPACES * s
             and g.bbox[2] <= staff.x0 + CLEF_MAX_END_SPACES * s
             and g.h >= CLEF_MIN_HEIGHT_SPACES * s and abs(g.cy - (staff.top + 2 * s)) <= 2 * s]
    return clefs[0] if len(clefs) == 1 else None


def _first_number(row: list[tuple[Any, str]], space: float) -> tuple[list[tuple[Any, str]], list[tuple[Any, str]]]:
    """The leftmost run of digits that touch or nearly touch, and the glyphs left over after a wider gap.

    The digits of one number are set together; a glyph beyond the gap belongs to the music that follows.
    """
    ordered = sorted(row, key=lambda item: item[0].bbox[0])
    count = 1
    while count < len(ordered) and ordered[count][0].bbox[0] - ordered[count - 1][0].bbox[2] <= DIGIT_GAP_SPACES * space:
        count += 1
    return ordered[:count], ordered[count:]


def read_system_time_signature(staff: Staff, symbols: PageSymbols) -> dict[str, Any]:
    """The signature printed at a system start: ``read``, ``absent`` or ``unreadable`` (with a located reason)."""
    s = staff.space
    mid = staff.lines[2]
    location = {"page_index": staff.page_index, "staff_top": round(staff.top, 3), "staff_x0": round(staff.x0, 3)}

    def result(status: str, **extra: Any) -> dict[str, Any]:
        base = {"status": status, "numerator": None, "denominator": None, "shape": None, "sources": [],
                "reason": None, "location": location}
        base.update(extra)
        return base

    clef = _clef(staff, symbols)
    if clef is None:
        return result("unreadable", reason="time_signature_clef_unread")
    heads = [g for g in symbols.glyphs if _is_notehead(g, s) and staff.top - 2 * s <= g.cy <= staff.bottom + 2 * s
             and g.bbox[0] > clef.bbox[2]]
    first_note_x = min((g.bbox[0] for g in heads), default=staff.x1)
    lo, hi = clef.bbox[2] + 0.25 * s, first_note_x
    tol = ROW_TOLERANCE_SPACES * s
    rows: dict[str, list[tuple[Any, str]]] = {"top": [], "bottom": []}
    common: list[Glyph] = []
    unrecognised: dict[str, str] = {}
    for g in sorted(symbols.glyphs, key=lambda g: g.bbox[0]):
        if not lo <= g.bbox[0] < hi or g.ident == clef.ident:
            continue
        sized = NUMERAL_MIN_HEIGHT_SPACES * s <= g.h <= NUMERAL_MAX_HEIGHT_SPACES * s and g.w <= NUMERAL_MAX_WIDTH_SPACES * s
        if g.bbox[1] >= staff.top - tol and g.bbox[3] <= mid + tol and sized:
            row = "top"
        elif g.bbox[1] >= mid - tol and g.bbox[3] <= staff.bottom + tol and sized:
            row = "bottom"
        elif (COMMON_MIN_HEIGHT_SPACES * s <= g.h <= COMMON_MAX_HEIGHT_SPACES * s and g.curved
              and g.w >= COMMON_MIN_WIDTH_SPACES * s and g.w >= COMMON_MIN_ASPECT * g.h
              and abs(g.cy - mid) <= COMMON_CENTRE_SPACES * s):
            common.append(g)
            continue
        else:
            continue
        digit, why = classify_numeral(glyph_raster(g))
        if digit is None:
            unrecognised[g.ident] = why or "numeral_unrecognised"
            rows[row].append((g, "?"))
        else:
            rows[row].append((g, digit))
    reach = SIGNATURE_REACH_SPACES * s
    candidates = [item[0].bbox[0] for r in rows.values() for item in r] + [g.bbox[0] for g in common]
    if not candidates:
        return result("absent")
    # The signature follows the clef and any key accidentals: a run of header glyphs, each starting close to
    # the end of the one before. A numeral further from that run than the reach is not part of the header.
    edge = clef.bbox[2]
    for g in sorted(symbols.glyphs, key=lambda g: g.bbox[0]):
        if g.bbox[0] < lo or g.bbox[0] >= min(candidates) or g.ident == clef.ident:
            continue
        if not staff.top - 3 * s <= g.cy <= staff.bottom + s or g.bbox[0] - edge > reach:
            continue
        edge = max(edge, g.bbox[2])
    if min(candidates) - edge > reach:
        return result("absent")
    sources = [item[0].ident for r in rows.values() for item in r] + [g.ident for g in common]
    if common:
        if rows["top"] or rows["bottom"] or len(common) != 1:
            return result("unreadable", reason="time_signature_common_time_with_numerals", sources=sources)
        shape, why = classify_common_cut(common[0], glyph_raster(common[0]), symbols.segments, s)
        if shape is None:
            return result("unreadable", reason=why, sources=sources)
        value = (4, 4) if shape == "common" else (2, 2)
        return result("read", numerator=value[0], denominator=value[1], shape=f"{shape}_time", sources=sources)
    if not rows["top"] or not rows["bottom"]:
        # One half staff only: a rest or a stray mark beside the clef is not a stacked signature. It is
        # reported (never read, never used) so a numerator without a denominator stays visible.
        return result("absent", ignored_sources=sources)
    top_row, top_rest = _first_number(rows["top"], s)
    bottom_row, bottom_rest = _first_number(rows["bottom"], s)
    top, bottom = "".join(d for _, d in top_row), "".join(d for _, d in bottom_row)
    ignored_sources = [item[0].ident for item in top_rest + bottom_rest]
    sources = [item[0].ident for item in top_row + bottom_row]
    bad = [ident for ident in sources if ident in unrecognised]
    if bad:
        return result("unreadable", reason=unrecognised[bad[0]], sources=sources, ignored_sources=ignored_sources)
    centre = lambda row: (min(i[0].bbox[0] for i in row) + max(i[0].bbox[2] for i in row)) / 2  # noqa: E731
    if abs(centre(top_row) - centre(bottom_row)) > ROW_ALIGN_SPACES * s:
        return result("unreadable", reason="time_signature_rows_not_stacked", sources=sources,
                      ignored_sources=ignored_sources)
    numerator, denominator = int(top), int(bottom)
    if top.startswith("0") or bottom.startswith("0") or not 1 <= numerator <= MAX_NUMERATOR \
            or denominator not in VALID_DENOMINATORS:
        return result("unreadable", reason="time_signature_not_a_meter", sources=sources,
                      ignored_sources=ignored_sources, numerator=numerator, denominator=denominator)
    return result("read", numerator=numerator, denominator=denominator, shape="numerals", sources=sources,
                  ignored_sources=ignored_sources)
