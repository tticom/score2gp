"""Read a labelled upward bend whose shaft otherwise becomes an unread event.

The cubic, triangular arrow, amount label and owning head must agree. This
bounded form excludes releases, pre-bends, multiple sounding heads and unlabelled curves. A
successful old bar has no unread shaft to replace and is left unchanged.
"""

from typing import Any


BEND_AMOUNTS = {"1/4": 0.5, "1/2": 1.0, "Full": 2.0}


def _upward_shaft(glyph: Any, space: float):
    items = glyph.drawing.get("items", [])
    if (glyph.filled or len(items) != 1 or items[0][0] != "c"
            or not 0 < float(glyph.drawing.get("width") or 0) <= 0.2 * space):
        return None
    points = items[0][1:]
    if len(points) != 4:
        return None
    a, b, c, d = points
    tolerance = 0.05 * space
    if not (d.x - a.x >= 0.5 * space and a.y - d.y >= 0.5 * space
            and all(p.x <= q.x + tolerance and p.y >= q.y - tolerance
                    for p, q in zip(points, points[1:]))
            and abs(b.y - a.y) <= tolerance and abs(d.x - c.x) <= tolerance):
        return None
    return a, d


def _upward_arrow(glyph: Any, end: Any, space: float) -> bool:
    items = glyph.drawing.get("items", [])
    if not glyph.filled or len(items) != 3 or any(i[0] != "l" for i in items):
        return False
    vertices = {(float(p.x), float(p.y)) for i in items for p in i[1:]}
    if len(vertices) != 3:
        return False
    tip, left, right = sorted(vertices, key=lambda p: (p[1], p[0]))
    tolerance = 0.05 * space
    # The two lower vertices form a horizontal base at the shaft's upper end.
    return (0 < glyph.w <= space and 0 < glyph.h <= space
            and abs(left[1] - right[1]) <= tolerance and tip[1] < left[1]
            and min(left[0], right[0]) < tip[0] < max(left[0], right[0])
            and abs(tip[0] - end.x) <= tolerance
            and abs(left[1] - end.y) <= tolerance)


def read_simple_bends(events: list[dict[str, Any]], glyphs, texts,
                      head_kinds: dict[str, str], space: float, bars) -> list[dict[str, Any]]:
    """Replace only a positively identified unread shaft with its owning bend.

    The value is the printed label, not a pitch difference or a bar-total
    repair. Requiring an actual unread event protects previously written bars.
    No mutation is made unless every ownership and form check succeeds.
    """
    unread = {e["_rest"].ident for e in events if e.get("_rest") is not None
              and (e.get("_unread") == "symbol_unclassified" or e.get("_rest_kind") == "unidentified")}
    candidates: dict[int, list[tuple[Any, ...]]] = {}
    blocked: set[int] = set()
    lowest = {bar: max((h.bbox[3] for e in events if e.get("_bar") == bar
                       for h in e.get("_heads", [])), default=float("-inf"))
              for bar in range(len(bars))}
    for shaft in glyphs:
        ends = _upward_shaft(shaft, space)
        if ends is None:
            continue
        start, end = ends
        bar = next((i for i, (left, right) in enumerate(bars) if left <= start.x < end.x <= right), None)
        # A repeated bend diagram above the TAB row is below every notation
        # head. It is not an additional notation bend or an unresolved owner.
        if bar is None or start.y > lowest[bar] + 0.2 * space:
            continue
        arrows = [g for g in glyphs if _upward_arrow(g, end, space)]
        if len(arrows) != 1:
            continue
        arrow = arrows[0]
        labels = [t for t in texts if t.text in BEND_AMOUNTS
                  and t.bbox[0] <= end.x <= t.bbox[2]
                  and -0.2 * space <= arrow.bbox[1] - t.bbox[3] <= 0.6 * space]
        if len(labels) != 1:
            blocked.add(bar)
            continue
        owners = []
        for event in events:
            sounding = [h for h in event.get("_heads", []) if head_kinds[h.ident] != "cross"]
            if (event.get("_bar") != bar or len(sounding) != 1 or event.get("_stem") is None
                    or event.get("_grace") or event.get("_unread")):
                continue
            head = sounding[0]
            if (-0.2 * space <= start.x - head.bbox[2] <= 0.2 * space
                    and head.bbox[1] - 0.2 * space <= start.y <= head.bbox[3] + 0.2 * space):
                owners.append((event, head))
        if len(owners) != 1:
            blocked.add(bar)
            continue
        owner, head = owners[0]
        # The shaft must end before the next note. Longer curves, or a shaft
        # crossing a barline, require another reading and stay refused.
        following = [e for e in events if e.get("_heads") and e["_cx"] > owner["_cx"]]
        if following and end.x >= min(e["_heads"][0].bbox[0] for e in following):
            blocked.add(bar)
            continue
        candidates.setdefault(bar, []).append((shaft, arrow, labels[0], owner, head))

    removed: set[str] = set()
    for bar, marks in candidates.items():
        if bar in blocked or not any(m[0].ident in unread for m in marks):
            continue
        # Read the complete bar's bends, including a shaft the old reader
        # ignored outside rest reach. Otherwise a new bar could lose a bend.
        labels = {t.ident for t in texts if t.text in BEND_AMOUNTS
                  and bars[bar][0] <= t.cx <= bars[bar][1] and t.bbox[3] <= lowest[bar]}
        if (labels != {m[2].ident for m in marks}
                or len({id(m[3]) for m in marks}) != len(marks)):
            continue
        for shaft, arrow, label, owner, head in marks:
            owner["_bend"] = {"semitones": BEND_AMOUNTS[label.text], "label": label.text,
                              "head_source": head.ident,
                              "sources": [shaft.ident, arrow.ident, label.ident]}
            removed.update((shaft.ident, arrow.ident))
    return [e for e in events if getattr(e.get("_rest"), "ident", None) not in removed]
