"""Note-duration reader for the notation staff (DUR-01).

Every note and rest carries its own duration, written in its note type:

* the notehead (hollow or filled) and whether a stem is attached give the base value;
* each identified flag glyph hook, or each distinct beam line meeting the stem, halves it;
* each augmentation dot adds half of the previous value;
* a rest has its own glyph for each value, and takes dots the same way;
* a tuplet bracket or number scales only the notes it spans;
* a tie joins two written values into one sounding note: it is recorded, never merged.

Event counts, note spacing, defaults and the bar total are never a source of duration. The bar
total against the time signature is reported as a check only. When the symbols do not identify a
value, the event is recorded ``unread`` with a located reason: it is never guessed.

Symbols are read from the PDF's vector drawings with the painted-contour and visibility-at-contact
primitives built for L3-01 (``pdf._notehead_candidate_shapes`` and ``pdf._paints_into``): a stem
belongs to a notehead, and a flag to a stem, only where their paint actually touches. Glyph kinds are
identified from their painted form, by scanning the fill along lines: a beam is a band of constant
thickness, a flag blade crosses a scan line through its middle once per hook, a quarter rest is a
single stroke on every horizontal scan, a hooked rest has one hook band per value step.

All geometry is expressed in staff spaces of the staff being read.
"""

from __future__ import annotations

import hashlib
import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from score2gp.meter import bar_capacity_ticks

from .font_glyphs import is_music_font_text, music_font_drawings

from ..pdf import (
    CURVE_FLATTENING_TOLERANCE_PT,
    NOTEHEAD_MAX_HEIGHT_SPACES,
    NOTEHEAD_MAX_WIDTH_SPACES,
    NOTEHEAD_MIN_HEIGHT_SPACES,
    NOTEHEAD_MIN_WIDTH_SPACES,
    _NoteheadShape,
    _edges,
    _has_attached_notehead,
    _inside_fill,
    _notehead_candidate_shapes,
    _paints_ink,
    _paints_into,
    _path_subpaths,
)

SCHEMA = "note-duration-records.v0.6"  # v0.6: printed time signature per bar with its basis; v0.5: grace notes, located non-events; v0.4: located key signature per bar

WRITTEN_VALUES = {
    "whole": Fraction(4), "half": Fraction(2), "quarter": Fraction(1), "eighth": Fraction(1, 2),
    "16th": Fraction(1, 4), "32nd": Fraction(1, 8), "64th": Fraction(1, 16),
}
FLAGGED_VALUES = ["quarter", "eighth", "16th", "32nd", "64th"]  # by flag hooks or beam lines

# Staff and symbol geometry, in staff spaces.
# A small head (a grace or cue size) is narrower and lower than a full-size head of the same staff: measured
# 0.88 x 0.75 spaces against 1.18 x 1.0 for every other head, and 1.13 x 1.13 for the round ones; so a head
# under 1.0 wide and under 0.85 high is small. Both are ratios of this staff's own space, never points.
SMALL_HEAD_MAX_WIDTH_SPACES = 1.0
SMALL_HEAD_MAX_HEIGHT_SPACES = 0.85
# A grace note is engraved just before the note it ornaments: its head ends within this reach of the next
# head or accidental run of that note.
GRACE_MAX_GAP_SPACES = 3.0
# A stroke fragment of a wave glyph (vibrato, arpeggio) is thinner than any notehead measured (0.75 spaces).
STROKE_FRAGMENT_MAX_THIN_SPACES = 0.7
# REFUSE-07: a rolled-chord (arpeggio) wave is printed as a vertical stack of identical narrow curved
# strokes, each overlapping its neighbour; a stack of this many is a wave column, never a rest or a note.
WAVE_COLUMN_MIN_STROKES = 3
WAVE_COLUMN_X_TOLERANCE_SPACES = 0.05
WAVE_COLUMN_FORM_TOLERANCE_SPACES = 0.05
# The arrowhead that ends a wave column: a small filled glyph standing on the column's end and spanning it.
WAVE_ARROW_MAX_WIDTH_SPACES = 1.2
WAVE_ARROW_MAX_HEIGHT_SPACES = 1.3
WAVE_ARROW_END_GAP_SPACES = 0.1
WAVE_ARROW_END_OVERLAP_SPACES = 0.3
STAFF_LINE_MIN_LENGTH_PT = 50.0
STAFF_LINE_MERGE_GAP_PT = 20.0  # TAB lines are interrupted around fret numbers
# A staff line is mostly ink along its span (TAB lines about 0.8 despite fret-number gaps); a chain
# of ledger lines at one height is about 0.3.
STAFF_LINE_MIN_COVERAGE = 0.6
STAFF_LINE_END_TOLERANCE_PT = 3.0
STAFF_GAP_TOLERANCE = 0.03  # relative spacing tolerance between the lines of one staff
# Measured ordinary notation steps are about 4.25-6.38 pt in the mounted corpus. The largest
# filled vertical barline there is 0.68 pt; the enlarged source is 17.72 spaces with
# 2.84-pt bars. These bounds stay below normal rest-block widths.
RECT_VERTICAL_MAX_THICKNESS_SPACES = 0.24
RECT_HORIZONTAL_MAX_THICKNESS_SPACES = 0.16
STAFF_FIRST_STEP_MAX_SPACES = 2.35
# A page with no repeated long-line step has no scale to derive from; it keeps the limits
# the detector always used there (points) so its behaviour is unchanged.
UNSCALED_RECT_VERTICAL_MAX_PT = 1.5
UNSCALED_RECT_HORIZONTAL_MAX_PT = 1.0
UNSCALED_STAFF_FIRST_STEP_MAX_PT = 15.0
ZONE_REACH_SPACES = 8.0
BARLINE_END_TOLERANCE_SPACES = 0.15
BARLINE_MAX_WIDTH_SPACES = 1.0
BARLINE_CLUSTER_SPACES = 1.5
THICK_BARLINE_MIN_FILL_RATIO = 0.95
STEM_MAX_WIDTH_SPACES = 0.3
STEM_MIN_LENGTH_SPACES = 1.5
BEAM_MIN_WIDTH_SPACES = 0.5
BEAM_MIN_THICKNESS_SPACES = 0.3
BEAM_MAX_THICKNESS_SPACES = 0.9
BEAM_THICKNESS_VARIATION_SPACES = 0.15
BEAM_MAX_GAP_SPACES = 0.6  # between successive beam lines stacked inward from the stem tip
FLAG_MIN_HEIGHT_SPACES = 1.0
FLAG_MIN_REACH_SPACES = 0.5
DOT_MIN_SPACES, DOT_MAX_SPACES = 0.25, 0.6
DOT_ROUNDNESS_SPACES = 0.15
DOT_FIRST_GAP_SPACES = 1.3
DOT_NEXT_GAP_SPACES = 1.0
DOT_HEIGHT_TOLERANCE_SPACES = 0.75
# A dot painted as a zero-length stroke with round caps (a stroked point). Its painted disc is the stroke
# width; the stroke has no length of its own, so it is not a straight segment.
POINT_DOT_FORM = "stroked_point_dot"
POINT_DOT_MAX_LENGTH_FRACTION = 0.1  # of the stroke width
POINT_DOT_ROUND_CAP = 1  # PDF line cap style 1
POINT_DOT_RING_SIDES = 16
ARC_MIN_WIDTH_SPACES = 1.5
ARC_MAX_HEIGHT_SPACES = 1.3
# REFUSE-10: a tie or slur longer than a few notes rises above ARC_MAX_HEIGHT_SPACES yet stays a shallow
# crescent: its rise is a small part of its length (a semicircle is 0.5). Measured on the approved set, a
# taller form that is not a long arc is consumed as a tie without this bound and changes written output.
ARC_MAX_RISE_RATIO = 0.25
ARC_MAX_FILL_RATIO = 0.45  # below NOTEHEAD_MIN_FILL_RATIO: a crescent, never an oval
# REFUSE-10: a vibrato or trill line is a thin zigzag of at least this many direction reversals (four full
# periods), so a chevron or a single stroke is never one; it is at least this wide.
WAVY_LINE_MIN_REVERSALS = 8
WAVY_LINE_MIN_WIDTH_SPACES = 2.0
TIE_END_REACH_SPACES = 1.0
TIE_SAME_POSITION_SPACES = 0.25
TIE_VERTICAL_REACH_SPACES = 1.6
HEADER_CLEF_START_SPACES = 3.0
HEADER_CONTIGUITY_SPACES = 1.5
REPEAT_DOT_MAX_SPACES = 0.6  # a repeat dot is a small filled disc, at most this many spaces across
REPEAT_DOT_REACH_SPACES = 1.5  # ... standing within this many spaces right of the barline it belongs to
ACCIDENTAL_REACH_SPACES = 2.0
# REFUSE-18: the tallest parenthesis pair read around one stacked chord (staff spaces); taller strokes stay unread.
PAREN_CHORD_MAX_HEIGHT_SPACES = 6.5
REST_BLOCK = {"min_w": 0.8, "max_w": 1.8, "min_h": 0.3, "max_h": 0.8, "line": 0.12}
REST_QUARTER = {"min_w": 0.7, "max_w": 1.5, "min_h": 2.2, "max_h": 3.6}
# A quarter rest is one zigzag stroke: nearly every horizontal scan crosses it once (its foot curls,
# so a few cross twice). Sharps and naturals cross two or three times on most scans.
QUARTER_REST_SINGLE_RUN_SHARE = 0.75
REST_STEM_SLANT = (0.15, 0.8)  # a hooked rest's stem: leftward drop of its right edge per unit of height
REST_ROW_STEP_SPACES = 0.05
REST_EDGE_HYSTERESIS_SPACES = 0.1
REST_STEM_MARGIN_SPACES = 0.05
REST_HOOK_MIN_HEIGHT_SPACES = 0.2
REST_HOOK_MIN_WIDTH_SPACES = 0.2  # REFUSE-08: stem-edge slivers left by the cut (measured <= 0.1) are not hook balls (>= 0.58)
REST_STEM_TOP_SHARE = 0.3  # a hooked rest's stem top lies in the upper part of the glyph
REST_WINDOW = {"min_w": 0.6, "max_w": 2.6, "min_h": 0.3, "max_h": 6.0}
REST_VERTICAL_REACH_SPACES = 2.0
TUPLET_BRACKET_REACH_SPACES = 1.5
TUPLET_BRACKET_OVERLAP_SPACES = 0.3
TUPLET_NUMBER_BEAM_REACH_SPACES = 2.5
# DUR-04: a number over a longer, uneven beam group counts only its own notes; the run it stands over must lead
# the next-best run by this much (staff spaces) or the number stays unassociated rather than guessed.
TUPLET_RUN_MARGIN_SPACES = 1.0
LABEL_GAP_SPACES = 1.0
SCAN_SAMPLES = 16
# An oval fills pi/4 of its box, less when tilted; a tie crescent of notehead size fills about 0.3.
NOTEHEAD_MIN_FILL_RATIO = 0.5

DIGITS = re.compile(r"^(\d+)(?::(\d+))?$")


# --- primitives -----------------------------------------------------------------------------

