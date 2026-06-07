from __future__ import annotations
from typing import Any
from .pdf_staff_geometry import (
    NotationStaffGeometry,
    LocalPrimitivesSummary,
    NotationStaffDiagnostics,
    PdfStaffNotationGeometryDiagnostics,
    NotationStaffMorphology
)

def build_notation_diagnostics(
    page: Any,
    page_index: int,
    notation_groups: list[list[Any]]
) -> PdfStaffNotationGeometryDiagnostics:
    staves_diags = []

    drawings = page.get_drawings()
    try:
        text_dict = page.get_text("dict")
    except Exception:
        text_dict = {}

    for system_idx, group in enumerate(notation_groups, start=1):
        line_ys = sorted([round((line.y0 + line.y1) / 2, 3) for line in group])
        x0 = min(min(line.x0, line.x1) for line in group)
        x1 = max(max(line.x0, line.x1) for line in group)
        y0 = min(line_ys)
        y1 = max(line_ys)

        staff_geom = NotationStaffGeometry(
            page_index=page_index,
            system_index=system_idx,
            staff_index=1,
            x0=round(x0, 3),
            y0=round(y0, 3),
            x1=round(x1, 3),
            y1=round(y1, 3),
            line_y_coords=line_ys
        )

        line_count = 0
        curve_count = 0
        rect_count = 0

        y0_padded = y0 - 20.0
        y1_padded = y1 + 20.0

        # Morphology counters
        staff_line_horizontal = 0
        non_staff_horizontal = 0
        vertical_stroke_candidate = 0
        diagonal_stroke_candidate = 0
        rectangle_candidate = 0
        curve_candidate = 0
        text_span_by_font = {}

        x0_limit = staff_geom.x0
        x1_limit = staff_geom.x1
        y0_limit = staff_geom.y0 - 20.0
        y1_limit = staff_geom.y1 + 20.0

        for drawing in drawings:
            draw_rect = drawing.get("rect")
            if draw_rect:
                dx0, dy0, dx1, dy1 = draw_rect
                h_overlap = not (dx1 < x0 or dx0 > x1)
                v_overlap = not (dy1 <= y0_padded or dy0 >= y1_padded)
                if h_overlap and v_overlap:
                    for item in drawing.get("items", []):
                        if not item:
                            continue
                        itype = item[0]
                        if itype == "l":
                            line_count += 1
                        elif itype == "c":
                            curve_count += 1
                        elif itype == "re":
                            rect_count += 1

            # morphology strict containment check
            for item in drawing.get("items", []):
                if not item:
                    continue
                itype = item[0]
                if itype == "l" and len(item) >= 3:
                    p0 = item[1]
                    p1 = item[2]
                    ix0 = min(p0.x, p1.x)
                    ix1 = max(p0.x, p1.x)
                    iy0 = min(p0.y, p1.y)
                    iy1 = max(p0.y, p1.y)
                    if ix0 >= x0_limit and ix1 <= x1_limit and iy0 >= y0_limit and iy1 <= y1_limit:
                        dx = abs(p0.x - p1.x)
                        dy = abs(p0.y - p1.y)
                        if dy <= 1.0:
                            y_coord = (p0.y + p1.y) / 2
                            if any(abs(y_coord - ly) <= 1.0 for ly in line_ys):
                                staff_line_horizontal += 1
                            else:
                                non_staff_horizontal += 1
                        elif dx <= 1.0 and dy >= 5.0:
                            vertical_stroke_candidate += 1
                        else:
                            diagonal_stroke_candidate += 1
                elif itype == "re" and len(item) >= 2:
                    rect = item[1]
                    ix0 = min(rect.x0, rect.x1)
                    ix1 = max(rect.x0, rect.x1)
                    iy0 = min(rect.y0, rect.y1)
                    iy1 = max(rect.y0, rect.y1)
                    if ix0 >= x0_limit and ix1 <= x1_limit and iy0 >= y0_limit and iy1 <= y1_limit:
                        rectangle_candidate += 1
                elif itype == "c" and len(item) >= 2:
                    pts = item[1:]
                    ix0 = min(p.x for p in pts)
                    ix1 = max(p.x for p in pts)
                    iy0 = min(p.y for p in pts)
                    iy1 = max(p.y for p in pts)
                    if ix0 >= x0_limit and ix1 <= x1_limit and iy0 >= y0_limit and iy1 <= y1_limit:
                        curve_candidate += 1

        font_counts = {}
        for block in text_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue
                    span_bbox = span.get("bbox")
                    if span_bbox:
                        sx0, sy0, sx1, sy1 = span_bbox
                        h_overlap = not (sx1 < x0 or sx0 > x1)
                        v_overlap = not (sy1 <= y0_padded or sy0 >= y1_padded)
                        if h_overlap and v_overlap:
                            font_name = span.get("font", "unknown")
                            font_counts[font_name] = font_counts.get(font_name, 0) + 1

                        # strict containment check for morphology
                        if sx0 >= x0_limit and sx1 <= x1_limit and sy0 >= y0_limit and sy1 <= y1_limit:
                            font_name = span.get("font", "unknown")
                            text_span_by_font[font_name] = text_span_by_font.get(font_name, 0) + 1

        primitives_summary = LocalPrimitivesSummary(
            line_count=line_count,
            curve_count=curve_count,
            rect_count=rect_count,
            text_span_count_by_font=font_counts
        )

        morphology = NotationStaffMorphology(
            staff_line_horizontal=staff_line_horizontal,
            non_staff_horizontal=non_staff_horizontal,
            vertical_stroke_candidate=vertical_stroke_candidate,
            diagonal_stroke_candidate=diagonal_stroke_candidate,
            rectangle_candidate=rectangle_candidate,
            curve_candidate=curve_candidate,
            text_span_by_font=text_span_by_font
        )

        staves_diags.append(
            NotationStaffDiagnostics(
                staff=staff_geom,
                primitives=primitives_summary,
                morphology=morphology
            )
        )

    return PdfStaffNotationGeometryDiagnostics(staves=staves_diags)


def extract_notation_diagnostics_dict(page: Any, page_index: int) -> dict[str, Any]:
    """
    Run standard-staff notation group detection and diagnostics building,
    returning a private-safe serialized diagnostics dictionary.

    On diagnostics failure, return the standard private-safe failure status
    without leaking exception details, file paths, raw text, glyph content, or
    coordinate dumps.
    """
    from .pdf_staff_detection import _detect_notation_staff_groups

    try:
        notation_groups = _detect_notation_staff_groups(page)
        notation_diags = build_notation_diagnostics(page, page_index, notation_groups)
        return (
            notation_diags.model_dump()
            if hasattr(notation_diags, "model_dump")
            else notation_diags.dict()
        )
    except Exception:
        return {"staves": [], "status": "pdf_notation_geometry_diagnostics_failed"}
