"""Painted TAB crosses: two crossing diagonals centred on one drawn string."""
from typing import Any

from .pdf import _paints_ink


def drawn_tab_crosses(drawings: list[dict], systems: list[Any],
                     y_offset: float, existing: list[dict]) -> list[dict]:
    found: list[dict] = []
    diagonals = [(index, item[1], item[2])
                 for index, drawing in enumerate(drawings)
                 if drawing.get("type") == "s"
                 and _paints_ink(drawing.get("color"), drawing.get("stroke_opacity"))
                 for item in drawing.get("items", []) if item[0] == "l"
                 and abs(item[1].x - item[2].x) > 0
                 and abs(abs(item[1].x - item[2].x) - abs(item[1].y - item[2].y))
                 <= 0.1 * abs(item[1].x - item[2].x)]
    for index, a, b in diagonals:
        # Each diagonal runs corner to corner in the same square. A bow tie,
        # a bend arrow or two adjacent strokes cannot satisfy this contact.
        x0, x1 = sorted((float(a.x), float(b.x)))
        y0, y1 = sorted((float(a.y), float(b.y)))
        size = x1 - x0
        if size <= 0 or abs(y1 - y0 - size) > 0.1 * size:
            continue
        partners = [(j, c, d) for j, c, d in diagonals
                    if (a.x - b.x) * (a.y - b.y) * (c.x - d.x) * (c.y - d.y) < 0
                    and abs(min(c.x, d.x) - x0) <= 0.1 * size
                    and abs(max(c.x, d.x) - x1) <= 0.1 * size
                    and abs(min(c.y, d.y) - y0) <= 0.1 * size
                    and abs(max(c.y, d.y) - y1) <= 0.1 * size]
        if not partners:
            continue
        y0, y1 = y0 + y_offset, y1 + y_offset
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        owners = [s for s in systems if s.x0 <= cx <= s.x1
                  and 0.35 * s.line_spacing <= size <= 0.85 * s.line_spacing
                  and min(abs(cy - y) for y in s.line_ys) <= 0.15 * s.line_spacing]
        if len(owners) != 1:
            continue
        # Identical paint and a text-plus-vector representation are one mark.
        if any(abs((p["x0"] + p["x1"]) / 2 - cx) <= 0.2 * size
               and abs((p["y0"] + p["y1"]) / 2 - cy) <= 0.2 * size
               for p in found + [p for p in existing if p["text"].strip().lower() in {"x", "×"}]):
            continue
        found.append(dict(text="x", x0=x0, x1=x1, y0=y0, y1=y1,
                          word_index=None, block_no=None, line_no=None, word_no=None,
                          vector_drawing_index=index))
    return found