@dataclass
class Glyph:
    """A drawn shape other than a straight staff line or vertical: noteheads, beams, flags..."""

    ident: str
    drawing: dict[str, Any]
    bbox: tuple[float, float, float, float]
    shape: _NoteheadShape
    curved: bool
    filled: bool
    # The shape and bounding box stay fixed for this page's reading. Reuse the
    # identical grid across notehead, key/time-signature and arc checks, without
    # retaining glyphs beyond their ordinary lifetime or mixing resolutions.
    _fill_ratios: dict[int, float] = field(default_factory=dict, init=False, repr=False, compare=False)

    @property
    def cx(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def cy(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2

    @property
    def w(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def h(self) -> float:
        return self.bbox[3] - self.bbox[1]


@dataclass
class Segment:
    """A straight stroke item or a thin filled rectangle."""

    ident: str
    x0: float
    y0: float
    x1: float
    y1: float
    width: float  # painted thickness

    @property
    def vertical(self) -> bool:
        return abs(self.x1 - self.x0) <= 0.05 and abs(self.y1 - self.y0) > 0.05

    @property
    def horizontal(self) -> bool:
        return abs(self.y1 - self.y0) <= 0.05 and abs(self.x1 - self.x0) > 0.05


@dataclass
class Polyline:
    """A stroked path made only of straight items (tuplet bracket pieces, for example)."""

    ident: str
    bbox: tuple[float, float, float, float]
    segments: list[tuple[float, float, float, float]]


@dataclass
class Text:
    ident: str
    text: str
    bbox: tuple[float, float, float, float]

    @property
    def cx(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def cy(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2


@dataclass
class Staff:
    page_index: int
    lines: list[float]
    x0: float
    x1: float
    line_ids: list[str]

    @property
    def space(self) -> float:
        return (self.lines[-1] - self.lines[0]) / (len(self.lines) - 1)

    @property
    def top(self) -> float:
        return self.lines[0]

    @property
    def bottom(self) -> float:
        return self.lines[-1]


@dataclass
class Stem:
    ident: str
    x: float
    y0: float
    y1: float
    half_width: float
    heads: list[Glyph] = field(default_factory=list)
    up: bool = True

    @property
    def tip(self) -> float:
        return self.y0 if self.up else self.y1

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (self.x - self.half_width, self.y0, self.x + self.half_width, self.y1)


@dataclass
class PageSymbols:
    page_index: int
    glyphs: list[Glyph]
    segments: list[Segment]
    polylines: list[Polyline]
    texts: list[Text]
    head_shapes: list[_NoteheadShape]
    page_staff_space: float | None = None


# --- fill scanning --------------------------------------------------------------------------

def _runs(shape: _NoteheadShape, vertical: bool, at: float, lo: float, hi: float) -> list[tuple[float, float]]:
    """Maximal stretches of [lo, hi] painted by the shape's fill along a scan line.

    ``vertical`` scans the line x = ``at`` over y in [lo, hi]; otherwise the line y = ``at``.
    Exact: the line is cut wherever an outline edge crosses it and each piece is tested once.
    """
    cuts = {lo, hi}
    for ax, ay, bx, by in shape.fill_edges:
        if vertical:
            a, b, p, q = ax, bx, ay, by
        else:
            a, b, p, q = ay, by, ax, bx
        if a != b and min(a, b) <= at <= max(a, b):
            v = p + (at - a) * (q - p) / (b - a)
            if lo < v < hi:
                cuts.add(v)
    ordered = sorted(cuts)
    runs: list[list[float]] = []
    for a, b in zip(ordered, ordered[1:]):
        if b - a <= 1e-9:
            continue
        m = (a + b) / 2
        inside = _inside_fill(at, m, shape) if vertical else _inside_fill(m, at, shape)
        if not inside:
            continue
        if runs and abs(runs[-1][1] - a) <= 1e-6:
            runs[-1][1] = b
        else:
            runs.append([a, b])
    return [(a, b) for a, b in runs]


def _fill_ratio(glyph: Glyph, n: int = 12) -> float:
    if n in glyph._fill_ratios:
        return glyph._fill_ratios[n]
    x0, y0, x1, y1 = glyph.bbox
    hits = sum(
        _inside_fill(x0 + (i + 0.5) * (x1 - x0) / n, y0 + (j + 0.5) * (y1 - y0) / n, glyph.shape)
        for i in range(n) for j in range(n)
    )
    ratio = hits / (n * n)
    glyph._fill_ratios[n] = ratio
    return ratio


def _row_counts(glyph: Glyph, samples: int = SCAN_SAMPLES) -> list[int]:
    """Painted runs on horizontal scans spread over the glyph's height."""
    x0, y0, x1, y1 = glyph.bbox
    return [len(_runs(glyph.shape, False, y0 + (k + 0.5) * (y1 - y0) / samples, x0 - 1, x1 + 1))
            for k in range(samples)]


def _column_counts(glyph: Glyph, fractions: tuple[float, ...]) -> list[int]:
    x0, y0, x1, y1 = glyph.bbox
    return [len(_runs(glyph.shape, True, x0 + f * (x1 - x0), y0 - 1, y1 + 1)) for f in fractions]


# --- extraction -----------------------------------------------------------------------------

def _measured_page_staff_space(drawings: list[dict[str, Any]], page_width: float) -> float | None:
    """Read the repeated staff-line step from long horizontal strokes before classifying rectangles.

    The same PDF path can contain notation and TAB with different line steps. The smaller
    repeated step is the conservative scale for both; a barline or TAB line still has to
    pass the ordinary staff-local geometry checks later. Isolated ledger lines cannot
    supply the required repeated step.
    """
    by_span: dict[tuple[float, float], set[float]] = {}
    for drawing in drawings:
        if not _paints_ink(drawing.get("color"), drawing.get("stroke_opacity"), None):
            continue
        if _paints_ink(drawing.get("fill"), drawing.get("fill_opacity"), None):
            continue
        for item in drawing.get("items", []):
            if item[0] != "l" or abs(float(item[1].y - item[2].y)) > 0.05:
                continue
            x0, x1 = sorted((float(item[1].x), float(item[2].x)))
            if x1 - x0 < 0.08 * page_width:
                continue
            by_span.setdefault((round(x0, 1), round(x1, 1)), set()).add(round(float(item[1].y), 2))
    gaps: list[float] = []
    for positions in by_span.values():
        ys = sorted(positions)
        if len(ys) < 4:
            continue
        gaps.extend(b - a for a, b in zip(ys, ys[1:]) if b > a)
    bins = Counter(round(gap, 1) for gap in gaps)
    repeated = [key for key, count in bins.items() if count >= 3]
    if not repeated:
        return None
    smallest = min(repeated)
    return statistics.median(gap for gap in gaps if round(gap, 1) == smallest)

def extract_page_symbols(page: Any, page_index: int, *, include_music_font: bool = True) -> PageSymbols:
    """Split a PyMuPDF page's drawings into glyphs, straight segments, polylines and texts."""
    import pymupdf  # noqa: PLC0415 - image-free text extraction flags
    drawings = page.get_drawings()
    if include_music_font:
        drawings += music_font_drawings(page)
    page_staff_space = _measured_page_staff_space(drawings, float(page.rect.width))
    try:
        image_rects = [tuple(info["bbox"]) for info in page.get_image_info()]
    except Exception:  # noqa: BLE001 - image metadata is optional evidence
        image_rects = []
    # Curved drawings keep the L3-01 painted shape (with the paint beneath them), so contact is
    # judged where paint is visible. _notehead_candidate_shapes returns one shape per curved
    # drawing that can paint, in drawing order; the same predicate selects them here.
    curved_shapes = iter(_notehead_candidate_shapes(drawings, image_rects))
    glyphs: list[Glyph] = []
    segments: list[Segment] = []
    polylines: list[Polyline] = []
    for index, drawing in enumerate(drawings):
        rect = drawing.get("rect")
        items = drawing.get("items", [])
        if rect is None or not items:
            continue
        ident = f"p{page_index}:d{index}"
        is_curved = any(item and item[0] == "c" for item in items)
        filled = _paints_ink(drawing.get("fill"), drawing.get("fill_opacity"), None)
        stroked = _paints_ink(drawing.get("color"), drawing.get("stroke_opacity"), None)
        if is_curved:
            if not (filled or stroked):
                continue
            shape = next(curved_shapes)
            glyphs.append(Glyph(ident, drawing, shape.bbox, shape, True, filled))
            continue
        kinds = {item[0] for item in items}
        point = _stroked_point_dot(drawing, items) if stroked and not filled else None
        if point is not None:
            cx, cy, width = point
            half = width / 2
            ring = [(cx + half * math.cos(2 * math.pi * k / POINT_DOT_RING_SIDES),
                     cy + half * math.sin(2 * math.pi * k / POINT_DOT_RING_SIDES))
                    for k in range(POINT_DOT_RING_SIDES)]
            shape = _NoteheadShape(
                bbox=(cx - half, cy - half, cx + half, cy + half), fill_edges=_edges([ring], close=True),
                stroke_edges=(), stroke_half_width=0.0, even_odd=False, fill_color=drawing.get("color"),
                fill_opacity=drawing.get("stroke_opacity"))
            point_drawing = dict(drawing)
            point_drawing["source_form"] = POINT_DOT_FORM
            glyphs.append(Glyph(ident, point_drawing, shape.bbox, shape, False, True))
            continue
        if stroked and not filled and kinds == {"l"}:
            width = float(drawing.get("width") or 0.0)
            pieces = []
            for k, item in enumerate(items):
                a, b = item[1], item[2]
                pieces.append((float(a.x), float(a.y), float(b.x), float(b.y)))
                segments.append(Segment(f"{ident}.{k}", float(a.x), float(a.y), float(b.x), float(b.y), width))
            if len(items) >= 2:
                polylines.append(Polyline(ident, (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)), pieces))
            continue
        if not filled:
            continue
        if kinds == {"re"} and len(items) == 1:
            r = items[0][1]
            w, h = float(r.x1 - r.x0), float(r.y1 - r.y0)
            if page_staff_space:
                vertical_limit = RECT_VERTICAL_MAX_THICKNESS_SPACES * page_staff_space
                horizontal_limit = RECT_HORIZONTAL_MAX_THICKNESS_SPACES * page_staff_space
            else:
                vertical_limit = UNSCALED_RECT_VERTICAL_MAX_PT
                horizontal_limit = UNSCALED_RECT_HORIZONTAL_MAX_PT
            if w <= vertical_limit and h > 3 * w:  # a vertical drawn as a filled rectangle
                x = float(r.x0 + r.x1) / 2
                segments.append(Segment(ident, x, float(r.y0), x, float(r.y1), w))
                continue
            if h <= horizontal_limit and w > 3 * h:  # a horizontal drawn as a filled rectangle
                y = float(r.y0 + r.y1) / 2
                segments.append(Segment(ident, float(r.x0), y, float(r.x1), y, h))
                continue
        subpaths = _path_subpaths(items)
        shape = _NoteheadShape(
            bbox=(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)),
            fill_edges=_edges(subpaths, close=True), stroke_edges=(), stroke_half_width=0.0,
            even_odd=bool(drawing.get("even_odd")), fill_color=drawing.get("fill"),
            fill_opacity=drawing.get("fill_opacity"),
        )
        glyphs.append(Glyph(ident, drawing, shape.bbox, shape, False, True))
    texts: list[Text] = []
    # Image geometry is already collected above; no text consumer needs image
    # bytes. Keep the text route bounded by text, including on refused scans.
    for block in page.get_text("rawdict", flags=pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES).get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for chars in _tokens([c for c in span.get("chars", [])
                                      if not include_music_font or not is_music_font_text(c["c"], span.get("font", ""))],
                                     float(span.get("size") or 0.0)):
                    text = "".join(c["c"] for c in chars)
                    box = _bbox_union([tuple(float(v) for v in c["bbox"]) for c in chars])
                    texts.append(Text(f"p{page_index}:t{len(texts)}", text, box))
    head_shapes = [g.shape for g in glyphs if g.curved or (
        g.drawing.get("source_form") == "font_glyph_outline"
        and page_staff_space and _is_dead_note_x_head(g, page_staff_space))]
    return PageSymbols(page_index, glyphs, segments, polylines, texts, head_shapes, page_staff_space)


def _stroked_point_dot(drawing: dict[str, Any], items: list[Any]) -> tuple[float, float, float] | None:
    """Centre and diameter of a dot painted as one zero-length round-capped stroke, else None."""
    width = float(drawing.get("width") or 0.0)
    caps = drawing.get("lineCap") or ()
    if width <= 0 or len(items) != 1 or items[0][0] != "l" or not caps or any(c != POINT_DOT_ROUND_CAP for c in caps):
        return None
    a, b = items[0][1], items[0][2]
    if math.hypot(float(a.x) - float(b.x), float(a.y) - float(b.y)) > POINT_DOT_MAX_LENGTH_FRACTION * width:
        return None
    return (float(a.x) + float(b.x)) / 2, (float(a.y) + float(b.y)) / 2, width


def _tokens(chars: list[dict[str, Any]], size: float) -> list[list[dict[str, Any]]]:
    """Characters of a span split where the baseline changes or a visible gap opens.

    Text extraction may join glyphs that are printed apart, such as the two stacked numbers of a
    time signature; each printed group is its own token. Spaces stay inside a phrase, so a label
    such as "Example 1" never yields a bare number. Surrounding spaces are trimmed.
    """
    tokens: list[list[dict[str, Any]]] = []
    for char in chars:
        if tokens:
            previous = tokens[-1][-1]
            same_line = abs(float(char["origin"][1]) - float(previous["origin"][1])) <= 0.1 * size
            touching = float(char["bbox"][0]) - float(previous["bbox"][2]) <= 0.3 * size
            if same_line and touching:
                tokens[-1].append(char)
                continue
        tokens.append([char])
    trimmed = []
    for token in tokens:
        while token and not token[0].get("c", "").strip():
            token = token[1:]
        while token and not token[-1].get("c", "").strip():
            token = token[:-1]
        if token:
            trimmed.append(token)
    return trimmed


def _coverage(pieces: list[tuple[float, float]]) -> float:
    """Length covered by the union of intervals."""
    total, end = 0.0, -math.inf
    for a, b in sorted(pieces):
        if b > end:
            total += b - max(a, end)
            end = b
    return total


def find_staves(symbols: PageSymbols) -> tuple[list[Staff], list[Staff]]:
    """Five-line notation staves and six-line TAB staves: runs of equally spaced long horizontals."""
    # Every horizontal piece joins the merge, however short: TAB lines are drawn as short pieces
    # between fret numbers. Only the merged line must be long.
    pieces = sorted((s for s in symbols.segments if s.horizontal), key=lambda s: ((s.y0 + s.y1) / 2, min(s.x0, s.x1)))
    lines: list[dict[str, Any]] = []
    for s in pieces:
        y, a, b = (s.y0 + s.y1) / 2, min(s.x0, s.x1), max(s.x0, s.x1)
        for line in lines:
            if abs(line["y"] - y) <= 0.05 and a <= line["x1"] + STAFF_LINE_MERGE_GAP_PT and b >= line["x0"] - STAFF_LINE_MERGE_GAP_PT:
                line["x0"], line["x1"] = min(line["x0"], a), max(line["x1"], b)
                line["ids"].append(s.ident)
                line["pieces"].append((a, b))
                break
        else:
            lines.append({"y": y, "x0": a, "x1": b, "ids": [s.ident], "pieces": [(a, b)]})
    lines = [line for line in lines if line["x1"] - line["x0"] >= STAFF_LINE_MIN_LENGTH_PT
             and _coverage(line["pieces"]) >= STAFF_LINE_MIN_COVERAGE * (line["x1"] - line["x0"])]
    lines.sort(key=lambda line: line["y"])
    notation: list[Staff] = []
    tab: list[Staff] = []
    used: set[int] = set()
    for i, first in enumerate(lines):
        if i in used:
            continue
        run = [i]
        gap = None
        for j in range(i + 1, len(lines)):
            if j in used:
                continue
            other = lines[j]
            # The lines of one staff start and end together; a chain of tuplet-bracket or ledger
            # pieces at a staff-line height does not.
            if abs(other["x0"] - first["x0"]) > STAFF_LINE_END_TOLERANCE_PT or abs(other["x1"] - first["x1"]) > STAFF_LINE_END_TOLERANCE_PT:
                continue
            step = other["y"] - lines[run[-1]]["y"]
            if gap is None:
                first_step_limit = (
                    STAFF_FIRST_STEP_MAX_SPACES * symbols.page_staff_space
                    if symbols.page_staff_space
                    else UNSCALED_STAFF_FIRST_STEP_MAX_PT
                )
                if step > first_step_limit:
                    break
                gap = step
                run.append(j)
            elif abs(step - gap) <= STAFF_GAP_TOLERANCE * gap + 0.05:
                run.append(j)
            else:
                break
        if len(run) in (5, 6):
            used.update(run)
            members = [lines[k] for k in run]
            staff = Staff(symbols.page_index, [m["y"] for m in members], min(m["x0"] for m in members),
                          max(m["x1"] for m in members), [ident for m in members for ident in m["ids"]])
            (notation if len(run) == 5 else tab).append(staff)
    return notation, tab


# --- stems, beams, flags, dots --------------------------------------------------------------

def _is_notehead(glyph: Glyph, space: float) -> str | None:
    """"filled" or "hollow" when the glyph has a notehead's size and painted form, else None."""
    if not glyph.curved:
        return None
    if not (NOTEHEAD_MIN_WIDTH_SPACES * space <= glyph.w <= NOTEHEAD_MAX_WIDTH_SPACES * space):
        return None
    if not (NOTEHEAD_MIN_HEIGHT_SPACES * space <= glyph.h <= NOTEHEAD_MAX_HEIGHT_SPACES * space):
        return None
    if not glyph.filled:
        return "hollow" if glyph.shape.stroke_edges else None
    if _inside_fill(glyph.cx, glyph.cy, glyph.shape):
        return "filled" if _fill_ratio(glyph) >= NOTEHEAD_MIN_FILL_RATIO else None
    # A ring: the centre is unpainted and scans through it cross the outline on both sides.
    across = len(_runs(glyph.shape, False, glyph.cy, glyph.bbox[0] - 1, glyph.bbox[2] + 1))
    down = len(_runs(glyph.shape, True, glyph.cx, glyph.bbox[1] - 1, glyph.bbox[3] + 1))
    return "hollow" if across == 2 and down == 2 else None


def _is_small_head(glyph: Glyph, space: float) -> bool:
    """A notehead drawn smaller than this staff's full-size heads (grace and cue size)."""
    return glyph.w < SMALL_HEAD_MAX_WIDTH_SPACES * space and glyph.h < SMALL_HEAD_MAX_HEIGHT_SPACES * space


def _is_dead_note_x_head(glyph: Glyph, space: float) -> bool:
    """A head-sized cross has two arms on either side and one crossing at its centre.

    These are ownership evidence only: UNREAD-01 never gives an X a written value.
    The real-source census includes ledger-line crosses outside the rest window.
    """
    if not glyph.filled or (not glyph.curved and glyph.drawing.get("source_form") != "font_glyph_outline"):
        return False
    if not (NOTEHEAD_MIN_WIDTH_SPACES <= glyph.w / space <= NOTEHEAD_MAX_WIDTH_SPACES
            and NOTEHEAD_MIN_HEIGHT_SPACES <= glyph.h / space <= NOTEHEAD_MAX_HEIGHT_SPACES):
        return False
    rows = _row_counts(glyph)
    return (rows[0] == rows[-1] == 2 and rows[len(rows) // 2] == 1
            and _column_counts(glyph, (0.1, 0.5, 0.9)) == [2, 1, 2])


def _unread_shape_class(glyph: Glyph, space: float) -> str:
    """Name the measured form of an unread glyph without accepting its value."""
    if _is_dead_note_x_head(glyph, space):
        return "dead_note_x_head"
    if _is_beam(glyph, space):
        return "constant_thickness_band"
    if glyph.curved:
        if glyph.w <= space and glyph.h <= 1.1 * space:
            return "narrow_curved_stroke"
        if glyph.h >= 2 * space:
            return "rest_sized_curve"
        return "other_curved_form"
    return "straight_form"


def _parenthesis_inner_edges(head: Glyph, glyphs: list[Glyph], space: float) -> list[float]:
    """Left edges a head's left parenthesis may abut: the head itself, or its own recognised accidental."""
    return [head.bbox[0]] + [
        a.bbox[0] for a in glyphs
        if a.ident != head.ident and head.bbox[0] - a.bbox[2] <= ACCIDENTAL_REACH_SPACES * space
        and a.bbox[2] <= head.bbox[0] + 0.1 * space and a.bbox[1] <= head.bbox[3] and head.bbox[1] <= a.bbox[3]
        and _accidental_direction(a, space)]


def _notehead_parentheses(glyphs: list[Glyph], heads: list[Glyph],
                          space: float, chord_pairs: set[str] | None = None) -> dict[str, list[Glyph]]:
    """Paired curved strokes enclosing one head, not a new note or a rest.

    The approved contours have one horizontal paint run and two vertical
    runs toward the open side. Their size and contact with the enclosed head
    are staff-relative. Parenthesized/ghost-note output has no IR contract,
    so this locates an unsupported form; it does not discard an annotation.
    """
    sides: dict[str, list[Glyph]] = {"left": [], "right": []}
    tall: dict[str, list[Glyph]] = {"left": [], "right": []}
    for glyph in glyphs:
        if not (glyph.curved and glyph.filled and 0.4 <= glyph.w / space <= 1.0):
            continue
        height = glyph.h / space
        if not (0.75 <= height <= PAREN_CHORD_MAX_HEIGHT_SPACES):
            continue
        if any(count != 1 for count in _row_counts(glyph)):
            continue
        columns = _column_counts(glyph, (0.1, 0.5, 0.9))
        side = "left" if columns == [0, 2, 2] else "right" if columns == [2, 2, 0] else None
        if side is None:
            continue
        (sides if height <= 1.25 else tall)[side].append(glyph)
    pairs: dict[str, list[Glyph]] = {}
    for head in heads:
        # REFUSE-16: a head's own printed accidental stands inside its parentheses, so the left one then
        # abuts that accidental (a recognised sharp, flat or natural just left of the head), not the head.
        edges = _parenthesis_inner_edges(head, glyphs, space)
        left = [g for g in sides["left"]
                if abs(g.cy - head.cy) <= 0.15 * space
                and any(abs(g.bbox[2] - edge) <= 0.25 * space for edge in edges)]
        right = [g for g in sides["right"]
                 if abs(g.cy - head.cy) <= 0.15 * space
                 and abs(g.bbox[0] - head.bbox[2]) <= 0.25 * space]
        if len(left) == len(right) == 1 and abs(left[0].h - right[0].h) <= 0.1 * space:
            pairs[head.ident] = [left[0], right[0]]
    ownership: dict[str, int] = {}
    for pair in pairs.values():
        for glyph in pair:
            ownership[glyph.ident] = ownership.get(glyph.ident, 0) + 1
    result = {head: pair for head, pair in pairs.items()
              if all(ownership[g.ident] == 1 for g in pair)}
    chords = _chord_parentheses(glyphs, heads, tall, space, set(result)) if chord_pairs is not None else {}
    chord_pairs = chord_pairs if chord_pairs is not None else set()
    chord_pairs.update(chords)
    result.update(chords)
    return result


def _chord_parentheses(glyphs: list[Glyph], heads: list[Glyph], tall: dict[str, list[Glyph]],
                       space: float, taken: set[str]) -> dict[str, list[Glyph]]:
    """REFUSE-18: one tall parenthesis pair enclosing every head of a stacked chord (a ghost chord).

    The pair is two curved strokes of one measured form and equal height, taller than a single-head pair.
    It encloses the heads whose centres lie within its vertical span and between its strokes; its left
    stroke abuts the left edge of those heads (or a recognised accidental of one) and its right stroke
    abuts their right edge. At least two heads must be enclosed and no head may be claimed by another
    pair, and no stroke may fit two candidate pairs: otherwise the pair is not matched and the
    strokes stay located, unread symbols. The value comes from the printed shapes, never from spacing.
    """
    found: dict[str, list[Glyph]] = {}
    claimed: dict[str, int] = {}
    candidates = []
    for left in tall["left"]:
        for right in tall["right"]:
            if (abs(left.cy - right.cy) > 0.15 * space or abs(left.h - right.h) > 0.1 * space
                    or not left.bbox[2] <= right.bbox[0] or right.bbox[0] - left.bbox[2] > 2.5 * space):
                continue
            inside = [h for h in heads
                      if left.bbox[1] - 0.1 * space <= h.cy <= left.bbox[3] + 0.1 * space
                      and left.bbox[2] - 0.1 * space <= h.bbox[0] and h.bbox[2] <= right.bbox[0] + 0.1 * space]
            if len(inside) < 2 or any(h.ident in taken for h in inside):
                continue
            inner_left = min(edge for h in inside for edge in _parenthesis_inner_edges(h, glyphs, space))
            if (abs(left.bbox[2] - inner_left) > 0.25 * space
                    or abs(right.bbox[0] - max(h.bbox[2] for h in inside)) > 0.25 * space):
                continue
            candidates.append((left, right, inside))
    for left, right, inside in candidates:
        for glyph in (left, right):
            claimed[glyph.ident] = claimed.get(glyph.ident, 0) + 1
        for h in inside:
            claimed[h.ident] = claimed.get(h.ident, 0) + 1
    for left, right, inside in candidates:
        if claimed[left.ident] == claimed[right.ident] == 1 and all(claimed[h.ident] == 1 for h in inside):
            for h in inside:
                found[h.ident] = [left, right]
    return found


def _is_stroke_fragment_outside_band(glyph: Glyph, staff: Staff) -> bool:
    """A thin piece of a wave glyph (vibrato squiggle, arpeggio stroke) lying wholly outside the five-line band.

    A rest stands within the band (its glyph touches or crosses it) and every notehead is at least as
    thin as the smallest head, so a piece thinner than that, above the top line or below the bottom
    line, is neither a note nor a rest.
    """
    s = staff.space
    outside = glyph.bbox[3] <= staff.top or glyph.bbox[1] >= staff.bottom
    return outside and glyph.curved and glyph.filled and min(glyph.w, glyph.h) < STROKE_FRAGMENT_MAX_THIN_SPACES * s


def _wave_column_ids(glyphs: list[Glyph], space: float) -> set[str]:
    """REFUSE-07: the strokes of a vertical wave column (a rolled-chord mark's body), and its arrowhead.

    A rolled chord's wave is drawn as a stack of identical narrow curved strokes sharing one left edge,
    each touching or overlapping the next. A rest is a single glyph and a notehead is never this narrow, so
    a run of ``WAVE_COLUMN_MIN_STROKES`` or more strokes of one measured form, stacked without a gap, is a
    wave column. A lone stroke, or strokes of unequal form or with a gap between them, is not matched.
    """
    narrow = [g for g in glyphs if g.curved and g.filled and g.w <= space and g.h <= 1.1 * space]
    ids: set[str] = set()
    columns: list[list[Glyph]] = []
    used: set[str] = set()
    for first in sorted(narrow, key=lambda g: (g.bbox[0], g.bbox[1])):
        if first.ident in used:
            continue
        column = sorted(
            (g for g in narrow
             if abs(g.bbox[0] - first.bbox[0]) <= WAVE_COLUMN_X_TOLERANCE_SPACES * space
             and abs(g.w - first.w) <= WAVE_COLUMN_FORM_TOLERANCE_SPACES * space
             and abs(g.h - first.h) <= WAVE_COLUMN_FORM_TOLERANCE_SPACES * space),
            key=lambda g: g.bbox[1])
        used.update(g.ident for g in column)
        run = column[:1]
        for g in column[1:] + [None]:
            if g is not None and g.bbox[1] <= run[-1].bbox[3] + 0.01 * space:
                run.append(g)
                continue
            if len(run) >= WAVE_COLUMN_MIN_STROKES:
                ids.update(r.ident for r in run)
                columns.append(run)
            run = [g] if g is not None else []
    # The arrowhead is the small filled glyph standing on either end of a column and spanning its width.
    for run in columns:
        left, right = min(r.bbox[0] for r in run), max(r.bbox[2] for r in run)
        top, bottom = min(r.bbox[1] for r in run), max(r.bbox[3] for r in run)
        for g in glyphs:
            if (g.ident not in ids and g.filled and g.w <= WAVE_ARROW_MAX_WIDTH_SPACES * space
                    and g.h <= WAVE_ARROW_MAX_HEIGHT_SPACES * space
                    and g.bbox[0] <= left + 0.01 * space and g.bbox[2] >= right - 0.01 * space
                    and (-WAVE_ARROW_END_GAP_SPACES * space <= g.bbox[3] - top <= WAVE_ARROW_END_OVERLAP_SPACES * space
                         or -WAVE_ARROW_END_GAP_SPACES * space <= bottom - g.bbox[1]
                         <= WAVE_ARROW_END_OVERLAP_SPACES * space)):
                ids.add(g.ident)
    return ids


def _is_dot(glyph: Glyph, space: float) -> bool:
    return (glyph.filled and DOT_MIN_SPACES * space <= glyph.w <= DOT_MAX_SPACES * space
            and DOT_MIN_SPACES * space <= glyph.h <= DOT_MAX_SPACES * space
            and abs(glyph.w - glyph.h) <= DOT_ROUNDNESS_SPACES * space
            and _inside_fill(glyph.cx, glyph.cy, glyph.shape))


def _is_beam(glyph: Glyph, space: float) -> bool:
    """A beam line is a filled band of constant vertical thickness along its length."""
    if not glyph.filled or glyph.w < BEAM_MIN_WIDTH_SPACES * space:
        return False
    thicknesses = []
    for f in (0.1, 0.5, 0.9):
        runs = _runs(glyph.shape, True, glyph.bbox[0] + f * glyph.w, glyph.bbox[1] - 1, glyph.bbox[3] + 1)
        if len(runs) != 1:
            return False
        thicknesses.append(runs[0][1] - runs[0][0])
    return (min(thicknesses) >= BEAM_MIN_THICKNESS_SPACES * space
            and max(thicknesses) <= BEAM_MAX_THICKNESS_SPACES * space
            and max(thicknesses) - min(thicknesses) <= BEAM_THICKNESS_VARIATION_SPACES * space)


def _arc_joins_note_and_grace(glyph: Glyph, events: list[dict[str, Any]], space: float) -> bool:
    """True for an arc leaving one single-head event and ending on the next, one of them a grace, with both
    heads at one staff position: the notation of a tie onto or from a grace note."""
    notes = sorted(((e, e["_heads"][0]) for e in events if len(e.get("_heads", [])) == 1),
                   key=lambda item: item[0]["_cx"])
    reach = TIE_END_REACH_SPACES * space
    starts = [i for i, (_e, h) in enumerate(notes) if h.bbox[0] - 0.3 * space <= glyph.bbox[0] <= h.bbox[2] + reach]
    stops = [i for i, (_e, h) in enumerate(notes) if h.bbox[0] - reach <= glyph.bbox[2] <= h.bbox[2] + 0.3 * space]
    if len(starts) != 1 or len(stops) != 1 or stops[0] != starts[0] + 1:
        return False
    (first, a), (last, b) = notes[starts[0]], notes[stops[0]]
    return bool(first.get("_grace") or last.get("_grace")) and abs(a.cy - b.cy) <= TIE_SAME_POSITION_SPACES * space


def _is_arc(glyph: Glyph, space: float) -> bool:
    """A tie or slur: a thin filled crescent, which leaves most of its box unpainted."""
    return (glyph.curved and glyph.filled and glyph.w >= ARC_MIN_WIDTH_SPACES * space
            and glyph.h <= ARC_MAX_HEIGHT_SPACES * space and _fill_ratio(glyph) <= ARC_MAX_FILL_RATIO)


def _is_slanted_arc(glyph: Glyph, space: float) -> bool:
    """A tapered crescent, measuring its bow relative to its endpoint slope.

    A slanted slur's axis-aligned box includes the change in head position.
    Keep the existing curvature bound, but measure the painted bow above or
    below the line joining its ends. Every scan must cross one thin band,
    tapering at both ends; a box or a low fill ratio alone is insufficient.
    """
    if not (glyph.curved and glyph.filled and glyph.w >= ARC_MIN_WIDTH_SPACES * space
            and _fill_ratio(glyph) <= ARC_MAX_FILL_RATIO):
        return False
    fractions = (0.05, 0.25, 0.5, 0.75, 0.95)
    scans = [_runs(glyph.shape, True, glyph.bbox[0] + f * glyph.w,
                   glyph.bbox[1] - 1, glyph.bbox[3] + 1) for f in fractions]
    if any(len(runs) != 1 for runs in scans):
        return False
    widths = [runs[0][1] - runs[0][0] for runs in scans]
    if not (max(widths[0], widths[-1]) < min(widths[1:-1])
            and max(widths) < BEAM_MIN_THICKNESS_SPACES * space):
        return False
    centers = [(runs[0][0] + runs[0][1]) / 2 for runs in scans]
    residuals = [centers[i] - (centers[0] + (centers[-1] - centers[0])
                 * (f - fractions[0]) / (fractions[-1] - fractions[0]))
                 for i, f in enumerate(fractions) if 0 < i < len(fractions) - 1]
    return ((all(v > 0 for v in residuals) or all(v < 0 for v in residuals))
            and max(map(abs, residuals)) <= ARC_MAX_HEIGHT_SPACES * space)


def _is_crescent_band(glyph: Glyph, space: float) -> bool:
    """A thin band tapering at both ends: one painted run on every vertical scan, ends thinner than the middle."""
    fractions = (0.05, 0.25, 0.5, 0.75, 0.95)
    scans = [_runs(glyph.shape, True, glyph.bbox[0] + f * glyph.w, glyph.bbox[1] - 1, glyph.bbox[3] + 1)
             for f in fractions]
    if any(len(runs) != 1 for runs in scans):
        return False
    widths = [runs[0][1] - runs[0][0] for runs in scans]
    return (max(widths[0], widths[-1]) < min(widths[1:-1])
            and max(widths) < BEAM_MIN_THICKNESS_SPACES * space)


def _is_shallow_crescent(glyph: Glyph, space: float) -> bool:
    """REFUSE-10: a tie or slur crescent taller than ARC_MAX_HEIGHT_SPACES, because it is long.

    The shape is the arc's own (thin, tapering at both ends, mostly unpainted); only the height bound is
    relaxed to a rise that is a small part of the width, because a long arc rises more. The caller also
    accepts the glyph only where both of its ends are located on adjacent heads (a tie).
    """
    return (glyph.curved and glyph.filled and glyph.w >= ARC_MIN_WIDTH_SPACES * space
            and glyph.h > ARC_MAX_HEIGHT_SPACES * space and glyph.h <= ARC_MAX_RISE_RATIO * glyph.w
            and _fill_ratio(glyph) <= ARC_MAX_FILL_RATIO and _is_crescent_band(glyph, space))


def _is_wavy_line_outside_staff(glyph: Glyph, staff: Staff) -> bool:
    """REFUSE-10: a vibrato or trill line, a long thin zigzag drawn wholly above or below the five lines.

    Notation fixes its meaning (a held-note effect, no duration, pitch or string), so it is a located
    non-event even when it runs over noteheads. It is matched by its form alone: a filled outline made only
    of straight segments, thinner than any notehead, wide, with many direction reversals along its path.
    """
    space = staff.space
    if not (glyph.filled and not glyph.curved and (glyph.bbox[3] <= staff.top or glyph.bbox[1] >= staff.bottom)
            and glyph.w >= WAVY_LINE_MIN_WIDTH_SPACES * space
            and glyph.h < STROKE_FRAGMENT_MAX_THIN_SPACES * space):
        return False
    items = glyph.drawing.get("items", [])
    if not items or any(item[0] != "l" for item in items):
        return False
    ys: list[float] = []
    for item in items:
        for point in (item[1], item[2]):
            if not ys or abs(ys[-1] - point.y) > 1e-6:
                ys.append(point.y)
    steps = [b - a for a, b in zip(ys, ys[1:])]
    reversals = sum(1 for a, b in zip(steps, steps[1:]) if a * b < 0)
    return reversals >= WAVY_LINE_MIN_REVERSALS


def _shallow_crescent_ties(glyphs: list[Glyph], events: list[dict[str, Any]], space: float,
                           neighbours: list[tuple[float, float, float, float]]
                           ) -> list[tuple[dict, dict, Glyph]]:
    """REFUSE-10: shallow crescents that join two adjacent single-head notes at one staff position.

    A tie is fixed by notation: an arc leaving a note and ending on the very next note at the same staff
    position, standing clear above or below both heads, onto a note that prints no accidental. Both ends must
    be located by exactly one head each; anything else is not returned and keeps its earlier handling.
    """
    notes = [(e, e["_heads"][0]) for e in events if len(e.get("_heads", [])) == 1]
    result = []
    reach = TIE_END_REACH_SPACES * space
    for contour in glyphs:
        if not _is_shallow_crescent(contour, space):
            continue
        starts = [(e, h) for e, h in notes
                  if h.bbox[0] - 0.3 * space <= contour.bbox[0] <= h.bbox[2] + reach]
        stops = [(e, h) for e, h in notes
                 if h.bbox[0] - reach <= contour.bbox[2] <= h.bbox[2] + 0.3 * space]
        if len(starts) != 1 or len(stops) != 1:
            continue
        start, first = starts[0]
        stop, last = stops[0]
        following = min((e for e in events if e["_cx"] > start["_cx"]),
                        key=lambda e: e["_cx"], default=None)
        above = (contour.bbox[3] <= min(first.bbox[1], last.bbox[1])
                 and max(first.bbox[1], last.bbox[1]) - contour.bbox[3] <= reach)
        below = (contour.bbox[1] >= max(first.bbox[3], last.bbox[3])
                 and contour.bbox[1] - min(first.bbox[3], last.bbox[3]) <= reach)
        if (following is stop and abs(first.cy - last.cy) <= TIE_SAME_POSITION_SPACES * space
                and (above or below) and not _carries_accidental(last, neighbours, space)):
            result.append((start, stop, contour))
    return result


def _carries_accidental(head: Glyph, neighbours: list[tuple[float, float, float, float]], space: float) -> bool:
    """True when any other drawn mark or text box stands just left of the head, where an accidental is printed.

    A note that prints its own accidental is struck at a new pitch: an arc onto it is a hammer-on or pull-off
    over one staff position, never a tie (a tied note repeats the pitch and prints no accidental). Any mark
    there blocks the tie reading, which only ever keeps a bar refused.
    """
    return any(head.bbox[0] - b[2] <= ACCIDENTAL_REACH_SPACES * space and b[2] <= head.bbox[0] + 0.1 * space
               and b[1] <= head.bbox[3] and head.bbox[1] <= b[3] for b in neighbours)


def _arc_end_ys(glyph: Glyph) -> tuple[float, float] | None:
    """Vertical centre of the painted band at each end of a crescent, or None."""
    ends = []
    for f in (0.05, 0.95):
        runs = _runs(glyph.shape, True, glyph.bbox[0] + f * glyph.w, glyph.bbox[1] - 1, glyph.bbox[3] + 1)
        if len(runs) != 1:
            return None
        ends.append((runs[0][0] + runs[0][1]) / 2)
    return ends[0], ends[1]


def _vertical_gap(head: Glyph, y: float) -> float:
    """Distance from a height to the head's painted extent (zero when the height is within it)."""
    return max(head.bbox[1] - y, y - head.bbox[3], 0.0)


def _slanted_slur_ids(glyphs: list[Glyph], events: list[dict[str, Any]], space: float) -> set[str]:
    """Only uniquely owned slurs between two single-head stemmed notes, adjacent or not.

    Different staff positions establish a slur rather than a tie. Do not feed
    these contours into tie inference or infer a held chord member from them.
    Check ownership before the more expensive painted-contour scans.
    """
    notes = [(e, e["_heads"][0]) for e in events if len(e.get("_heads", [])) == 1
             and e.get("_stem") is not None and not e.get("_grace")]
    result: set[str] = set()
    reach = TIE_END_REACH_SPACES * space
    for glyph in glyphs:
        if not (glyph.curved and glyph.filled and glyph.w >= ARC_MIN_WIDTH_SPACES * space):
            continue
        starts = [(e, h) for e, h in notes
                  if h.bbox[0] - 0.3 * space <= glyph.bbox[0] <= h.bbox[2] + reach
                  and abs(h.cy - glyph.cy) <= TIE_VERTICAL_REACH_SPACES * space]
        stops = [(e, h) for e, h in notes
                 if h.bbox[0] - reach <= glyph.bbox[2] <= h.bbox[2] + 0.3 * space
                 and abs(h.cy - glyph.cy) <= TIE_VERTICAL_REACH_SPACES * space]
        if len(starts) != 1 or len(stops) != 1:
            # A slur over several notes has its box centre far from the lower
            # end head. Locate each head from the painted end of the arc.
            ends = _arc_end_ys(glyph)
            if ends is None:
                continue
            starts = [(e, h) for e, h in notes
                      if h.bbox[0] - 0.3 * space <= glyph.bbox[0] <= h.bbox[2] + reach
                      and abs(h.cy - ends[0]) <= TIE_VERTICAL_REACH_SPACES * space]
            stops = [(e, h) for e, h in notes
                     if h.bbox[0] - reach <= glyph.bbox[2] <= h.bbox[2] + 0.3 * space
                     and abs(h.cy - ends[1]) <= TIE_VERTICAL_REACH_SPACES * space]
            if len(starts) != 1 or len(stops) != 1:
                # REFUSE-10: the arc end stands clear of its head's centre by the head's own half height
                # as well as the gap: measure the distance to the head's painted extent instead.
                starts = [(e, h) for e, h in notes
                          if h.bbox[0] - 0.3 * space <= glyph.bbox[0] <= h.bbox[2] + reach
                          and _vertical_gap(h, ends[0]) <= TIE_VERTICAL_REACH_SPACES * space]
                stops = [(e, h) for e, h in notes
                         if h.bbox[0] - reach <= glyph.bbox[2] <= h.bbox[2] + 0.3 * space
                         and _vertical_gap(h, ends[1]) <= TIE_VERTICAL_REACH_SPACES * space]
                if len(starts) != 1 or len(stops) != 1:
                    continue
        start, first = starts[0]
        stop, last = stops[0]
        # A slur may span several notes (REFUSE-02): its ends are two different
        # staff positions, so it is never a tie, and it carries no duration.
        if (stop["_cx"] > start["_cx"] and abs(first.cy - last.cy) > TIE_SAME_POSITION_SPACES * space
                and _is_slanted_arc(glyph, space)):
            result.add(glyph.ident)
    return result


def _attach_heads(stem: Stem, heads: list[Glyph]) -> None:
    for head in heads:
        x0, y0, x1, y1 = head.bbox
        sx0, sy0, sx1, sy1 = stem.rect
        if sx1 < x0 or sx0 > x1 or sy1 < y0 or sy0 > y1:
            continue
        if _paints_into(head.shape, stem.rect):
            stem.heads.append(head)


def _beam_lines_at_stem(stem: Stem, beams: list[Glyph], space: float) -> list[dict[str, Any]] | str:
    """The distinct beam lines meeting this stem, from the tip inward, or an unread reason.

    A beam meets the stem where its painted band crosses the stem's painted extent. Bands from all
    beam drawings are merged, so the count is of visibly separate lines, not of drawings.
    """
    lo_x, hi_x = stem.x - stem.half_width, stem.x + stem.half_width
    tol = CURVE_FLATTENING_TOLERANCE_PT
    bands: list[list[Any]] = []
    for beam in beams:
        bx0, by0, bx1, by1 = beam.bbox
        if bx1 < lo_x - tol or bx0 > hi_x + tol or by1 < stem.y0 - tol or by0 > stem.y1 + tol:
            continue
        probe = min(max(stem.x, bx0 + tol), bx1 - tol)
        for a, b in _runs(beam.shape, True, probe, stem.y0 - 2 * space, stem.y1 + 2 * space):
            if b >= stem.y0 - tol and a <= stem.y1 + tol:
                bands.append([a, b, [beam.ident]])
    bands.sort(key=lambda band: band[0])
    merged: list[list[Any]] = []
    for a, b, ids in bands:
        if merged and a <= merged[-1][1] + tol:
            merged[-1][1] = max(merged[-1][1], b)
            merged[-1][2] = sorted(set(merged[-1][2]) | set(ids))
        else:
            merged.append([a, b, ids])
    if not merged:
        return []
    if any(b - a > BEAM_MAX_THICKNESS_SPACES * space for a, b, _ in merged):
        return "beam_lines_not_separable"
    # Order from the tip inward; the outermost line holds the tip, the rest follow it closely.
    merged.sort(key=lambda band: abs((band[0] + band[1]) / 2 - stem.tip))
    first = merged[0]
    if not (first[0] - space * 0.05 <= stem.tip <= first[1] + space * 0.05):
        return "stem_crossing_not_at_tip"
    for previous, current in zip(merged, merged[1:]):
        gap = max(current[0] - previous[1], previous[0] - current[1])
        if gap > BEAM_MAX_GAP_SPACES * space:
            return "stem_crossing_not_at_tip"
    return [{"band": (a, b), "sources": ids} for a, b, ids in merged]


# REFUSE-09: scans stay in the stretch where a flag runs outward from its stem. A single stem-up flag curls back
# under its own blade from about 0.55 of its reach (measured on the corpus: one run to 0.5, two from 0.55), so a
# scan at 0.6 crossed it twice and the glyph was left unidentified; two-blade flags keep two runs from 0.15 to 0.8.
GRACE_READABLE_FLAG_HOOKS = (1, 2)  # REFUSE-09: a grace carries no metrical duration; one or two drawn blades both fix an eighth or 16th grace
FLAG_SCAN_FRACTIONS = (0.3, 0.4, 0.5)


def _flag_hooks(glyph: Glyph, stem: Stem, space: float) -> int:
    """Hooks in one flag glyph: blades crossed by vertical scans through its middle.

    A combined sixteenth-note flag is one glyph with two blades; each blade crosses a scan line
    through the flag's middle once. Scans at three positions (FLAG_SCAN_FRACTIONS) must agree, else the glyph is not
    identified (0).
    """
    reach = glyph.bbox[2] - stem.x
    counts = [len(_runs(glyph.shape, True, stem.x + f * reach, glyph.bbox[1] - 1, glyph.bbox[3] + 1))
              for f in FLAG_SCAN_FRACTIONS]
    return counts[0] if len(set(counts)) == 1 and 1 <= counts[0] <= 4 else 0


def _flags_at_stem(stem: Stem, candidates: list[Glyph], space: float) -> list[Glyph]:
    """Flag glyphs painted onto the stem, starting at its tip.

    The first holds the tip; further flag glyphs (flags drawn one per drawing) follow it inward,
    each touching the stem and overlapping or adjoining the flags already found.
    """
    tol = CURVE_FLATTENING_TOLERANCE_PT
    attached = []
    for glyph in candidates:
        x0, y0, x1, y1 = glyph.bbox
        if glyph.h < FLAG_MIN_HEIGHT_SPACES * space or x1 < stem.x + FLAG_MIN_REACH_SPACES * space:
            continue
        if x0 > stem.x + stem.half_width + tol or y1 < stem.y0 - tol or y0 > stem.y1 + tol:
            continue
        if _paints_into(glyph.shape, stem.rect):
            attached.append(glyph)
    found = [g for g in attached if g.bbox[1] - tol <= stem.tip <= g.bbox[3] + tol]
    if not found:
        return []
    grew = True
    while grew:
        grew = False
        lo, hi = min(g.bbox[1] for g in found), max(g.bbox[3] for g in found)
        for glyph in attached:
            if glyph not in found and glyph.bbox[1] <= hi + BEAM_MAX_GAP_SPACES * space and glyph.bbox[3] >= lo - BEAM_MAX_GAP_SPACES * space:
                found.append(glyph)
                grew = True
    return found


def _dot_fits(dot: Glyph, anchor: tuple[float, float, float, float], edge: float, row: list[Glyph],
              space: float, rest: bool) -> bool:
    """Whether ``dot`` stands where the next augmentation dot of this anchor would stand."""
    x0, y0, x1, y1 = anchor
    cy = (y0 + y1) / 2
    reach = DOT_FIRST_GAP_SPACES if not row else DOT_NEXT_GAP_SPACES
    if dot.bbox[0] < edge - 0.1 * space or dot.bbox[0] - edge > reach * space:
        return False
    if rest:
        return y0 - 0.5 * space <= dot.cy <= y1 + 0.5 * space
    if row:
        return abs(dot.cy - row[-1].cy) <= 0.1 * space
    return abs(dot.cy - cy) <= DOT_HEIGHT_TOLERANCE_SPACES * space


def _augmentation_dots(anchors: list[tuple[float, float, float, float]], dots: list[Glyph], claimed: set[str],
                       space: float, rest: bool = False) -> list[list[Glyph]]:
    """The row of dots to the right of each notehead of the event (or of its rest).

    Each dot adds half the previous value. A chord's noteheads are dotted together, so the count is
    the length of a row, not the number of dot glyphs.
    """
    rows: list[list[Glyph]] = []
    for anchor in anchors:
        row: list[Glyph] = []
        edge = anchor[2]
        while True:
            options = [dot for dot in dots
                       if dot.ident not in claimed and dot not in row and _dot_fits(dot, anchor, edge, row, space, rest)]
            if not options:
                break
            nearest = min(options, key=lambda d: d.bbox[0])
            row.append(nearest)
            edge = nearest.bbox[2]
        if row:
            rows.append(row)
    return rows


def _ambiguous_point_dots(events: list[dict[str, Any]], space: float) -> set[str]:
    """Stroked-point dots that more than one event's first dot position accepts.

    A point dot is read only where position and size attach it to exactly one note or rest. One that
    could belong to two events is left unread (never guessed, never taken from the bar total).
    """
    claimants: dict[str, set[int]] = {}
    point_dots = {d.ident: d for event in events for row in event.get("_dots", []) for d in row
                  if d.drawing.get("source_form") == POINT_DOT_FORM}
    if not point_dots:
        return set()
    for index, event in enumerate(events):
        rest = "_rest" in event
        for head in [h.bbox for h in event.get("_heads", [])] or [event["_rest"].bbox]:
            for dot in point_dots.values():
                if _dot_fits(dot, head, head[2], [], space, rest):
                    claimants.setdefault(dot.ident, set()).add(index)
    return {ident for ident, owners in claimants.items() if len(owners) > 1}


# --- rests ----------------------------------------------------------------------------------

def _rows(glyph: Glyph, space: float) -> list[tuple[float, list[tuple[float, float]]]]:
    """Painted runs on horizontal scans every REST_ROW_STEP_SPACES down the glyph."""
    steps = max(SCAN_SAMPLES, int(glyph.h / (REST_ROW_STEP_SPACES * space)))
    out = []
    for k in range(steps):
        y = glyph.bbox[1] + (k + 0.5) * glyph.h / steps
        out.append((y, _runs(glyph.shape, False, y, glyph.bbox[0] - 1, glyph.bbox[2] + 1)))
    return out


def _stem_top(rows: list[tuple[float, list[tuple[float, float]]]]) -> int | None:
    """Index of the scan where the glyph's right edge is furthest right: a hooked rest's stem top.

    The first hook's ball may rise above the stem, so rows above this one have no stem in them.
    """
    edges = [(runs[-1][1], k) for k, (_, runs) in enumerate(rows) if runs]
    if not edges:
        return None
    best = max(edge for edge, _ in edges)
    return min(k for edge, k in edges if edge == best)


def _right_edge_reversals(rows: list[tuple[float, list[tuple[float, float]]]], space: float,
                          start: int = 0) -> tuple[int, float]:
    """Direction changes of the glyph's right edge down its height from ``start``, and its net drop.

    A zigzag stroke (a quarter rest) reverses; a hooked rest's slanted stem keeps descending to the
    left. Changes smaller than REST_EDGE_HYSTERESIS_SPACES are ignored.
    """
    edges = [runs[-1][1] for _, runs in rows[start:] if runs]
    if len(edges) < 2:
        return 0, 0.0
    reversals, direction, anchor = 0, 0, edges[0]
    for x in edges[1:]:
        delta = x - anchor
        if abs(delta) < REST_EDGE_HYSTERESIS_SPACES * space:
            continue
        step = 1 if delta > 0 else -1
        if direction and step != direction:
            reversals += 1
        direction, anchor = step, x
    return reversals, edges[0] - edges[-1]


def _hooks_beside_stem(rows: list[tuple[float, list[tuple[float, float]]]], space: float, start: int = 0) -> int:
    """Hooks of a hooked rest: the separate painted pieces left of its stem.

    The stem is the band just inside the right edge from its top (``start``) down, as thick as the
    stem where it stands alone. With the stem removed, each hook (its ball and arm) is one piece;
    pieces are joined across successive scans where their runs overlap.
    """
    alone = [runs[-1][1] - runs[-1][0] for _, runs in rows[start:] if len(runs) == 1]
    if not alone:
        return 0
    stem = min(alone) + REST_STEM_MARGIN_SPACES * space
    pieces: list[dict[str, Any]] = []
    previous: list[tuple[tuple[float, float], dict[str, Any]]] = []
    for k, (y, runs) in enumerate(rows):
        cut = runs[-1][1] - stem if runs and k >= start else math.inf
        current = []
        for a, b in runs:
            b = min(b, cut)
            if b - a < REST_HOOK_MIN_WIDTH_SPACES * space:
                continue
            joined = [piece for (pa, pb), piece in previous if a <= pb and pa <= b]
            roots = []
            for piece in joined:
                while piece.get("merged"):
                    piece = piece["merged"]
                if piece not in roots:
                    roots.append(piece)
            if roots:
                piece = roots[0]
                for other in roots[1:]:
                    other["merged"] = piece
                    piece["y0"] = min(piece["y0"], other["y0"])
            else:
                piece = {"y0": y}
                pieces.append(piece)
            piece["y1"] = y
            current.append(((a, b), piece))
        previous = current
    roots = [p for p in pieces if not p.get("merged")]
    return sum(1 for p in roots if p["y1"] - p["y0"] >= REST_HOOK_MIN_HEIGHT_SPACES * space)


def _rest_glyph(glyph: Glyph, staff: Staff) -> str | None:
    """The rest value this glyph's form identifies, "unidentified" for a rest-sized unknown, or None."""
    s = staff.space
    w, h = glyph.w / s, glyph.h / s
    if not glyph.filled:
        return None
    b = REST_BLOCK
    if b["min_w"] <= w <= b["max_w"] and b["min_h"] <= h <= b["max_h"]:
        if set(_row_counts(glyph)) == {1} and set(_column_counts(glyph, (0.2, 0.5, 0.8))) == {1}:
            hangs = any(abs(glyph.bbox[1] - y) <= b["line"] * s for y in staff.lines)
            sits = any(abs(glyph.bbox[3] - y) <= b["line"] * s for y in staff.lines)
            if hangs != sits:
                return "whole" if hangs else "half"
            return "unidentified"
    r = REST_WINDOW
    if not (r["min_w"] <= w <= r["max_w"] and r["min_h"] <= h <= r["max_h"]):
        return None
    rows = _rows(glyph, s)
    top = _stem_top(rows)
    lo, hi = REST_STEM_SLANT
    if top is not None and top <= REST_STEM_TOP_SHARE * len(rows):
        reversals, drop = _right_edge_reversals(rows, s, top)
        stem_height = rows[-1][0] - rows[top][0]
        if reversals == 0 and stem_height > 0 and lo * stem_height <= drop <= hi * stem_height:
            hooks = _hooks_beside_stem(rows, s, top)
            if 1 <= hooks <= 4:
                return FLAGGED_VALUES[hooks]
            return "unidentified"
    reversals, _ = _right_edge_reversals(rows, s)
    q = REST_QUARTER
    if q["min_w"] <= w <= q["max_w"] and q["min_h"] <= h <= q["max_h"] and reversals >= 2:
        counts = _row_counts(glyph)
        if counts.count(1) >= QUARTER_REST_SINGLE_RUN_SHARE * len(counts) and _column_counts(glyph, (0.5,))[0] >= 2:
            return "quarter"
    return "unidentified"


def _rest_form_outranks_accidental_position(beside: str | None, kind: str | None) -> bool:
    """REFUSE-08: a glyph whose own form fixes a rest value (slanted stem and hook count, a block on a line,
    a quarter-rest zigzag) is a rest even where an accidental would stand, just left of a notehead. Only
    that position is released: a rest over, under or touching a head or stem stays a located overlap.
    The value comes from the shape alone, never from spacing or the bar total."""
    return beside == "accidental_beside_notehead" and kind in WRITTEN_VALUES


def _is_thick_barline(glyph: Glyph, staff: Staff) -> bool:
    """The thick line of a final or repeat barline: a solid upright band from the top staff line to
    the bottom one. No rest has that form."""
    s = staff.space
    tol = BARLINE_END_TOLERANCE_SPACES * s
    if not glyph.filled or glyph.curved or glyph.w > BARLINE_MAX_WIDTH_SPACES * s:
        return False
    if abs(glyph.bbox[1] - staff.top) > tol or abs(glyph.bbox[3] - staff.bottom) > tol:
        return False
    return (set(_row_counts(glyph)) == {1} and set(_column_counts(glyph, (0.2, 0.5, 0.8))) == {1}
            and _fill_ratio(glyph) >= THICK_BARLINE_MIN_FILL_RATIO)


# --- tuplets and time signatures ------------------------------------------------------------

def _tuplet_ratio(text: str) -> tuple[int, int] | None:
    match = DIGITS.match(text)
    if not match:
        return None
    actual = int(match.group(1))
    if match.group(2):
        return actual, int(match.group(2))
    if actual < 3 or actual & (actual - 1) == 0:
        return None  # 2 or 4 in the time of 3 (compound time) is not stated by the number alone
    return actual, 2 ** int(math.log2(actual))


def _run_under_number(digit: Text, members: list[dict[str, Any]], count: int, space: float) -> list[dict[str, Any]] | None:
    """The `count` consecutive events a bare tuplet number stands over, inside a longer beam group.

    A printed number states how many notes it spans, so over a beam group of another size (and not a whole
    multiple of it, which stays read as before) it cannot span the whole group. The run is the one whose
    first and last notes enclose the number and whose centre is nearest to it; if a second run is nearly as
    good, the number is not placed. The bar total is never consulted.
    """
    ordered = sorted(members, key=lambda e: e["_cx"])
    runs = [ordered[i:i + count] for i in range(len(ordered) - count + 1)]
    scored = sorted((abs(digit.cx - (r[0]["_cx"] + r[-1]["_cx"]) / 2), i) for i, r in enumerate(runs)
                    if r[0]["_cx"] <= digit.cx <= r[-1]["_cx"])
    if not scored:
        return None
    if len(scored) > 1 and scored[1][0] - scored[0][0] < TUPLET_RUN_MARGIN_SPACES * space:
        return None
    return runs[scored[0][1]]


def _read_tuplets(digits: list[Text], polylines: list[Polyline], groups: list[dict[str, Any]],
                  events: list[dict[str, Any]], space: float) -> tuple[list[dict[str, Any]], list[Text]]:
    """Tuplets spanned by a bracket around a number, or by a number over one beam group.

    Returns the tuplets (with the events they scale) and the numbers that could not be associated.
    """
    tuplets, unassociated = [], []
    reach = TUPLET_BRACKET_REACH_SPACES * space
    for digit in digits:
        ratio = _tuplet_ratio(digit.text)
        near = [p for p in polylines if p.bbox[1] - space <= digit.cy <= p.bbox[3] + space]
        left = [p for p in near if digit.bbox[0] - reach <= p.bbox[2] <= digit.bbox[0] + 0.3 * space]
        right = [p for p in near if digit.bbox[2] - 0.3 * space <= p.bbox[0] <= digit.bbox[2] + reach]
        members: list[dict[str, Any]] = []
        sources = [digit.ident]
        if len(left) == 1 and len(right) == 1:
            x0, x1 = left[0].bbox[0], right[0].bbox[2]
            pad = TUPLET_BRACKET_OVERLAP_SPACES * space
            members = [e for e in events if x0 - pad <= e["_cx"] <= x1 + pad]
            sources += [left[0].ident, right[0].ident]
        elif not left and not right:
            under = [g for g in groups if g["x0"] <= digit.cx <= g["x1"]
                     and min(abs(digit.cy - y) for y in g["beam_ys"]) <= TUPLET_NUMBER_BEAM_REACH_SPACES * space]
            if len(under) == 1:
                members = [e for e in events if e.get("_beam_group") == under[0]["id"]]
                if ratio and len(members) > ratio[0] and len(members) % ratio[0]:
                    members = _run_under_number(digit, members, ratio[0], space) or []
                sources += under[0]["sources"]
        if members and ratio:
            tuplets.append({"actual": ratio[0], "normal": ratio[1], "members": members, "sources": sources,
                            "ratio_source": "stated" if ":" in digit.text else "tuplet_number_convention"})
        else:
            unassociated.append(digit)
    return tuplets, unassociated


def _read_time_signature(texts: list[Text], staff: Staff, header_end: float) -> dict[str, Any] | None:
    """A time signature printed as two stacked text numbers at the start of the staff."""
    s = staff.space
    mid = staff.lines[2]
    numbers = [t for t in texts if DIGITS.match(t.text) and ":" not in t.text and t.cx <= header_end
               and staff.top - s <= t.cy <= staff.bottom + s]
    for top in numbers:
        if not staff.top - s <= top.cy <= mid:
            continue
        for bottom in numbers:
            if bottom is top or not mid <= bottom.cy <= staff.bottom + s or abs(top.cx - bottom.cx) > 0.6 * s:
                continue
            return {"numerator": int(top.text), "denominator": int(bottom.text), "sources": [top.ident, bottom.ident],
                    "x1": max(top.bbox[2], bottom.bbox[2])}
    return None


# --- value composition ----------------------------------------------------------------------

def _written_value(parts: dict[str, Any]) -> tuple[str | None, str | None]:
    """The written value named by the symbols, or (None, reason). Never a default."""
    if parts["kind"] == "rest":
        glyph = parts["rest_glyph"]
        return (glyph, None) if glyph in WRITTEN_VALUES else (None, "rest_glyph_unidentified")
    head, stem = parts["head_kind"], parts["has_stem"]
    flags, beams = parts["flag_hooks"], parts["beam_count"]
    if head == "hollow":
        if flags or beams:
            return None, "hollow_notehead_with_flag_or_beam"
        return ("half", None) if stem else ("whole", None)
    if not stem:
        return None, "filled_notehead_without_stem"
    if flags and beams:
        return None, "flag_and_beam_on_one_stem"
    steps = beams or flags
    if steps >= len(FLAGGED_VALUES):
        return None, "more_than_four_flags_or_beams"
    return FLAGGED_VALUES[steps], None


def _frac(value: Fraction | None) -> str | None:
    if value is None:
        return None
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _bbox_union(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


# --- reading one staff ----------------------------------------------------------------------

class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, a: str) -> str:
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a: str, b: str) -> None:
        self.parent[self.find(a)] = self.find(b)


def _zone(staff: Staff, all_staves: list[Staff]) -> tuple[float, float]:
    s = staff.space
    upper, lower = staff.top - ZONE_REACH_SPACES * s, staff.bottom + ZONE_REACH_SPACES * s
    for other in all_staves:
        if other is staff:
            continue
        if other.bottom < staff.top:
            upper = max(upper, other.bottom + 0.5 * s)
        elif other.top > staff.bottom:
            lower = min(lower, other.top - 0.5 * s)
    return upper, lower


def _tab_text_rows(staff: Staff, symbols: PageSymbols) -> list[tuple[float, float, float, float, float]]:
    """Six broad, equally spaced horizontal rows below a notation staff.

    This uses the union of line fragments at each height. Fret gaps can split
    the fragments beyond the stricter endpoint matching in ``find_staves``.
    A row is evidence only when all six lines cover most of the notation
    staff's horizontal extent; short beams and ledger lines cannot qualify.
    """
    rows: list[dict[str, Any]] = []
    for seg in sorted((s for s in symbols.segments if s.horizontal and s.y0 > staff.bottom + 0.5 * staff.space),
                      key=lambda s: s.y0):
        y = (seg.y0 + seg.y1) / 2
        if rows and abs(rows[-1]["y"] - y) <= 0.01 * staff.space:
            row = rows[-1]
            row["x0"] = min(row["x0"], seg.x0)
            row["x1"] = max(row["x1"], seg.x1)
            row["pieces"].append((seg.x0, seg.x1))
        else:
            rows.append({"y": y, "x0": seg.x0, "x1": seg.x1, "pieces": [(seg.x0, seg.x1)]})
    width = staff.x1 - staff.x0
    broad = [r for r in rows if r["x1"] - r["x0"] >= 0.8 * width
             and abs(r["x0"] - staff.x0) <= staff.space
             and abs(r["x1"] - staff.x1) <= staff.space
             and _coverage(r["pieces"]) >= STAFF_LINE_MIN_COVERAGE * (r["x1"] - r["x0"])]
    found = []
    for start in range(len(broad) - 5):
        run = broad[start:start + 6]
        steps = [b["y"] - a["y"] for a, b in zip(run, run[1:])]
        step = statistics.median(steps)
        if step <= 0 or any(abs(gap - step) > STAFF_GAP_TOLERANCE * step + 0.01 * staff.space for gap in steps):
            continue
        found.append((run[0]["y"], run[-1]["y"], min(r["x0"] for r in run),
                      max(r["x1"] for r in run), step))
    return found


def _on_tab_text_row(text: Text, rows: list[tuple[float, float, float, float, float]]) -> bool:
    """A digit centred on or between six TAB lines belongs to that row."""
    return any(x0 <= text.cx <= x1 and top - 0.1 * step <= text.cy <= bottom + 0.1 * step
               for top, bottom, x0, x1, step in rows)


def _barlines(staff: Staff, symbols: PageSymbols) -> list[tuple[float, float]]:
    """Bar boundaries (left edge, right edge) along the staff, double barlines merged."""
    s = staff.space
    tol = BARLINE_END_TOLERANCE_SPACES * s
    xs = []
    for seg in symbols.segments:
        if not seg.vertical or seg.width > BARLINE_MAX_WIDTH_SPACES * s:
            continue
        x = (seg.x0 + seg.x1) / 2
        y0, y1 = min(seg.y0, seg.y1), max(seg.y0, seg.y1)
        if not (staff.x0 - 1.0 <= x <= staff.x1 + 1.0) or y0 > staff.top + tol or y1 < staff.bottom - tol:
            continue
        extent = (x - seg.width / 2, x + seg.width / 2)
        if _has_attached_notehead(extent, y0, y1, symbols.head_shapes, s):
            continue  # a stem
        xs.append(extent)
    xs.sort()
    clusters: list[list[float]] = []
    for a, b in xs:
        if clusters and a - clusters[-1][1] <= BARLINE_CLUSTER_SPACES * s:
            clusters[-1][1] = max(clusters[-1][1], b)
        else:
            clusters.append([a, b])
    return [(a, b) for a, b in clusters if a - staff.x0 > BARLINE_CLUSTER_SPACES * s]


def _is_start_repeat_after_header(staff: Staff, glyphs: list[Glyph], texts: list[Text],
                                  cluster: tuple[float, float]) -> bool:
    """REFUSE-17: the first barline cluster of a system is a start-repeat barline that follows only the header.

    A start-repeat sign (thick band, thin line, two dots on the right) printed straight after the clef and
    meter opens the first bar; it does not close a bar. Read as a boundary it would leave a bar made of the
    header alone. The sign is recognised from its own printed form: a thick barline band just left of the
    cluster, two small filled discs just right of it, and before it only an unbroken run of header symbols
    (clef, key, meter) from the staff start. A blank bar before a repeat sign leaves a gap and is not matched.
    """
    s = staff.space
    a, b = cluster
    thick = [g for g in glyphs if _is_thick_barline(g, staff) and g.bbox[2] <= a + 0.1 * s
             and a - g.bbox[2] <= BARLINE_CLUSTER_SPACES * s]
    if len(thick) != 1:
        return False
    run_end = staff.x0
    members = [m.bbox for m in glyphs if m.bbox[2] <= thick[0].bbox[0]] + [
        t.bbox for t in texts if t.bbox[2] <= thick[0].bbox[0] and staff.top - s <= t.cy <= staff.bottom + s]
    for x0, _, x1, _ in sorted(members):
        if x0 > staff.x0 + HEADER_CLEF_START_SPACES * s and x0 > run_end + HEADER_CONTIGUITY_SPACES * s:
            return False
        run_end = max(run_end, x1)
    if thick[0].bbox[0] > run_end + HEADER_CONTIGUITY_SPACES * s:
        return False
    dots = [g for g in glyphs if g.filled and g.w <= REPEAT_DOT_MAX_SPACES * s and g.h <= REPEAT_DOT_MAX_SPACES * s
            and b - 0.1 * s <= g.bbox[0] <= b + REPEAT_DOT_REACH_SPACES * s
            and staff.top < g.cy < staff.bottom]
    return len(dots) == 2 and abs(dots[0].cy - dots[1].cy) > 0.5 * s


def _covers_staff(glyph: Glyph, staff: Staff) -> bool:
    """A filled shape whose box encloses the whole staff (a page background or frame) is not a printed symbol.

    No notation glyph spans a staff from its first line to its last and from its left end to its right end;
    left in, such a shape sorts first in the header scan and makes the whole staff "header", hiding every
    rest on it.
    """
    return (glyph.bbox[0] <= staff.x0 and glyph.bbox[2] >= staff.x1
            and glyph.bbox[1] <= staff.top and glyph.bbox[3] >= staff.bottom)


def _read_staff(staff: Staff, symbols: PageSymbols, all_staves: list[Staff], state: dict[str, Any]) -> dict[str, Any]:
    s = staff.space
    upper, lower = _zone(staff, all_staves)

    def in_zone(x: float, y: float) -> bool:
        return upper <= y <= lower and staff.x0 - 1.0 <= x <= staff.x1 + 1.0

    glyphs = [g for g in symbols.glyphs if in_zone(g.cx, g.cy) and not _covers_staff(g, staff)]
    base_equivalent = state.get("base_equivalent", False)
    dead_heads = [] if base_equivalent else [g for g in glyphs if _is_dead_note_x_head(g, s)]
    dead_ids = {g.ident for g in dead_heads}
    heads: list[Glyph] = []
    head_kind: dict[str, str] = {}
    for g in glyphs:
        kind = "cross" if g.ident in dead_ids else _is_notehead(g, s)
        if kind:
            heads.append(g)
            head_kind[g.ident] = kind
    head_ids = set(head_kind)
    chord_pair_heads: set[str] = set()
    parentheses = {} if base_equivalent else _notehead_parentheses(
        glyphs, heads, s, chord_pair_heads if state.get("chord_pairs", True) else None)
    parenthesis_ids = {g.ident for pair in parentheses.values() for g in pair}
    small_ids = {h.ident for h in heads if _is_small_head(h, s)}
    non_events: list[dict[str, Any]] = []
    dots = [g for g in glyphs if g.ident not in head_ids and _is_dot(g, s)]
    dot_ids = {d.ident for d in dots}
    beams = [g for g in glyphs if g.ident not in head_ids and g.ident not in dot_ids and _is_beam(g, s)]
    beam_ids = {b.ident for b in beams}

    # Keep every band touching a dead-head stem out of other notes' beam groups.
    # The cross owns its stem even though this task cannot write its TAB event.
    dead_stems = []
    for seg in symbols.segments:
        if not seg.vertical or seg.width > STEM_MAX_WIDTH_SPACES * s:
            continue
        x = (seg.x0 + seg.x1) / 2
        y0, y1 = sorted((seg.y0, seg.y1))
        if y1 - y0 < STEM_MIN_LENGTH_SPACES * s or not in_zone(x, (y0 + y1) / 2):
            continue
        stem = Stem(seg.ident, x, y0, y1, seg.width / 2)
        _attach_heads(stem, dead_heads)
        if any(h.bbox[1] <= y0 <= h.bbox[3] or h.bbox[1] <= y1 <= h.bbox[3]
               for h in stem.heads):
            dead_stems.append(stem)
    dead_beam_ids = {beam.ident for beam in beams for stem in dead_stems
                     if _paints_into(beam.shape, stem.rect)}
    # A band is owned through painted head/stem contact and the duration gate,
    # including when it joins numeric heads and crosses. Shape alone is never
    # sufficient; _beam_lines_at_stem still checks each stem's attachment.

    # Stems: verticals in painted contact with a notehead at one of their ends.
    boundaries = _barlines(staff, symbols)
    stems: list[Stem] = []
    for seg in symbols.segments:
        if not seg.vertical or seg.width > STEM_MAX_WIDTH_SPACES * s:
            continue
        x = (seg.x0 + seg.x1) / 2
        y0, y1 = min(seg.y0, seg.y1), max(seg.y0, seg.y1)
        if y1 - y0 < STEM_MIN_LENGTH_SPACES * s or not in_zone(x, (y0 + y1) / 2):
            continue
        stem = Stem(seg.ident, x, y0, y1, seg.width / 2)
        _attach_heads(stem, heads)
        at_top = [h for h in stem.heads if h.bbox[1] <= y0 <= h.bbox[3]]
        at_bottom = [h for h in stem.heads if h.bbox[1] <= y1 <= h.bbox[3]]
        if not at_top and not at_bottom:
            continue
        stem.up = bool(at_bottom) and not at_top
        stems.append(stem)
    stem_of: dict[str, list[Stem]] = {}
    for stem in stems:
        for head in stem.heads:
            stem_of.setdefault(head.ident, []).append(stem)

    used = dead_ids | head_ids | dot_ids | beam_ids
    flag_candidates = [g for g in glyphs if g.ident not in used and g.filled]
    arcs = [g for g in glyphs if g.ident not in used and _is_arc(g, s)]
    arc_ids = {a.ident for a in arcs}

    # Beam groups: stems joined by a shared beam drawing.
    parts_by_stem: dict[str, dict[str, Any]] = {}
    groups = _UnionFind()
    for stem in stems:
        lines = _beam_lines_at_stem(stem, beams, s)
        flags = [f for f in _flags_at_stem(stem, flag_candidates, s) if f.ident not in arc_ids]
        parts_by_stem[stem.ident] = {"lines": lines, "flags": flags}
        if isinstance(lines, list):
            for line in lines:
                for ident in line["sources"]:
                    groups.union(stem.ident, "beam:" + ident)
    group_members: dict[str, list[Stem]] = {}
    for stem in stems:
        lines = parts_by_stem[stem.ident]["lines"]
        if isinstance(lines, list) and lines:
            group_members.setdefault(groups.find(stem.ident), []).append(stem)
    group_ids = {root: f"s{state['system_number']}g{i}" for i, root in enumerate(
        sorted(group_members, key=lambda r: min(m.x for m in group_members[r])))}
    flag_ids = {f.ident for p in parts_by_stem.values() for f in p["flags"]}
    # A beam-shaped band that meets no stem is not a beam (a whole or half rest is such a band).
    attached_beam_ids = {ident for p in parts_by_stem.values() if isinstance(p["lines"], list)
                         for line in p["lines"] for ident in line["sources"]}

    # Events: a stem with its noteheads; stemless noteheads grouped by horizontal overlap; rests.
    events: list[dict[str, Any]] = []
    for stem in stems:
        chord = sorted(stem.heads, key=lambda h: h.cy)
        event = {"_heads": chord, "_stem": stem, "_cx": sum(h.cx for h in chord) / len(chord)}
        small = [h.ident in small_ids for h in chord]
        if all(small):
            event["_grace"] = True  # a small head on a stem: a grace note when its flag is read
        elif any(small):
            event["_unread"] = "small_notehead_mixed_with_full_size"
        events.append(event)
    loose = sorted((h for h in heads if h.ident not in stem_of), key=lambda h: h.bbox[0])
    for head in loose:
        if head.ident in small_ids:
            if head_kind[head.ident] == "filled":
                # A small filled head with no stem has no beat of its own: it is recorded and left out.
                non_events.append({"reason": "small_notehead_without_stem", "glyph": head, "cx": head.cx,
                                   "width_spaces": head.w / s, "height_spaces": head.h / s})
            else:
                events.append({"_heads": [head], "_stem": None, "_cx": head.cx, "_unread": "small_notehead_unclassified",
                               "_loose_small": True})
            continue
        for event in events:
            if event["_stem"] is None and "_loose_small" not in event and any(h.bbox[0] <= head.bbox[2] and head.bbox[0] <= h.bbox[2] for h in event["_heads"]):
                event["_heads"].append(head)
                break
        else:
            events.append({"_heads": [head], "_stem": None, "_cx": head.cx})
    for event in events:
        if event["_stem"] is None:
            event["_cx"] = sum(h.cx for h in event["_heads"]) / len(event["_heads"])
    for event in events:
        unsupported = list({g.ident: g for head in event.get("_heads", [])
                            for g in parentheses.get(head.ident, [])}.values())
        if unsupported and all(head.ident in parentheses for head in event["_heads"]):
            # REFUSE-14: every head of the event is enclosed by its own printed parenthesis pair, which
            # is the notation for a ghost note: the whole event is ghosted (no head is picked by inference).
            event["_ghost"] = unsupported
            # REFUSE-18: remember a ghost that only a tall chord pair supplies, so a bar the reader
            # already wrote without it keeps its notes (the assembler decides, as for REFUSE-14).
            event["_ghost_chord_pair"] = any(head.ident in chord_pair_heads for head in event["_heads"])
        if unsupported:
            event["_unread_symbols"] = unsupported
    # Located-only symbols are recorded with their class but never enter the event
    # stream: a refused bar keeps the bar-level reason it had before they were seen.
    located_events = []

    # The system header (clef, key and time signature) is the run of symbols from the staff start.
    first_note_x = min((h.bbox[0] for h in heads), default=staff.x1)
    header_end = staff.x0
    for g in sorted(glyphs, key=lambda g: g.bbox[0]):
        if g.ident in head_ids or g.bbox[0] >= first_note_x:
            break
        if g.bbox[0] <= staff.x0 + HEADER_CLEF_START_SPACES * s or g.bbox[0] <= header_end + HEADER_CONTIGUITY_SPACES * s:
            header_end = max(header_end, g.bbox[2])
        else:
            break
    digit_texts = [t for t in symbols.texts if DIGITS.match(t.text) and in_zone(t.cx, t.cy)]
    time_signature = _read_time_signature(digit_texts, staff, first_note_x)
    if time_signature:
        header_end = max(header_end, time_signature["x1"])
        state["time_signature"] = {"value": (time_signature["numerator"], time_signature["denominator"]),
                                   "source": "text_glyphs", "sources": time_signature["sources"]}
        digit_texts = [t for t in digit_texts if t.ident not in time_signature["sources"]]

    slur_ids = _slanted_slur_ids(
        [g for g in glyphs if g.ident not in used | flag_ids | arc_ids | parenthesis_ids], events, s)
    arc_ids |= slur_ids
    state["diagnostics"]["arcs_not_ties"] += len(slur_ids)
    crescent_ties = _shallow_crescent_ties(
        [g for g in glyphs if g.ident not in used | flag_ids | arc_ids | parenthesis_ids],
        [e for e in events if not e.get("_grace")], s,
        [g.bbox for g in glyphs if g.ident not in head_ids and not _is_shallow_crescent(g, s)]
        + [t.bbox for t in symbols.texts if t.text in ACCIDENTAL_TEXT and in_zone(t.cx, t.cy)])
    crescent_tie_ids = {contour.ident for _start, _stop, contour in crescent_ties}
    arc_ids |= crescent_tie_ids

    # Every other glyph after the header is a rest, a located unread event, or a symbol classified
    # (and counted) as something else. Nothing that could be a rest is dropped silently.
    ignored: dict[str, int] = {}
    overlaps: list[dict[str, Any]] = []
    wave_ids = _wave_column_ids(symbols.glyphs, s)  # the column runs past this staff's zone
    head_boxes = [h.bbox for h in heads]
    accidental_marks: list[tuple[tuple[float, float, float, float], str, str, float]] = []
    for t in symbols.texts:
        direction = ACCIDENTAL_TEXT.get(t.text)
        if direction and in_zone(t.cx, t.cy):
            accidental_marks.append((t.bbox, direction, t.ident, t.bbox[3]))  # text boxes rise above the pitch
    for g in glyphs:
        if g.ident in parenthesis_ids | dead_ids | head_ids | dot_ids | attached_beam_ids | flag_ids | arc_ids or g.bbox[2] <= header_end:
            continue
        if g.ident in dead_beam_ids:
            located_events.append({"_rest": g, "_rest_kind": None, "_cx": g.cx, "_kind": "unclassified",
                                   "_dots": [], "_unread": "beam_attached_to_dead_note_x_head"})
            continue
        # Rests stand within reach of the staff; beyond it are tempo marks, text symbols and the like.
        if not (staff.top - REST_VERTICAL_REACH_SPACES * s <= g.bbox[1] and g.bbox[3] <= staff.bottom + REST_VERTICAL_REACH_SPACES * s):
            ignored["outside_rest_reach"] = ignored.get("outside_rest_reach", 0) + 1
            # A note on a ledger line has its accidental out of the rests' reach: still a printed accidental.
            if any(b[0] - g.bbox[2] <= ACCIDENTAL_REACH_SPACES * s and g.bbox[2] <= b[0] + 0.1 * s
                   and g.bbox[1] <= b[3] and b[1] <= g.bbox[3] for b in head_boxes):
                direction = _accidental_direction(g, s)
                if direction:
                    accidental_marks.append((g.bbox, direction, g.ident, _glyph_anchor(g, direction, s)))
            continue
        # Accidentals sit just left of a notehead; articulations sit over or under one.
        if any(b[0] - g.bbox[2] <= ACCIDENTAL_REACH_SPACES * s and g.bbox[2] <= b[0] + 0.1 * s
               and g.bbox[1] <= b[3] and b[1] <= g.bbox[3] for b in head_boxes):
            beside = "accidental_beside_notehead"
        elif any(g.bbox[0] <= b[2] and b[0] <= g.bbox[2] for b in head_boxes):
            beside = "over_or_under_notehead"
        elif any(st.x - st.half_width <= g.bbox[2] and g.bbox[0] <= st.x + st.half_width and g.bbox[1] <= st.y1 and st.y0 <= g.bbox[3] for st in stems):
            beside = "touching_stem"
        else:
            beside = None
        kind = _rest_glyph(g, staff)
        if _rest_form_outranks_accidental_position(beside, kind):
            beside = None
        if not beside and kind not in WRITTEN_VALUES and _is_stroke_fragment_outside_band(g, staff):
            non_events.append({"reason": "stroke_fragment_outside_staff_band", "glyph": g, "cx": g.cx,
                               "width_spaces": g.w / s, "height_spaces": g.h / s,
                               "distance_spaces": max(staff.top - g.bbox[3], g.bbox[1] - staff.bottom) / s})
            continue
        if kind not in WRITTEN_VALUES and _is_wavy_line_outside_staff(g, staff):
            # REFUSE-10: a vibrato or trill line outside the five lines, even over noteheads.
            non_events.append({"reason": "wavy_line_outside_staff", "glyph": g, "cx": g.cx,
                               "width_spaces": g.w / s, "height_spaces": g.h / s})
            continue
        if kind not in WRITTEN_VALUES and g.ident in wave_ids:
            # REFUSE-07: a stroke of a rolled-chord wave column, wherever it stands against a head or stem.
            non_events.append({"reason": "wave_column_stroke", "glyph": g, "cx": g.cx,
                               "width_spaces": g.w / s, "height_spaces": g.h / s})
            continue
        if beside:
            # A glyph whose own form identifies a rest value is a rest even beside a note (another
            # voice's rest printed over it): never dropped.
            if kind in WRITTEN_VALUES:
                events.append({"_rest": g, "_rest_kind": kind, "_cx": g.cx, "_unread": "rest_glyph_beside_note"})
            else:
                ignored[beside] = ignored.get(beside, 0) + 1
                direction = _accidental_direction(g, s) if beside == "accidental_beside_notehead" else None
                if not direction and not base_equivalent and beside == "accidental_beside_notehead":
                    direction = _grace_scale_accidental_direction(g, s, heads, small_ids)
                if direction:
                    accidental_marks.append((g.bbox, direction, g.ident, _glyph_anchor(g, direction, s)))
                elif not base_equivalent:
                    # The assembler decides preservation from the base-equivalent
                    # route; a located overlap never supplies a duration.
                    overlaps.append({"glyph": g, "cx": g.cx, "position": beside})
            continue
        if kind is None:
            if _is_thick_barline(g, staff):
                ignored["thick_barline"] = ignored.get("thick_barline", 0) + 1
            else:
                events.append({"_rest": g, "_rest_kind": None, "_cx": g.cx, "_kind": "unclassified",
                               "_unread": "symbol_unclassified"})
            continue
        events.append({"_rest": g, "_rest_kind": kind, "_cx": g.cx})

    _attach_accidentals(events, accidental_marks, staff)
    if not base_equivalent:
        # REFUSE-16: an arc joining a note and an adjacent grace head at one staff position is a tie the
        # reader does not carry across a grace (REFUSE-11/12 tie only ordinary notes). It is located, never
        # dropped, so a bar that holds it is not written without the tie.
        for glyph in arcs:
            if glyph.ident not in slur_ids | crescent_tie_ids and _arc_joins_note_and_grace(glyph, events, s):
                ignored["over_or_under_notehead"] = ignored.get("over_or_under_notehead", 0) + 1
                overlaps.append({"glyph": glyph, "cx": glyph.cx, "position": "over_or_under_notehead"})

    # Assign events to bars.
    leading_start_repeat = None
    if (boundaries and not any(e["_cx"] < boundaries[0][0] for e in events)
            and _is_start_repeat_after_header(staff, glyphs, [t for t in symbols.texts if in_zone(t.cx, t.cy)], boundaries[0])):
        leading_start_repeat = [round(boundaries[0][0], 3), round(boundaries[0][1], 3)]
        boundaries = boundaries[1:]  # REFUSE-17: a start-repeat sign opens bar 1, it does not end a bar before it
        ignored["leading_start_repeat_barline"] = ignored.get("leading_start_repeat_barline", 0) + 1
    edges = [staff.x0] + [x for pair in boundaries for x in pair] + [staff.x1]
    bars = [(edges[i], edges[i + 1]) for i in range(0, len(edges) - 1, 2)]
    for event in events:
        event["_bar"] = next((i for i, (a, b) in enumerate(bars) if a <= event["_cx"] <= b), None)
    bar_count = len(bars)
    if bars and not any(e["_bar"] == bar_count - 1 for e in events) and bars[-1][1] - bars[-1][0] < 3 * s:
        bars = bars[:-1]  # the sliver after a final barline drawn short of the staff end

    for item in non_events:
        glyph = item.pop("glyph")
        cx = item.pop("cx")
        bar = next((i for i, (a, b) in enumerate(bars) if a <= cx <= b), None)
        located = {"page_index": staff.page_index, "system_index": state["system_index"],
                   "bar_index": None if bar is None else state["bar_offset"] + bar,
                   "bbox": [round(v, 3) for v in glyph.bbox], **{k: round(v, 3) for k, v in item.items() if k != "reason"}}
        state["diagnostics"]["non_events"].append({"reason": item["reason"], **located})
        by_reason = state["diagnostics"]["non_events_by_reason"]
        by_reason[item["reason"]] = by_reason.get(item["reason"], 0) + 1

    for item in overlaps:
        glyph = item["glyph"]
        bar = next((i for i, (a, b) in enumerate(bars) if a <= item["cx"] <= b), None)
        position = None if bar is None else sum(
            1 for e in events if e["_bar"] == bar and e["_cx"] < item["cx"])
        state["diagnostics"].setdefault("unread_symbols", []).append({
            "status": "unread", "class": "unsupported_overlapping_form", "reason": item["position"],
            "shape_class": _unread_shape_class(glyph, s), "source": glyph.ident,
            "location": {"page_index": staff.page_index, "system_index": state["system_index"],
                         "bar_index": None if bar is None else state["bar_offset"] + bar,
                         "event_index": position, "bbox": [round(v, 3) for v in glyph.bbox]},
            "width_spaces": round(glyph.w / s, 3), "height_spaces": round(glyph.h / s, 3)})

    # Bar numbers are printed before the first event of their bar.
    first_x_in_bar: dict[int, float] = {}
    for e in events:
        box = _event_bbox(e)
        if e["_bar"] is not None:
            first_x_in_bar[e["_bar"]] = min(first_x_in_bar.get(e["_bar"], math.inf), box[0])
    tab_text_rows = _tab_text_rows(staff, symbols)
    tuplet_digits = []
    for t in digit_texts:
        if _on_tab_text_row(t, tab_text_rows):
            continue
        # A number printed on a barline belongs to the bar starting there.
        bar = next((i for i, (_, end) in enumerate(bars) if t.cx <= end), None)
        if bar is not None and t.cx < first_x_in_bar.get(bar, math.inf) and t.cy < staff.top:
            continue
        # A number touching other text on its line is part of a label (a chord name such as
        # "Cm7(flat)5"), never a tuplet number.
        if any(o is not t and abs(o.cy - t.cy) <= 0.5 * s and (0 <= t.bbox[0] - o.bbox[2] <= LABEL_GAP_SPACES * s
                                                              or 0 <= o.bbox[0] - t.bbox[2] <= LABEL_GAP_SPACES * s)
               for o in symbols.texts):
            state["diagnostics"]["label_numbers"] += 1
            continue
        tuplet_digits.append(t)

    # Per-stem parts, dots, groups.
    claimed: set[str] = set()
    events.sort(key=lambda e: e["_cx"])
    for event in events:
        stem = event.get("_stem")
        if stem is not None:
            parts = parts_by_stem[stem.ident]
            if isinstance(parts["lines"], list) and parts["lines"]:
                root = groups.find(stem.ident)
                event["_beam_group"] = group_ids[root]
                event["_beam_group_size"] = len(group_members[root])
        anchors = [h.bbox for h in event.get("_heads", [])] or [event["_rest"].bbox]
        rows = _augmentation_dots(anchors, dots, claimed, s, rest="_rest" in event)
        claimed.update(d.ident for row in rows for d in row)
        event["_dots"] = rows
    ambiguous = _ambiguous_point_dots(events, s)
    if ambiguous:
        # More than one note or rest could own the dot: it stays unread, as do any dots after it in its row.
        for event in events:
            kept = []
            for row in event["_dots"]:
                cut = next((i for i, d in enumerate(row) if d.ident in ambiguous), len(row))
                if row[:cut]:
                    kept.append(row[:cut])
            event["_dots"] = kept
        state["diagnostics"]["ambiguous_point_dots"] = state["diagnostics"].get("ambiguous_point_dots", 0) + len(ambiguous)

    group_info = []
    for root, members in group_members.items():
        xs = [m.x for m in members]
        beam_ys = [(line["band"][0] + line["band"][1]) / 2 for m in members
                   for line in parts_by_stem[m.ident]["lines"]]
        sources = sorted({ident for m in members for line in parts_by_stem[m.ident]["lines"] for ident in line["sources"]})
        group_info.append({"id": group_ids[root], "x0": min(xs), "x1": max(xs), "beam_ys": beam_ys, "sources": sources})
    tuplets, unassociated = _read_tuplets(tuplet_digits, symbols.polylines, group_info, events, s)
    for index, tuplet in enumerate(tuplets):
        for member in tuplet["members"]:
            if "_tuplet" in member:
                member["_unread"] = "overlapping_tuplets"
            member["_tuplet"] = {"actual": tuplet["actual"], "normal": tuplet["normal"],
                                 "group": f"s{state['system_number']}t{index}", "sources": tuplet["sources"],
                                 "ratio_source": tuplet["ratio_source"]}
    for digit in unassociated:
        hit = [e for e in events if _event_bbox(e)[0] - 0.5 * s <= digit.cx <= _event_bbox(e)[2] + 0.5 * s]
        for e in hit:
            e["_unread"] = "tuplet_number_unassociated"
        if not hit:
            state["diagnostics"]["unassociated_numbers"] += 1

    # Ties: an arc from one notehead to the next notehead at the same staff position.
    tie_events = [e for e in events if not e.get("_grace")]  # a tie joins the notes either side of a grace
    for arc in arcs:
        tie = _tie_ends(arc, tie_events, s)
        if tie is None:
            arriving = _arriving_tie_end(arc, tie_events, s)
            if arriving is not None and ENABLE_ARRIVING_TIE:
                # REFUSE-11: an arc that ends on the system's first note and starts before any note of
                # this system. It is read as nothing here (it is only an arc ending at a head); the route
                # ties it to the previous system's last note only if that note's tie ran off the system
                # end on the same staff position.
                head = arriving[1]
                arriving[0].setdefault("_tie", {"start": False, "stop": False, "sources": []})
                arriving[0]["_tie"]["arrives_from_previous_system"] = {
                    "source": arc.ident, "head_position": _staff_position(head, staff, s)}
                continue
            state["diagnostics"]["arcs_not_ties"] += 1
            continue
        start, stop, start_head, stop_head = tie
        start.setdefault("_tie", {"start": False, "stop": False, "sources": []})
        start["_tie"]["start"] = True
        start["_tie"]["sources"].append(arc.ident)
        if ENABLE_TIED_HEAD_OWNERSHIP and len(start.get("_heads", [])) > 1:
            # TIEOWN-01: the arc leaves ONE head of a chord. Its position, and its rank among the chord's heads,
            # let the route tie that head alone instead of every note of the chord.
            _record_tie_end(start["_tie"], "start", start, start_head, staff, s)
        if stop is not None:
            stop.setdefault("_tie", {"start": False, "stop": False, "sources": []})
            stop["_tie"]["stop"] = True
            stop["_tie"]["sources"].append(arc.ident)
            if ENABLE_TIED_HEAD_OWNERSHIP and len(stop.get("_heads", [])) > 1:
                # REFUSE-12: the arc ends on ONE head of a chord. Record which, so the route can tie that
                # head alone; an event-level tie would tie every note of the chord.
                _record_tie_end(stop["_tie"], "stop", stop, stop_head, staff, s)
        else:
            start["_tie"]["continues_beyond_system"] = True
            leaving = [h for h in start.get("_heads", [])]
            if len(leaving) == 1:
                start["_tie"]["leaving_head_position"] = _staff_position(leaving[0], staff, s)

    # A taller crescent ending on a whole head is outside the supported tie
    # contour. If its ends locate adjacent heads at the same staff position,
    # silently treating it as decoration would drop a possible tie. Refuse its owners;
    # do not enlarge the accepted contour or assign a tie from spacing.
    for start, stop, contour in crescent_ties:
        for end, key in ((start, "start"), (stop, "stop")):
            end.setdefault("_tie", {"start": False, "stop": False, "sources": []})
            end["_tie"][key] = True
            end["_tie"]["sources"].append(contour.ident)
    for start, stop, contour in _unclassified_tie_contours(
            [g for g in glyphs if g.ident not in crescent_tie_ids], tie_events, s):
        for owner in (start, stop):
            owner["_unread"] = "unclassified_same_position_arc"
        state["diagnostics"].setdefault("unclassified_tie_contours", []).append({
            "source": contour.ident, "page_index": staff.page_index,
            "system_index": state["system_index"], "bbox": list(contour.bbox),
        })

    # Concurrent events (another voice) are not read by this reader.
    for a, b in zip(events, events[1:]):
        if "_heads" in a and "_heads" in b:
            ax, bx = _event_bbox(a), _event_bbox(b)
            if ax[2] > bx[0] + 0.1 * s and a.get("_stem") is not b.get("_stem"):
                a["_unread"] = b["_unread"] = "concurrent_events"

    records = []
    per_bar: dict[int, int] = {}
    located_records = []
    for event in sorted(located_events, key=lambda e: e["_cx"]):
        bar = next((i for i, (a, b) in enumerate(bars) if a <= event["_cx"] <= b), None)
        if bar is None:
            state["diagnostics"]["events_outside_bars"] += 1  # counted, never silently dropped
            continue
        event["_bar"] = bar
        # Position in the bar's event order: the number of ordinary events left of it.
        position = sum(1 for e in events if e["_bar"] == bar and e["_cx"] < event["_cx"])
        located_records.append(_record(event, staff, state, bar, position, parts_by_stem, head_kind, s))
    for event in events:
        bar = event["_bar"]
        if bar is None:
            state["diagnostics"]["events_outside_bars"] += 1  # counted, never silently dropped
            continue
        index = per_bar.get(bar, 0)
        per_bar[bar] = index + 1
        records.append(_record(event, staff, state, bar, index, parts_by_stem, head_kind, s))
    _attach_graces(records, s)
    state["diagnostics"].setdefault("located_unread_events", []).extend(located_records)
    by_reason = state["diagnostics"]["ignored_symbols_by_reason"]
    for reason, count in ignored.items():
        state["diagnostics"]["ignored_symbols"] += count
        by_reason[reason] = by_reason.get(reason, 0) + count
    return {"records": records, "bar_count": len(bars), "bars": bars, "time_signature": state.get("time_signature"),
            "leading_start_repeat": leading_start_repeat}


ACCIDENTAL_TEXT = {"#": "sharp", "♯": "sharp", "b": "flat", "♭": "flat"}
# Treble-clef natural pitch classes by staff step, counted from the bottom line (E).
_TREBLE_STEP_PITCH_CLASSES = (4, 5, 7, 9, 11, 0, 2)


def _is_natural_accidental(glyph: Glyph, space: float) -> bool:
    """Two offset uprights joined by two separated oblique bands.

    The left upright starts at the top, the right ends at the bottom. Scans
    between them cross both connectors, with open space above, below and
    between. This distinguishes a natural from a flat's bowl, a sharp's
    crossing strokes and a thin arpeggio fragment. Position beside a head
    establishes ownership elsewhere; it never establishes this glyph's type.
    """
    if not (glyph.filled and 0.5 <= glyph.w / space <= 1.1
            and 2.1 <= glyph.h / space <= 3.2):
        return False
    scans = [
        [((a - glyph.bbox[1]) / glyph.h, (b - glyph.bbox[1]) / glyph.h)
         for a, b in _runs(glyph.shape, True, glyph.bbox[0] + f * glyph.w,
                           glyph.bbox[1] - 1, glyph.bbox[3] + 1)]
        for f in (0.1, 0.3, 0.5, 0.7, 0.9)
    ]
    if [len(scan) for scan in scans] != [1, 2, 2, 2, 1]:
        return False
    left, right = scans[0][0], scans[-1][0]
    if not (left[0] <= 0.05 and 0.6 <= left[1] <= 0.85
            and 0.15 <= right[0] <= 0.4 and right[1] >= 0.95):
        return False
    return all(0.15 <= a < b <= 0.5 and 0.5 <= c < d <= 0.85
               and b - a <= 0.25 and d - c <= 0.25
               for ((a, b), (c, d)) in scans[1:-1])


def _accidental_direction(glyph: Glyph, space: float) -> str | None:
    from .key_signature import _kind  # key_signature imports this module

    return _kind(glyph, space) or ("natural" if _is_natural_accidental(glyph, space) else None)


def _grace_scale_accidental_direction(glyph: Glyph, space: float, heads: list[Glyph],
                                      small_ids: set[str]) -> str | None:
    """REFUSE-16: a sharp, flat or natural printed at grace size, just left of a small (grace) head.

    An engraver sets a grace note's accidental in the same reduced size as its head, so the accidental is
    the same drawn form as a full-size one at a smaller scale. The scale is this staff's own small head
    width over its median full-size head width (measured, never fixed); the unchanged form tests then run
    at that scale. Only a glyph standing in an accidental's place left of a small head qualifies, so a
    glyph beside a full-size head is judged exactly as before.
    """
    full = sorted(h.w for h in heads if h.ident not in small_ids)
    if not full:
        return None
    full_width = full[len(full) // 2]
    for head in heads:
        if head.ident not in small_ids:
            continue
        b = head.bbox
        if (b[0] - glyph.bbox[2] <= ACCIDENTAL_REACH_SPACES * space and glyph.bbox[2] <= b[0] + 0.1 * space
                and glyph.bbox[1] <= b[3] and b[1] <= glyph.bbox[3]):
            return _accidental_direction(glyph, space * head.w / full_width)
    return None


def _glyph_anchor(glyph: Glyph, direction: str, space: float) -> float:
    """The y of the pitch a painted accidental belongs to: a sharp is centred on it, a flat's bowl
    (measured on the corpus, half a space below the outline's centre) is."""
    return glyph.cy + (0.5 * space if direction == "flat" else 0.0)


def _attach_accidentals(events: list[dict[str, Any]], marks: list[tuple[tuple[float, float, float, float], str, str, float]],
                        staff: Staff) -> None:
    """Attach each printed flat or sharp to the notehead it stands left of.

    The staff step of that head, read as a treble clef, names the letter, so the accidental
    names a pitch class that the build step must find among the TAB notes of the event; an
    accidental whose pitch class no TAB note has is reported there, never forced onto a note.
    """
    space = staff.space
    for box, direction, ident, anchor in marks:
        best = None
        for event in events:
            for head in event.get("_heads", ()):
                b = head.bbox
                if (b[0] - box[2] <= ACCIDENTAL_REACH_SPACES * space and box[2] <= b[0] + 0.1 * space
                        and box[1] <= b[3] and b[1] <= box[3]):
                    distance = abs(head.cy - anchor)
                    if best is None or distance < best[0]:
                        best = (distance, event, head)
        if best is None:
            continue
        _, event, head = best
        step = round((staff.bottom - head.cy) / (space / 2))
        natural = _TREBLE_STEP_PITCH_CLASSES[step % 7]
        pitch_class = (natural + {"sharp": 1, "flat": -1, "natural": 0}[direction]) % 12
        event.setdefault("_accidentals", []).append(
            {"direction": direction, "pitch_class": pitch_class, "source": ident,
             "head_staff_position_index": round((head.cy - staff.top) / (space / 2))})


def _event_bbox(event: dict[str, Any]) -> tuple[float, float, float, float]:
    if "_rest" in event:
        return event["_rest"].bbox
    return _bbox_union([h.bbox for h in event["_heads"]])


def _unclassified_tie_contours(glyphs: list[Glyph], events: list[dict[str, Any]], space: float
                               ) -> list[tuple[dict, dict, Glyph]]:
    """Unsupported tall crescents ending on an adjacent same-position whole head.

    Stemmed notes can own other forms (including supported slanted slurs).
    This guard is limited to the measured whole-head continuation case.
    """
    notes = [(e, e["_heads"][0]) for e in events if len(e.get("_heads", [])) == 1]
    result = []
    reach = TIE_END_REACH_SPACES * space
    for contour in glyphs:
        if not (contour.curved and contour.filled
                and contour.w >= ARC_MIN_WIDTH_SPACES * space
                and contour.h > ARC_MAX_HEIGHT_SPACES * space
                and _fill_ratio(contour) <= ARC_MAX_FILL_RATIO):
            continue
        starts = [(e, h) for e, h in notes
                  if h.bbox[0] - 0.3 * space <= contour.bbox[0] <= h.bbox[2] + reach]
        stops = [(e, h) for e, h in notes
                 if h.bbox[0] - reach <= contour.bbox[2] <= h.bbox[2] + 0.3 * space]
        if len(starts) != 1 or len(stops) != 1:
            continue
        start, first = starts[0]
        stop, last = stops[0]
        following = min((e for e in events if e["_cx"] > start["_cx"]),
                        key=lambda e: e["_cx"], default=None)
        above = (contour.bbox[3] <= min(first.bbox[1], last.bbox[1])
                 and max(first.bbox[1], last.bbox[1]) - contour.bbox[3] <= reach)
        below = (contour.bbox[1] >= max(first.bbox[3], last.bbox[3])
                 and contour.bbox[1] - min(first.bbox[3], last.bbox[3]) <= reach)
        if (following is stop and stop.get("_stem") is None and _is_notehead(last, space) == "hollow"
                and abs(first.cy - last.cy) <= TIE_SAME_POSITION_SPACES * space
                and (above or below)):
            result.append((start, stop, contour))
    return result


ENABLE_ARRIVING_TIE = True  # REFUSE-11 mutant switch: False reads no arriving tie (the old behaviour)
ENABLE_TIED_HEAD_OWNERSHIP = True  # REFUSE-12 mutant switch: False records no tied-head position (the old behaviour)


def _staff_position(head: Glyph, staff: Staff, space: float) -> int:
    """A notehead's vertical place in half staff spaces above the bottom line (a pitch, without accidentals)."""
    return round((staff.bottom - head.cy) / (space / 2))


def _record_tie_end(tie: dict[str, Any], side: str, event: dict[str, Any], head: Glyph, staff: Staff,
                    space: float) -> None:
    """Note which head of a chord a tie arc end sits on: ``<side>_head_positions`` (staff positions) and
    ``<side>_head_ranks`` (0 = lowest head of the chord). The owned position must name exactly one head.
    Other heads may share a position: they cannot make this arc's unique endpoint ambiguous. Their
    positions still come from their printed TAB digits, never from their notation pitches."""
    position = _staff_position(head, staff, space)
    tie.setdefault(f"{side}_head_positions", []).append(position)
    positions = sorted(_staff_position(h, staff, space) for h in event["_heads"])
    if positions.count(position) == 1:
        tie.setdefault(f"{side}_head_ranks", []).append(positions.index(position))
        if len(set(positions)) != len(positions):
            tie["endpoint_rank_basis"] = "unique_endpoint_with_unrelated_duplicate"


def _arriving_tie_end(arc: Glyph, events: list[dict[str, Any]], space: float):
    """(first event, head) when ``arc`` is the end of a tie coming from the system before, or None.

    The arc must end at the very first note of the system, at the head's own staff height, and begin
    before every note of this system (no head of this system can own its start). Nothing else is read:
    that it is a tie and not a slur is settled by the route from the previous system's last note.
    """
    if not events:
        return None
    first = min(events, key=lambda e: e["_cx"])
    if len(first.get("_heads", [])) != 1:
        return None
    head = first["_heads"][0]
    reach = TIE_END_REACH_SPACES * space
    if arc.bbox[0] + 0.3 * space >= head.bbox[0]:
        return None  # it starts at or after the head: not an arrival
    if not (head.bbox[0] - reach <= arc.bbox[2] <= head.bbox[2] + 0.3 * space):
        return None
    if abs(head.cy - arc.cy) > TIE_VERTICAL_REACH_SPACES * space:
        return None
    return first, head


def _tie_ends(arc: Glyph, events: list[dict[str, Any]], space: float):
    """(start, stop) events joined by a tie arc, (start, None) when it runs on past the system, or None.

    A tie leaves a notehead (after its dots, if any) and ends at the same staff position on the very
    next event. An arc that ends at another pitch, or skips an event, is a slur: not a tie.
    """
    reach = TIE_END_REACH_SPACES * space
    notes = [(e, h) for e in events for h in e.get("_heads", [])]

    def right_edge(event: dict[str, Any], head: Glyph) -> float:
        dots = [d.bbox[2] for row in event.get("_dots", []) for d in row if abs(d.cy - head.cy) <= DOT_HEIGHT_TOLERANCE_SPACES * space]
        return max([head.bbox[2], *dots])

    starts = [(e, h) for e, h in notes if h.bbox[0] - 0.3 * space <= arc.bbox[0] <= right_edge(e, h) + reach
              and abs(h.cy - arc.cy) <= TIE_VERTICAL_REACH_SPACES * space]
    if len(starts) != 1:
        return None
    start, head = starts[0]
    following = sorted((e for e in events if e["_cx"] > start["_cx"]), key=lambda e: e["_cx"])
    ends_at = [(e, h) for e, h in notes if e is not start and h.bbox[0] - reach <= arc.bbox[2] <= h.bbox[2] + 0.3 * space]
    if not ends_at:
        return (start, None, head, None) if not following else None
    stops = [(e, h) for e, h in ends_at if abs(h.cy - head.cy) <= TIE_SAME_POSITION_SPACES * space]
    if len(stops) == 1 and following and stops[0][0] is following[0]:
        return start, stops[0][0], head, stops[0][1]
    return None


def _record(event: dict[str, Any], staff: Staff, state: dict[str, Any], bar: int, index: int,
            parts_by_stem: dict[str, dict[str, Any]], head_kind: dict[str, str], space: float) -> dict[str, Any]:
    bar_index = state["bar_offset"] + bar
    location = {"page_index": staff.page_index, "system_index": state["system_index"], "bar_index": bar_index,
                "event_index": index, "bbox": [round(v, 3) for v in _event_bbox(event)]}
    dot_rows = event["_dots"]
    dot_count = max((len(row) for row in dot_rows), default=0)
    tie = event.get("_tie", {"start": False, "stop": False, "sources": []})
    record: dict[str, Any] = {
        "page_index": staff.page_index, "system_index": state["system_index"], "system_number": state["system_number"],
        "bar_index": bar_index, "bar_in_system": bar, "event_index": index,
        "kind": "rest", "status": "read", "reason": None, "location": location,
        "notehead": None, "stem": None, "flags": {"count": 0, "glyphs": []},
        "beams": {"count": 0, "sources": [], "group": None, "group_size": 0},
        "dots": {"count": dot_count, "sources": sorted({d.ident for row in dot_rows for d in row})},
        "rest": None, "tuplet": event.get("_tuplet"), "tie": tie,
        "written": None, "value_quarters": None, "duration_quarters": None,
    }
    parts = {"kind": "rest", "head_kind": None, "has_stem": False, "flag_hooks": 0, "beam_count": 0,
             "beam_group_size": 0, "rest_glyph": None}
    reason = event.get("_unread")
    if event.get("_unread_symbols"):
        record["unread_symbols"] = [
            {"status": "unread", "class": "parenthesized_head_unrepresented",
             "reason": "parenthesized_head_unrepresented", "source": glyph.ident,
             "location": {**location, "bbox": [round(v, 3) for v in glyph.bbox]},
             "width_spaces": round(glyph.w / space, 3),
             "height_spaces": round(glyph.h / space, 3)}
            for glyph in event["_unread_symbols"]]
        # The existing IR has no ghost-note representation. Preserve the
        # source-read duration while exposing each unsupported owning-head
        # annotation as a located unread symbol, rather than erasing that note.
        state["diagnostics"].setdefault("unread_symbols", []).extend(record["unread_symbols"])
    if event.get("_ghost"):
        record["ghost"] = {"parenthesis_sources": [glyph.ident for glyph in event["_ghost"]]}
        if event.get("_ghost_chord_pair"):
            record["ghost"]["chord_pair"] = True
    if len({len(row) for row in dot_rows}) > 1:
        reason = reason or "dot_rows_disagree"
    if "_rest" in event:
        glyph = event["_rest"]
        record["kind"] = event.get("_kind", "rest")
        record["rest"] = {"glyph": event["_rest_kind"] if event["_rest_kind"] in WRITTEN_VALUES else None,
                          "source": glyph.ident}
        parts["rest_glyph"] = event["_rest_kind"]
    else:
        heads = event["_heads"]
        kinds = sorted({head_kind[h.ident] for h in heads})
        record["kind"] = "chord" if len(heads) > 1 else "note"
        record["notehead"] = {"kind": kinds[0] if len(kinds) == 1 else "mixed", "count": len(heads),
                              "sources": [h.ident for h in heads]}
        if "cross" in kinds:
            record["notehead"]["heads"] = [
                {"source": h.ident, "kind": head_kind[h.ident],
                 "staff_position_index": round((h.cy - staff.top) / (space / 2)),
                 "width_spaces": round(h.w / space, 3), "height_spaces": round(h.h / space, 3)}
                for h in heads]
        parts["kind"] = "note"
        duration_kinds = {"filled" if kind == "cross" else kind for kind in kinds}
        parts["head_kind"] = sorted(duration_kinds)[0]
        if event.get("_accidentals"):
            record["accidentals"] = event["_accidentals"]
        if len(duration_kinds) > 1:
            reason = reason or "mixed_notehead_kinds"
        stem = event["_stem"]
        if "cross" in kinds and stem is None:
            reason = reason or "percussive_strike_without_owning_stem"
        if stem is not None:
            record["stem"] = {"source": stem.ident, "direction": "up" if stem.up else "down"}
            parts["has_stem"] = True
            stem_parts = parts_by_stem[stem.ident]
            lines = stem_parts["lines"]
            if isinstance(lines, str):
                reason = reason or lines
                lines = []
            hooks = 0
            glyphs = []
            for flag in stem_parts["flags"]:
                n = _flag_hooks(flag, stem, space)
                if n == 0:
                    reason = reason or "flag_glyph_unidentified"
                hooks += n
                glyphs.append({"source": flag.ident, "hooks": n})
            record["flags"] = {"count": hooks, "glyphs": glyphs}
            record["beams"] = {"count": len(lines), "sources": [",".join(line["sources"]) for line in lines],
                               "group": event.get("_beam_group"), "group_size": event.get("_beam_group_size", 0)}
            parts["flag_hooks"] = hooks
            parts["beam_count"] = len(lines)
            parts["beam_group_size"] = event.get("_beam_group_size", 0)
    written, value_reason = _written_value(parts)
    reason = reason or value_reason
    grace = bool(event.get("_grace"))
    if grace:
        # A grace has no metrical duration: the printed value is evidence, never part of the bar total.
        # A flag is what makes it a grace; a beam, a dot or a tuplet on it is not read.
        if not parts["flag_hooks"] and not parts["beam_count"]:
            reason = reason or "grace_note_without_flag"
        elif parts["flag_hooks"] not in GRACE_READABLE_FLAG_HOOKS:
            reason = reason or "grace_note_unsupported_flag_count"
        elif parts["beam_count"]:
            reason = reason or "grace_note_beamed"
        elif dot_count:
            reason = reason or "grace_note_with_dot"
        heads = event["_heads"]
        record["grace"] = {"head_width_spaces": round(max(h.w for h in heads) / space, 3),
                           "head_height_spaces": round(max(h.h for h in heads) / space, 3),
                           "beat_event_index": None, "gap_spaces": None}
        reason = reason or _grace_under_tuplet_reason(record)
    if reason:
        if "_rest" in event:
            glyph = event["_rest"]
            record["shape_class"] = _unread_shape_class(glyph, space)
            record["source_form"] = glyph.drawing.get("source_form", "drawing")
            record["width_spaces"] = round(glyph.w / space, 3)
            record["height_spaces"] = round(glyph.h / space, 3)
        elif event.get("_unread_symbols"):
            record["shape_class"] = "notehead_parenthesis"
        record["status"] = "unread"
        record["reason"] = reason
        return record
    value = WRITTEN_VALUES[written] * (2 - Fraction(1, 2 ** dot_count))
    duration = Fraction(0) if grace else value
    if record["tuplet"] and not grace:
        duration = value * Fraction(record["tuplet"]["normal"], record["tuplet"]["actual"])
    record["written"] = written
    record["value_quarters"] = _frac(value)
    record["duration_quarters"] = _frac(duration)
    return record


def _grace_under_tuplet_reason(record: dict[str, Any]) -> str | None:
    """REFUSE-06: a grace under a tuplet bracket's span is read, never refused for it.

    It has no metrical duration: the tuplet scales none of it and the bar total never counts it. The
    printed bracket ratio is only carried on its beat, as the page shows it.
    """
    return None


def _attach_graces(records: list[dict[str, Any]], space: float) -> None:
    """Attach each grace to the beat it ornaments: the first full note after it in its bar, if it follows close.

    The grace stands before its note, so the beat is the next event to its right once any graces
    between are passed (a run of graces ornaments one beat). A grace with no note after it in the bar,
    a rest after it, or a gap wider than ``GRACE_MAX_GAP_SPACES`` is unread: it is never given a beat by guess.
    """
    for i, record in enumerate(records):
        if "grace" not in record:
            continue
        bar = record["bar_index"]
        j = i + 1
        while j < len(records) and records[j]["bar_index"] == bar and "grace" in records[j]:
            j += 1
        beat = records[j] if j < len(records) and records[j]["bar_index"] == bar else None
        gap = None if beat is None else (beat["location"]["bbox"][0] - record["location"]["bbox"][2]) / space
        record["grace"]["gap_spaces"] = None if gap is None else round(gap, 3)
        if beat is None:
            reason = "grace_note_without_following_note"
        elif beat["kind"] not in ("note", "chord"):
            reason = "grace_note_before_rest"
        elif not 0 <= gap <= GRACE_MAX_GAP_SPACES:
            reason = "grace_note_beat_too_far"
        else:
            record["grace"]["beat_event_index"] = beat["event_index"]
            continue
        if record["status"] == "read":
            record.update(status="unread", reason=reason, written=None, value_quarters=None, duration_quarters=None)


# --- document -------------------------------------------------------------------------------

def _bar_checks(records: list[dict[str, Any]], bar_signatures: dict[int, dict[str, Any] | None],
                located: list[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    """Per-bar totals. ``located`` symbols (UNREAD-01) never change a status except that they stop a bar
    that would match from being written: a located unread symbol is not a value, and its bar is refused."""
    checks = []
    for bar, signature in sorted(bar_signatures.items()):
        events = [r for r in records if r["bar_index"] == bar]
        unread = sum(1 for r in events if r["status"] != "read")
        total = sum((Fraction(r["duration_quarters"]) for r in events if r["status"] == "read"), Fraction(0))
        held = [{"class": r["shape_class"], "reason": r["reason"], "page_index": r["page_index"],
                 "system_index": r["system_index"], "bar_index": r["bar_index"], "event_index": r["event_index"]}
                for r in located if r["bar_index"] == bar]
        check = {"bar_index": bar, "events": len(events), "unread_events": unread, "total_quarters": _frac(total),
                 "time_signature": None, "time_signature_source": None, "expected_quarters": None}
        if held:
            check["located_unread"] = held
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
            check["status"] = "match" if total == expected and not held else "mismatch"
        checks.append(check)
    return checks


def _signature_basis(signature: dict[str, Any] | None) -> dict[str, Any] | None:
    """Why a bar has the signature it has: printed or caller-declared, the declared value, any unread reading."""
    if not signature:
        return None
    declared = signature.get("declared")
    return {"basis": signature["basis"], "origin": signature.get("origin"), "shape": signature.get("shape"),
            "declared": f"{declared[0]}/{declared[1]}" if declared else None, "unread": signature.get("unread")}


def _governing_signature(printed: dict[str, Any] | None, origin: str | None, declared: dict[str, Any] | None,
                         unread: dict[str, Any] | None) -> dict[str, Any] | None:
    """The signature that governs a system's bars, and why.

    A printed signature wins; the caller's declared value is only used where none is printed or readable,
    and a declared value that differs from a printed one is carried as a conflict, never chosen between.
    """
    if printed:
        signature = {**printed, "basis": "printed", "origin": origin}
        if declared:
            signature["declared"] = declared["value"]
            if tuple(declared["value"]) != tuple(printed["value"]):
                signature["conflict"] = True
        return signature
    if declared:
        return {**declared, "basis": "caller_declared", "origin": None, "unread": unread}
    return None


def _resolve_strike_head_positions(records: list[dict[str, Any]], staff: Staff,
                                   symbols: PageSymbols, keys: list[dict[str, Any]]) -> None:
    """Source staff position for writer storage only, never a sounding strike pitch.

    Reuse the existing proportional clef classifier and staff-step mapping. A
    header that cannot resolve its clef or key leaves the position unresolved.
    """
    from ..logical_clef_candidate_classifier import classify_logical_clef_candidate
    from ..pdf_geometry_candidates import LeftMarginPrimitiveCandidate
    from ..pdf_pitch_mapper import map_staff_step_to_midi_pitch
    from .time_signature import _clef

    if not any((r.get("notehead") or {}).get("heads") for r in records):
        return
    clef = _clef(staff, symbols)
    if clef is None:
        return
    x0, y0, x1, y1 = clef.bbox
    classified = classify_logical_clef_candidate([
        LeftMarginPrimitiveCandidate(page_index=staff.page_index + 1,
            system_index=1, staff_index=1, x0=x0, y0=y0, x1=x1, y1=y1,
            kind="curve", source="left_margin")], staff.space,
        staff.bottom - staff.top, staff.x0)
    clef_kind = classified["label"].removesuffix("_clef_candidate")
    if clef_kind not in {"treble", "bass", "alto"}:
        return
    # An octave annotation is not read by this clef classifier. Do not resolve
    # a header containing another nearby glyph or text as an ordinary clef.
    adjacent = [g for g in symbols.glyphs if g.ident != clef.ident
                and abs(g.cx - clef.cx) <= staff.space
                and 0 <= g.bbox[1] - clef.bbox[3] <= 2 * staff.space]
    adjacent += [t for t in symbols.texts if abs(t.cx - clef.cx) <= staff.space
                 and 0 <= t.bbox[1] - clef.bbox[3] <= 2 * staff.space]
    if adjacent:
        return
    for record in records:
        printed = [a for r in records if r["bar_index"] == record["bar_index"]
                   for a in r.get("accidentals") or ()]
        if any(a["direction"] != "natural" for a in printed):
            # The existing accidental reader returns event pitch classes, not
            # a per-head octave owner. Keep the storage position unresolved.
            continue
        # A natural only changes a head whose letter it can cancel in the key.
        naturals = {a["head_staff_position_index"] for a in printed}
        key = keys[record["bar_in_system"]]
        if key["status"] != "read":
            continue
        fifths = key["fifths"]
        altered = ("FCGDAEB"[:fifths] if fifths >= 0 else "BEADGCF"[:-fifths])
        for head in (record.get("notehead") or {}).get("heads", []):
            if head["kind"] != "cross":
                continue
            natural = map_staff_step_to_midi_pitch(head["staff_position_index"], clef_kind)
            letter = {0: "C", 2: "D", 4: "E", 5: "F", 7: "G", 9: "A", 11: "B"}[natural % 12]
            if letter in altered and head["staff_position_index"] in naturals:
                continue
            modifier = (1 if fifths > 0 else -1) if letter in altered else 0
            head["printed_head_midi"] = natural + modifier
            head["printed_position_basis"] = {"clef": clef_kind, "clef_source": clef.ident,
                                               "fifths": fifths, "octave_shift": 0}


def read_note_durations(pdf_path: str | Path, pages: tuple[int, int] | None = None,
                        time_signature: tuple[int, int] | None = None, *,
                        _base_equivalent: bool = False, _chord_pairs: bool = True) -> dict[str, Any]:
    """Read a duration record for every event on every notation staff of the PDF.

    ``pages`` is an inclusive 1-based page range. ``time_signature`` is a caller-declared
    signature used for the bar check only where none is printed or readable; a declared value that
    differs from a printed one makes the affected bars ``signature_conflict`` (TS-READ-01).
    """
    import pymupdf  # noqa: PLC0415 - PyMuPDF is only needed when reading a PDF
    from .key_signature import read_bar_key_signatures, read_system_key_signature  # noqa: PLC0415 - avoid module import cycle
    from .time_signature import read_system_time_signature  # noqa: PLC0415 - avoid module import cycle

    path = Path(pdf_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    records: list[dict[str, Any]] = []
    systems = []
    key_signatures = []
    bar_key_signatures: dict[int, dict[str, Any]] = {}
    bar_signatures: dict[int, dict[str, Any] | None] = {}
    bar_time_signatures: dict[int, dict[str, Any] | None] = {}
    time_signatures: list[dict[str, Any]] = []
    carried: dict[str, Any] | None = None  # the last printed signature, in force until another is printed
    state: dict[str, Any] = {"bar_offset": 0, "system_number": 0, "time_signature": None,
                             "base_equivalent": _base_equivalent, "chord_pairs": _chord_pairs,
                             "diagnostics": {"ignored_symbols": 0, "ignored_symbols_by_reason": {}, "arcs_not_ties": 0, "unassociated_numbers": 0, "label_numbers": 0,
                                             "events_outside_bars": 0, "pages_without_notation_staff": 0,
                                             "non_events": [], "non_events_by_reason": {}}}
    declared = {"value": time_signature, "source": "caller_declared", "sources": []} if time_signature else None
    with pymupdf.open(path) as doc:
        page_heights = [round(float(page.rect.height), 3) for page in doc]
        first, last = pages if pages else (1, len(doc))
        for page_index in range(first - 1, min(last, len(doc))):
            symbols = (extract_page_symbols(doc[page_index], page_index, include_music_font=False)
                       if _base_equivalent else extract_page_symbols(doc[page_index], page_index))
            notation, tab = find_staves(symbols)
            if not notation:
                state["diagnostics"]["pages_without_notation_staff"] += 1
            for system_index, staff in enumerate(sorted(notation, key=lambda st: st.top)):
                key_signature = read_system_key_signature(staff, symbols)
                key_signature["location"].update({"system_index": system_index,
                                                  "bar_index": state["bar_offset"]})
                state["system_index"] = system_index
                text_before = state["time_signature"]
                result = _read_staff(staff, symbols, notation + tab, state)
                records.extend(result["records"])
                system_keys = read_bar_key_signatures(
                    staff, symbols, result["bars"], key_signature,
                )
                _resolve_strike_head_positions(result["records"], staff, symbols, system_keys)
                for bar, bar_key in enumerate(system_keys):
                    bar_key_signatures[state["bar_offset"] + bar] = bar_key
                reading = None
                unread = None
                if state["time_signature"] is not text_before:  # printed as text glyphs at this system start
                    carried, origin = state["time_signature"], "system_start"
                    reading = {"status": "read", "shape": "text_glyphs", "reason": None, "sources": carried["sources"]}
                else:
                    reading = read_system_time_signature(staff, symbols)
                    if reading["status"] == "read":
                        value = (reading["numerator"], reading["denominator"])
                        carried = {"value": value, "source": "vector_glyphs", "sources": reading["sources"],
                                   "shape": reading["shape"]}
                        origin = "system_start"
                    elif reading["status"] == "unreadable" and reading["reason"] != "time_signature_clef_unread":
                        carried, origin = None, None  # a candidate we cannot read: nothing earlier is assumed to hold
                        unread = {"reason": reading["reason"], "location": reading["location"]}
                    else:  # absent, or no clef to search from: whatever is printed already stays in force
                        origin = "carried"
                signature = _governing_signature(carried, origin, declared, unread)
                time_signatures.append({"system_number": state["system_number"], "page_index": page_index,
                                        "first_bar_index": state["bar_offset"], "status": reading["status"],
                                        "shape": reading.get("shape"), "reason": reading.get("reason"),
                                        "value": list(carried["value"]) if carried and reading["status"] == "read" else None,
                                        "sources": reading.get("sources", []), "location": reading.get("location")})
                for bar in range(result["bar_count"]):
                    bar_signatures[state["bar_offset"] + bar] = signature
                    bar_time_signatures[state["bar_offset"] + bar] = _signature_basis(signature)
                key_signatures.append(key_signature)
                systems.append({"page_index": page_index, "system_index": system_index,
                                "system_number": state["system_number"], "first_bar_index": state["bar_offset"],
                                "bar_count": result["bar_count"], "staff_space": round(staff.space, 4),
                                "staff": {"top": round(staff.top, 3), "bottom": round(staff.bottom, 3),
                                          "x0": round(staff.x0, 3), "x1": round(staff.x1, 3)},
                                "bars": [[round(a, 3), round(b, 3)] for a, b in result["bars"]],
                                # REFUSE-17: present only where a start-repeat sign opens the system's first bar
                                **({"leading_start_repeat": result["leading_start_repeat"]}
                                   if result.get("leading_start_repeat") else {})})
                state["bar_offset"] += result["bar_count"]
                state["system_number"] += 1
    checks = _bar_checks(records, bar_signatures, state["diagnostics"].get("located_unread_events", []))
    read = sum(1 for r in records if r["status"] == "read")
    reasons: dict[str, int] = {}
    for r in records:
        if r["reason"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    state["diagnostics"]["key_signatures"] = key_signatures
    state["diagnostics"]["time_signatures"] = time_signatures
    state["diagnostics"]["bar_time_signatures"] = bar_time_signatures
    state["diagnostics"]["bar_key_signatures"] = bar_key_signatures
    if not _base_equivalent and any(
        symbol["class"] in ("unsupported_overlapping_form", "parenthesized_head_unrepresented")
        for symbol in state["diagnostics"].get("unread_symbols", [])
    ):
        # UNREAD-01 preservation is source-derived, never a fixture/bar list.
        # The unchanged drawing-only reader did not see music-font contours,
        # dead-head ownership or paired parentheses. Route that same evidence
        # through the ordinary assembler before deciding whether an overlap or parenthesis
        # must refuse a newly writable bar. No reference is consulted.
        state["diagnostics"]["base_equivalent_note_durations"] = read_note_durations(
            path, pages, time_signature, _base_equivalent=True)
    if any((r.get("ghost") or {}).get("chord_pair") for r in records):
        # REFUSE-18: the same reading without chord pairs is what the reader wrote before this rule; the
        # assembler keeps an already written bar exactly as that reading wrote it.
        state["diagnostics"]["chord_pair_free_note_durations"] = read_note_durations(
            path, pages, time_signature, _chord_pairs=False)
    return {
        "schema": SCHEMA,
        "source": {"pdf_sha256": digest, "pages": list(pages) if pages else None, "page_heights": page_heights},
        "systems": systems,
        "events": records,
        "bar_checks": checks,
        "summary": {"events": len(records), "read_events": read, "unread_events": len(records) - read,
                    "unread_reasons": dict(sorted(reasons.items())), "bars": state["bar_offset"],
                    "bar_check_status": _count(c["status"] for c in checks)},
        "diagnostics": state["diagnostics"],
    }


def _count(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))
