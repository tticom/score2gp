"""Read the slide type a drawn TAB mark shows, or record why it cannot be read.

A slide on a TAB staff is drawn as a short diagonal stroke touching a fret digit.
Where the stroke is anchored decides the family, and a slur arc over the pair decides
the connecting type:

* stroke ends at a digit, nothing before it in the system -> slide into the note
* stroke joins two digits on one string, one slur arc over both -> legato slide
* stroke joins two digits on one string, no arc over them -> shift slide
* anything else (an end bound to no digit, endpoints on different strings, several
  candidate arcs) -> refused with a reason code; no slide type is guessed.

The reading uses only drawn geometry. Strokes and arcs are page-local; digit boxes
are in the stacked page coordinates TabRaw uses, so the page offset is applied.
"""

from __future__ import annotations

from typing import Any

SLIDE_MARK_NOT_EXTRACTED = "slide_mark_not_extracted"
SLIDE_NOT_WRITTEN = "slide_not_written"

REASON_END_UNBOUND = "slide_endpoint_not_bound_to_digit"
REASON_DIFFERENT_STRINGS = "slide_endpoints_on_different_strings"
REASON_CROSS_BAR = "slide_endpoints_in_different_bars"
REASON_SLUR_AMBIGUOUS = "slide_slur_evidence_ambiguous"
REASON_NOTE_NOT_FOUND = "slide_endpoint_note_not_found"
REASON_TYPE_NOT_READ = "slide_type_not_read"
REASON_LABEL_WITHOUT_MARK = "slide_label_without_drawn_mark"


def slur_arcs(drawings: list[dict[str, Any]]) -> list[tuple[float, float, float]]:
    """Page-local (x0, y, x1) of drawings made only of curves whose end points are far apart and level.

    End points, not the control-point box, give where a slur starts and stops; noteheads and
    clef parts are closed curves with end points close together and are excluded.
    """
    arcs = []
    for drawing in drawings:
        items = drawing.get("items", [])
        if not items or len(items) > 4 or any(item[0] != "c" for item in items):
            continue
        points = [point for item in items for point in (item[1], item[-1])]
        xs, ys = [p.x for p in points], [p.y for p in points]
        span = max(xs) - min(xs)
        if span >= 6.0 and max(ys) - min(ys) <= span / 2:
            arcs.append((min(xs), sum(ys) / len(ys), max(xs)))
    return arcs


def _reach(box: dict[str, float]) -> float:
    """How far a stroke end may sit from a digit's box: half the digit's advance width.

    A narrow glyph ("1") prints a box narrower than its advance; digits are half as wide as tall.
    """
    return max(box["x1"] - box["x0"], (box["y1"] - box["y0"]) / 2) / 2


def _binds_left(stroke: dict[str, Any], digit: dict[str, Any], offset: float) -> bool:
    """The stroke starts just right of the digit's printed box, at the box's height."""
    x0, y0, _, y1 = stroke["bbox"]
    box = digit["bbox"]
    endpoint_y = y0 if stroke["direction"] == "down" else y1
    return (0 <= x0 - box["x1"] <= _reach(box)
            and box["y0"] - offset <= endpoint_y <= box["y1"] - offset)


def _binds_right(stroke: dict[str, Any], digit: dict[str, Any], offset: float) -> bool:
    """The stroke ends just left of the digit's printed box, at the box's height."""
    _, y0, x1, y1 = stroke["bbox"]
    box = digit["bbox"]
    endpoint_y = y0 if stroke["direction"] == "up" else y1
    return (0 < box["x0"] - x1 <= _reach(box)
            and box["y0"] - offset <= endpoint_y <= box["y1"] - offset)


def _arcs_over_pair(arcs, stroke, left, right, offset: float) -> list[tuple[float, float, float]]:
    lines = left.get("raw", {}).get("tab_line_ys") or []
    gap = (lines[-1] - lines[0]) / 5 if len(lines) == 6 else 6.4
    lbox, rbox = left["bbox"], right["bbox"]
    _, sy0, _, sy1 = stroke["bbox"]
    return [a for a in arcs
            if a[0] <= lbox["x1"] and a[2] >= rbox["x0"]
            and sy0 - 2 * gap <= a[1] <= sy1 + 2 * gap]


def read_slide_marks(
    digits: list[dict[str, Any]],
    strokes: list[dict[str, Any]],
    arcs: list[tuple[float, float, float]],
    page_offset: float,
) -> list[dict[str, Any]]:
    """One reading per diagonal stroke that touches a TAB digit; strokes touching none are not slide marks.

    ``status`` is ``read`` with a ``style``/``direction``, or ``refused`` with a ``reason``.
    """
    marks = []
    for index, stroke in enumerate(strokes):
        lefts = [d for d in digits if _binds_left(stroke, d, page_offset)]
        rights = [d for d in digits if _binds_right(stroke, d, page_offset)]
        if not lefts and not rights:
            continue
        x0, y0, x1, y1 = stroke["bbox"]
        mark: dict[str, Any] = {"index": index, "bbox": [x0, y0, x1, y1], "direction": stroke["direction"]}
        anchor = (lefts or rights)[0]
        mark["anchor_candidate_id"] = anchor["id"]
        width = anchor["bbox"]["x1"] - anchor["bbox"]["x0"]
        if len(lefts) > 1 or len(rights) > 1 or (lefts and rights and lefts[0] is rights[0]):
            mark.update(status="refused", reason=REASON_END_UNBOUND, placement="unbound")
        elif rights and not lefts:
            target = rights[0]
            preceded = any(d.get("system_index") == target.get("system_index")
                           and d["bbox"]["x1"] <= x0 for d in digits)
            lead_len = width / 2 <= x1 - x0 <= 2 * width
            short = (y1 - y0) <= (target["bbox"]["y1"] - target["bbox"]["y0"])
            if not preceded and lead_len and short:
                mark.update(status="read", style="slide-in", placement="before-note",
                            target_candidate_id=target["id"])
            else:
                mark.update(status="refused", reason=REASON_END_UNBOUND, placement="unbound")
        elif lefts and not rights:
            mark.update(status="refused", reason=REASON_END_UNBOUND, placement="after-note",
                        source_candidate_id=lefts[0]["id"])
        else:
            left, right = lefts[0], rights[0]
            mark.update(placement="between-notes", source_candidate_id=left["id"],
                        target_candidate_id=right["id"])
            if (left.get("system_index"), left.get("bar_index")) != (right.get("system_index"), right.get("bar_index")):
                mark.update(status="refused", reason=REASON_CROSS_BAR)
            elif left.get("string") != right.get("string"):
                mark.update(status="refused", reason=REASON_DIFFERENT_STRINGS)
            else:
                over = _arcs_over_pair(arcs, stroke, left, right, page_offset)
                if len(over) > 1:
                    mark.update(status="refused", reason=REASON_SLUR_AMBIGUOUS)
                else:
                    mark.update(status="read", style="legato" if over else "shift")
        marks.append(mark)
    return marks
