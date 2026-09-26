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
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

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

SCHEMA = "note-duration-records.v0.1"

WRITTEN_VALUES = {
    "whole": Fraction(4), "half": Fraction(2), "quarter": Fraction(1), "eighth": Fraction(1, 2),
    "16th": Fraction(1, 4), "32nd": Fraction(1, 8), "64th": Fraction(1, 16),
}
FLAGGED_VALUES = ["quarter", "eighth", "16th", "32nd", "64th"]  # by flag hooks or beam lines

# Staff and symbol geometry, in staff spaces.
STAFF_LINE_MIN_LENGTH_PT = 50.0
STAFF_LINE_MERGE_GAP_PT = 20.0  # TAB lines are interrupted around fret numbers
# A staff line is mostly ink along its span (TAB lines about 0.8 despite fret-number gaps); a chain
# of ledger lines at one height is about 0.3.
STAFF_LINE_MIN_COVERAGE = 0.6
STAFF_LINE_END_TOLERANCE_PT = 3.0
STAFF_GAP_TOLERANCE = 0.03  # relative spacing tolerance between the lines of one staff
ZONE_REACH_SPACES = 8.0
BARLINE_END_TOLERANCE_SPACES = 0.15
BARLINE_MAX_WIDTH_SPACES = 1.0
BARLINE_CLUSTER_SPACES = 1.5
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
ARC_MIN_WIDTH_SPACES = 1.5
ARC_MAX_HEIGHT_SPACES = 1.3
ARC_MAX_FILL_RATIO = 0.45  # below NOTEHEAD_MIN_FILL_RATIO: a crescent, never an oval
TIE_END_REACH_SPACES = 1.0
TIE_SAME_POSITION_SPACES = 0.25
TIE_VERTICAL_REACH_SPACES = 1.6
HEADER_CLEF_START_SPACES = 3.0
HEADER_CONTIGUITY_SPACES = 1.5
ACCIDENTAL_REACH_SPACES = 2.0
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
REST_STEM_TOP_SHARE = 0.3  # a hooked rest's stem top lies in the upper part of the glyph
REST_WINDOW = {"min_w": 0.6, "max_w": 2.6, "min_h": 0.3, "max_h": 6.0}
REST_VERTICAL_REACH_SPACES = 2.0
TUPLET_BRACKET_REACH_SPACES = 1.5
TUPLET_BRACKET_OVERLAP_SPACES = 0.3
TUPLET_NUMBER_BEAM_REACH_SPACES = 2.5
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
    x0, y0, x1, y1 = glyph.bbox
    hits = sum(
        _inside_fill(x0 + (i + 0.5) * (x1 - x0) / n, y0 + (j + 0.5) * (y1 - y0) / n, glyph.shape)
        for i in range(n) for j in range(n)
    )
    return hits / (n * n)


def _row_counts(glyph: Glyph, samples: int = SCAN_SAMPLES) -> list[int]:
    """Painted runs on horizontal scans spread over the glyph's height."""
    x0, y0, x1, y1 = glyph.bbox
    return [len(_runs(glyph.shape, False, y0 + (k + 0.5) * (y1 - y0) / samples, x0 - 1, x1 + 1))
            for k in range(samples)]


def _column_counts(glyph: Glyph, fractions: tuple[float, ...]) -> list[int]:
    x0, y0, x1, y1 = glyph.bbox
    return [len(_runs(glyph.shape, True, x0 + f * (x1 - x0), y0 - 1, y1 + 1)) for f in fractions]


# --- extraction -----------------------------------------------------------------------------

