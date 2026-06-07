from __future__ import annotations
from typing import Any
from .pdf_staff_geometry import (
    NotationStaffGeometry,
    LocalPrimitivesSummary,
    NotationStaffDiagnostics,
    PdfStaffNotationGeometryDiagnostics
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
                            
        primitives_summary = LocalPrimitivesSummary(
            line_count=line_count,
            curve_count=curve_count,
            rect_count=rect_count,
            text_span_count_by_font=font_counts
        )
        
        staves_diags.append(
            NotationStaffDiagnostics(
                staff=staff_geom,
                primitives=primitives_summary
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
    from .pdf import _detect_notation_staff_groups

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