def extract_page_symbols(page: Any, page_index: int) -> PageSymbols:
    """Split a PyMuPDF page's drawings into glyphs, straight segments, polylines and texts."""
    drawings = page.get_drawings()
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
            if w <= 1.5 and h > 3 * w:  # a vertical drawn as a filled rectangle
                x = float(r.x0 + r.x1) / 2
                segments.append(Segment(ident, x, float(r.y0), x, float(r.y1), w))
                continue
            if h <= 1.0 and w > 3 * h:  # a horizontal drawn as a filled rectangle
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
    for block in page.get_text("rawdict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for chars in _tokens(span.get("chars", []), float(span.get("size") or 0.0)):
                    text = "".join(c["c"] for c in chars)
                    box = _bbox_union([tuple(float(v) for v in c["bbox"]) for c in chars])
                    texts.append(Text(f"p{page_index}:t{len(texts)}", text, box))
    head_shapes = [g.shape for g in glyphs if g.curved]
    return PageSymbols(page_index, glyphs, segments, polylines, texts, head_shapes)


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
                if step > 15.0:
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


def _is_arc(glyph: Glyph, space: float) -> bool:
    """A tie or slur: a thin filled crescent, which leaves most of its box unpainted."""
    return (glyph.curved and glyph.filled and glyph.w >= ARC_MIN_WIDTH_SPACES * space
            and glyph.h <= ARC_MAX_HEIGHT_SPACES * space and _fill_ratio(glyph) <= ARC_MAX_FILL_RATIO)


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


def _flag_hooks(glyph: Glyph, stem: Stem, space: float) -> int:
    """Hooks in one flag glyph: blades crossed by vertical scans through its middle.

    A combined sixteenth-note flag is one glyph with two blades; each blade crosses a scan line
    through the flag's middle once. Scans at three positions must agree, else the glyph is not
    identified (0).
    """
    reach = glyph.bbox[2] - stem.x
    counts = [len(_runs(glyph.shape, True, stem.x + f * reach, glyph.bbox[1] - 1, glyph.bbox[3] + 1))
              for f in (0.4, 0.5, 0.6)]
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


def _augmentation_dots(anchors: list[tuple[float, float, float, float]], dots: list[Glyph], claimed: set[str],
                       space: float, rest: bool = False) -> list[list[Glyph]]:
    """The row of dots to the right of each notehead of the event (or of its rest).

    Each dot adds half the previous value. A chord's noteheads are dotted together, so the count is
    the length of a row, not the number of dot glyphs.
    """
    rows: list[list[Glyph]] = []
    for x0, y0, x1, y1 in anchors:
        cy = (y0 + y1) / 2
        row: list[Glyph] = []
        edge = x1
        while True:
            reach = DOT_FIRST_GAP_SPACES if not row else DOT_NEXT_GAP_SPACES
            options = []
            for dot in dots:
                if dot.ident in claimed or dot in row or dot.bbox[0] < edge - 0.1 * space:
                    continue
                if dot.bbox[0] - edge > reach * space:
                    continue
                if rest:
                    height_ok = y0 - 0.5 * space <= dot.cy <= y1 + 0.5 * space
                elif row:
                    height_ok = abs(dot.cy - row[-1].cy) <= 0.1 * space
                else:
                    height_ok = abs(dot.cy - cy) <= DOT_HEIGHT_TOLERANCE_SPACES * space
                if height_ok:
                    options.append(dot)
            if not options:
                break
            nearest = min(options, key=lambda d: d.bbox[0])
            row.append(nearest)
            edge = nearest.bbox[2]
        if row:
            rows.append(row)
    return rows


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
            if b - a <= 0:
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


def _read_staff(staff: Staff, symbols: PageSymbols, all_staves: list[Staff], state: dict[str, Any]) -> dict[str, Any]:
    s = staff.space
    upper, lower = _zone(staff, all_staves)

    def in_zone(x: float, y: float) -> bool:
        return upper <= y <= lower and staff.x0 - 1.0 <= x <= staff.x1 + 1.0

    glyphs = [g for g in symbols.glyphs if in_zone(g.cx, g.cy)]
    heads: list[Glyph] = []
    head_kind: dict[str, str] = {}
    for g in glyphs:
        kind = _is_notehead(g, s)
        if kind:
            heads.append(g)
            head_kind[g.ident] = kind
    head_ids = set(head_kind)
    dots = [g for g in glyphs if g.ident not in head_ids and _is_dot(g, s)]
    dot_ids = {d.ident for d in dots}
    beams = [g for g in glyphs if g.ident not in head_ids and g.ident not in dot_ids and _is_beam(g, s)]
    beam_ids = {b.ident for b in beams}

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

    used = head_ids | dot_ids | beam_ids
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
        events.append({"_heads": chord, "_stem": stem, "_cx": sum(h.cx for h in chord) / len(chord)})
    loose = sorted((h for h in heads if h.ident not in stem_of), key=lambda h: h.bbox[0])
    for head in loose:
        for event in events:
            if event["_stem"] is None and any(h.bbox[0] <= head.bbox[2] and head.bbox[0] <= h.bbox[2] for h in event["_heads"]):
                event["_heads"].append(head)
                break
        else:
            events.append({"_heads": [head], "_stem": None, "_cx": head.cx})
    for event in events:
        if event["_stem"] is None:
            event["_cx"] = sum(h.cx for h in event["_heads"]) / len(event["_heads"])

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

    ignored = []
    head_boxes = [h.bbox for h in heads]
    for g in glyphs:
        if g.ident in head_ids | dot_ids | attached_beam_ids | flag_ids | arc_ids or g.bbox[2] <= header_end:
            continue
        if not (staff.top - REST_VERTICAL_REACH_SPACES * s <= g.bbox[1] and g.bbox[3] <= staff.bottom + REST_VERTICAL_REACH_SPACES * s):
            continue
        # Accidentals sit just left of a notehead; articulations sit over or under one.
        if any(b[0] - g.bbox[2] <= ACCIDENTAL_REACH_SPACES * s and g.bbox[2] <= b[0] + 0.1 * s
               and g.bbox[1] <= b[3] and b[1] <= g.bbox[3] for b in head_boxes):
            ignored.append(g.ident)
            continue
        if any(g.bbox[0] <= b[2] and b[0] <= g.bbox[2] for b in head_boxes):
            ignored.append(g.ident)
            continue
        if any(st.x - st.half_width <= g.bbox[2] and g.bbox[0] <= st.x + st.half_width and g.bbox[1] <= st.y1 and st.y0 <= g.bbox[3] for st in stems):
            ignored.append(g.ident)
            continue
        kind = _rest_glyph(g, staff)
        if kind is None:
            ignored.append(g.ident)
            continue
        events.append({"_rest": g, "_rest_kind": kind, "_cx": g.cx})

    # Assign events to bars.
    edges = [staff.x0] + [x for pair in boundaries for x in pair] + [staff.x1]
    bars = [(edges[i], edges[i + 1]) for i in range(0, len(edges) - 1, 2)]
    for event in events:
        event["_bar"] = next((i for i, (a, b) in enumerate(bars) if a <= event["_cx"] <= b), None)
    bar_count = len(bars)
    if bars and not any(e["_bar"] == bar_count - 1 for e in events) and bars[-1][1] - bars[-1][0] < 3 * s:
        bars = bars[:-1]  # the sliver after a final barline drawn short of the staff end

    # Bar numbers are printed before the first event of their bar.
    first_x_in_bar: dict[int, float] = {}
    for e in events:
        box = _event_bbox(e)
        if e["_bar"] is not None:
            first_x_in_bar[e["_bar"]] = min(first_x_in_bar.get(e["_bar"], math.inf), box[0])
    tuplet_digits = []
    for t in digit_texts:
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
    for arc in arcs:
        tie = _tie_ends(arc, events, s)
        if tie is None:
            state["diagnostics"]["arcs_not_ties"] += 1
            continue
        start, stop = tie
        start.setdefault("_tie", {"start": False, "stop": False, "sources": []})
        start["_tie"]["start"] = True
        start["_tie"]["sources"].append(arc.ident)
        if stop is not None:
            stop.setdefault("_tie", {"start": False, "stop": False, "sources": []})
            stop["_tie"]["stop"] = True
            stop["_tie"]["sources"].append(arc.ident)
        else:
            start["_tie"]["continues_beyond_system"] = True

    # Concurrent events (another voice) are not read by this reader.
    for a, b in zip(events, events[1:]):
        if "_heads" in a and "_heads" in b:
            ax, bx = _event_bbox(a), _event_bbox(b)
            if ax[2] > bx[0] + 0.1 * s and a.get("_stem") is not b.get("_stem"):
                a["_unread"] = b["_unread"] = "concurrent_events"

    records = []
    per_bar: dict[int, int] = {}
    for event in events:
        bar = event["_bar"]
        if bar is None:
            state["diagnostics"]["events_outside_bars"] += 1  # counted, never silently dropped
            continue
        index = per_bar.get(bar, 0)
        per_bar[bar] = index + 1
        records.append(_record(event, staff, state, bar, index, parts_by_stem, head_kind, s))
    state["diagnostics"]["ignored_symbols"] += len(ignored)
    return {"records": records, "bar_count": len(bars), "time_signature": state.get("time_signature")}


def _event_bbox(event: dict[str, Any]) -> tuple[float, float, float, float]:
    if "_rest" in event:
        return event["_rest"].bbox
    return _bbox_union([h.bbox for h in event["_heads"]])


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
        return (start, None) if not following else None
    stops = [(e, h) for e, h in ends_at if abs(h.cy - head.cy) <= TIE_SAME_POSITION_SPACES * space]
    if len(stops) == 1 and following and stops[0][0] is following[0]:
        return start, stops[0][0]
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
    if len({len(row) for row in dot_rows}) > 1:
        reason = reason or "dot_rows_disagree"
    if "_rest" in event:
        glyph = event["_rest"]
        record["rest"] = {"glyph": event["_rest_kind"] if event["_rest_kind"] in WRITTEN_VALUES else None,
                          "source": glyph.ident}
        parts["rest_glyph"] = event["_rest_kind"]
    else:
        heads = event["_heads"]
        kinds = sorted({head_kind[h.ident] for h in heads})
        record["kind"] = "chord" if len(heads) > 1 else "note"
        record["notehead"] = {"kind": kinds[0] if len(kinds) == 1 else "mixed", "count": len(heads),
                              "sources": [h.ident for h in heads]}
        parts["kind"] = "note"
        parts["head_kind"] = kinds[0]
        if len(kinds) > 1:
            reason = reason or "mixed_notehead_kinds"
        stem = event["_stem"]
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
    if reason:
        record["status"] = "unread"
        record["reason"] = reason
        return record
    value = WRITTEN_VALUES[written] * (2 - Fraction(1, 2 ** dot_count))
    duration = value
    if record["tuplet"]:
        duration = value * Fraction(record["tuplet"]["normal"], record["tuplet"]["actual"])
    record["written"] = written
    record["value_quarters"] = _frac(value)
    record["duration_quarters"] = _frac(duration)
    return record


# --- document -------------------------------------------------------------------------------

def _bar_checks(records: list[dict[str, Any]], bar_signatures: dict[int, dict[str, Any] | None]) -> list[dict[str, Any]]:
    checks = []
    for bar, signature in sorted(bar_signatures.items()):
        events = [r for r in records if r["bar_index"] == bar]
        unread = sum(1 for r in events if r["status"] != "read")
        total = sum((Fraction(r["duration_quarters"]) for r in events if r["status"] == "read"), Fraction(0))
        check = {"bar_index": bar, "events": len(events), "unread_events": unread, "total_quarters": _frac(total),
                 "time_signature": None, "time_signature_source": None, "expected_quarters": None}
        if signature:
            numerator, denominator = signature["value"]
            expected = Fraction(4 * numerator, denominator)
            check.update(time_signature=f"{numerator}/{denominator}", time_signature_source=signature["source"],
                         expected_quarters=_frac(expected))
        if unread:
            check["status"] = "incomplete"
        elif not signature:
            check["status"] = "time_signature_unread"
        else:
            check["status"] = "match" if total == expected else "mismatch"
        checks.append(check)
    return checks


def read_note_durations(pdf_path: str | Path, pages: tuple[int, int] | None = None,
                        time_signature: tuple[int, int] | None = None) -> dict[str, Any]:
    """Read a duration record for every event on every notation staff of the PDF.

    ``pages`` is an inclusive 1-based page range. ``time_signature`` is a caller-declared
    signature used only for the bar check, and only where none is printed as text.
    """
    import pymupdf  # noqa: PLC0415 - PyMuPDF is only needed when reading a PDF

    path = Path(pdf_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    records: list[dict[str, Any]] = []
    systems = []
    bar_signatures: dict[int, dict[str, Any] | None] = {}
    state: dict[str, Any] = {"bar_offset": 0, "system_number": 0, "time_signature": None,
                             "diagnostics": {"ignored_symbols": 0, "arcs_not_ties": 0, "unassociated_numbers": 0, "label_numbers": 0,
                                             "events_outside_bars": 0, "pages_without_notation_staff": 0}}
    declared = {"value": time_signature, "source": "caller_declared", "sources": []} if time_signature else None
    with pymupdf.open(path) as doc:
        first, last = pages if pages else (1, len(doc))
        for page_index in range(first - 1, min(last, len(doc))):
            symbols = extract_page_symbols(doc[page_index], page_index)
            notation, tab = find_staves(symbols)
            if not notation:
                state["diagnostics"]["pages_without_notation_staff"] += 1
            for system_index, staff in enumerate(sorted(notation, key=lambda st: st.top)):
                state["system_index"] = system_index
                result = _read_staff(staff, symbols, notation + tab, state)
                records.extend(result["records"])
                signature = state["time_signature"] or declared
                for bar in range(result["bar_count"]):
                    bar_signatures[state["bar_offset"] + bar] = signature
                systems.append({"page_index": page_index, "system_index": system_index,
                                "system_number": state["system_number"], "first_bar_index": state["bar_offset"],
                                "bar_count": result["bar_count"], "staff_space": round(staff.space, 4)})
                state["bar_offset"] += result["bar_count"]
                state["system_number"] += 1
    checks = _bar_checks(records, bar_signatures)
    read = sum(1 for r in records if r["status"] == "read")
    reasons: dict[str, int] = {}
    for r in records:
        if r["reason"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    return {
        "schema": SCHEMA,
        "source": {"pdf_sha256": digest, "pages": list(pages) if pages else None},
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
