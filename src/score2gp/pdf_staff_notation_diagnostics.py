from __future__ import annotations
from typing import Any
from .pdf_staff_geometry import (
    NotationStaffGeometry,
    LocalPrimitivesSummary,
    NotationStaffDiagnostics,
    PdfStaffNotationGeometryDiagnostics,
    NotationStaffMorphology,
    XAlignedClusterAggregateDiagnostics,
    ClusterPrimitiveCountSummary,
    StaffLeftMarginAggregateDiagnostics
)
from dataclasses import dataclass
import statistics

@dataclass(frozen=True)
class PrimitiveGeometry:
    type: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2.0

def cluster_x_aligned_primitives(primitives: list[PrimitiveGeometry], staff_space: float) -> list[list[PrimitiveGeometry]]:
    if not primitives or staff_space <= 0.0:
        return []

    sorted_prims = sorted(primitives, key=lambda p: (p.center_x, min(p.y0, p.y1)))
    clusters = []
    current_cluster = [sorted_prims[0]]

    def get_cluster_center_x(cluster: list[PrimitiveGeometry]) -> float:
        return (min(p.x0 for p in cluster) + max(p.x1 for p in cluster)) / 2.0

    for prim in sorted_prims[1:]:
        cluster_center_x = get_cluster_center_x(current_cluster)
        dx_normalized = abs(prim.center_x - cluster_center_x) / staff_space

        c_x0 = min(p.x0 for p in current_cluster)
        c_x1 = max(p.x1 for p in current_cluster)

        is_compact_prim = (prim.x1 - prim.x0) <= 2.0 * staff_space
        is_compact_cluster = (c_x1 - c_x0) <= 2.0 * staff_space

        overlap = False
        if is_compact_prim and is_compact_cluster:
            overlap = not (prim.x1 < c_x0 - 0.5 * staff_space or prim.x0 > c_x1 + 0.5 * staff_space)

        if dx_normalized <= 0.5 or overlap:
            current_cluster.append(prim)
        else:
            clusters.append(current_cluster)
            current_cluster = [prim]

    if current_cluster:
        clusters.append(current_cluster)

    return clusters

def build_notation_diagnostics(
    page: Any,
    page_index: int,
    notation_groups: list[list[Any]]
) -> PdfStaffNotationGeometryDiagnostics:
    from .pdf_staff_geometry import SystemConnectorDiagnostics

    staves_diags = []
    system_connectors = []

    drawings = page.get_drawings()
    try:
        text_dict = page.get_text("dict")
    except Exception:
        text_dict = {}

    # Pre-calculate bounds for all notation groups
    group_bounds = []
    for group in notation_groups:
        line_ys = sorted([round((line.y0 + line.y1) / 2, 3) for line in group])
        x0 = min(min(line.x0, line.x1) for line in group)
        x1 = max(max(line.x0, line.x1) for line in group)
        y0 = min(line_ys)
        y1 = max(line_ys)
        if len(line_ys) >= 2:
            gaps = [line_ys[i+1] - line_ys[i] for i in range(len(line_ys)-1)]
            staff_space = statistics.median(gaps)
        else:
            staff_space = 0.0
        group_bounds.append({"line_ys": line_ys, "x0": x0, "x1": x1, "y0": y0, "y1": y1, "staff_space": staff_space})

    # Detect connectors
    # We look for vertical lines or curves near the left margin (x0 - 20 to x0 + 10) that span across multiple groups
    group_system_mapping = {i: {"system_index": i + 1, "staff_index": 1} for i in range(len(notation_groups))}
    current_system_idx = 1

    # We will build connected systems
    connected_systems = []
    i = 0
    while i < len(notation_groups):
        system_group_indices = [i]
        j = i + 1

        while j < len(notation_groups):
            # Check if there is a connector between group j-1 and group j
            g_prev = group_bounds[j-1]
            g_curr = group_bounds[j]

            # Connector must be roughly at the left edge
            left_x = min(g_prev["x0"], g_curr["x0"])

            connector_found = False
            connector_info = None

            # Scan drawings for a vertical line or curve spanning from g_prev["y0"] to g_curr["y1"]
            for drawing in drawings:
                draw_rect = drawing.get("rect")
                if not draw_rect: continue
                dx0, dy0, dx1, dy1 = draw_rect

                # Check if this drawing spans the two groups vertically and is at the left margin
                if dx1 < left_x - 30 or dx0 > left_x + 10:
                    continue

                if dy0 <= g_prev["y0"] + 5 and dy1 >= g_curr["y1"] - 5:
                    # It spans! Check primitive type
                    for item in drawing.get("items", []):
                        if not item: continue
                        itype = item[0]
                        if itype == "l" and len(item) >= 3:
                            p0, p1 = item[1], item[2]
                            ix0, ix1 = min(p0.x, p1.x), max(p0.x, p1.x)
                            iy0, iy1 = min(p0.y, p1.y), max(p0.y, p1.y)
                            if ix1 - ix0 <= 2.0 and iy1 - iy0 >= (g_curr["y1"] - g_prev["y0"]) - 10:
                                connector_found = True
                                connector_info = ("leading_barline", ix0, iy0, ix1, iy1)
                                break
                        elif itype == "c" and len(item) >= 2:
                            pts = item[1:]
                            iy0, iy1 = min(p.y for p in pts), max(p.y for p in pts)
                            ix0, ix1 = min(p.x for p in pts), max(p.x for p in pts)
                            if iy1 - iy0 >= (g_curr["y1"] - g_prev["y0"]) - 10:
                                connector_found = True
                                connector_info = ("brace_curve", ix0, iy0, ix1, iy1) # or bracket
                                break

                if connector_found:
                    break

            if connector_found:
                system_group_indices.append(j)
                # We could add to system_connectors here, but it's better to add one connector for the whole system later
                j += 1
            else:
                break

        connected_systems.append(system_group_indices)
        i = j

    global_staff_idx = 0
    for system_idx, indices in enumerate(connected_systems, start=1):
        if len(indices) > 1:
            # We found a multi-staff system, let's find the bounding connector for the whole system
            g_first = group_bounds[indices[0]]
            g_last = group_bounds[indices[-1]]
            left_x = min(group_bounds[idx]["x0"] for idx in indices)

            best_connector = ("unknown_connector", left_x, g_first["y0"], left_x, g_last["y1"])
            for drawing in drawings:
                draw_rect = drawing.get("rect")
                if not draw_rect: continue
                dx0, dy0, dx1, dy1 = draw_rect
                if dx1 < left_x - 30 or dx0 > left_x + 10: continue
                if dy0 <= g_first["y0"] + 5 and dy1 >= g_last["y1"] - 5:
                    for item in drawing.get("items", []):
                        if not item: continue
                        itype = item[0]
                        if itype == "l" and len(item) >= 3:
                            p0, p1 = item[1], item[2]
                            ix0, ix1 = min(p0.x, p1.x), max(p0.x, p1.x)
                            iy0, iy1 = min(p0.y, p1.y), max(p0.y, p1.y)
                            if ix1 - ix0 <= 2.0 and iy1 - iy0 >= (g_last["y1"] - g_first["y0"]) - 10:
                                best_connector = ("leading_barline", ix0, iy0, ix1, iy1)
                                break
                        elif itype == "c" and len(item) >= 2:
                            pts = item[1:]
                            iy0, iy1 = min(p.y for p in pts), max(p.y for p in pts)
                            ix0, ix1 = min(p.x for p in pts), max(p.x for p in pts)
                            if iy1 - iy0 >= (g_last["y1"] - g_first["y0"]) - 10:
                                best_connector = ("brace_curve", ix0, iy0, ix1, iy1)
                                break

            system_connectors.append(
                SystemConnectorDiagnostics(
                    connected_staff_indices=[global_staff_idx + k + 1 for k in range(len(indices))],
                    connector_kind=best_connector[0],
                    x0=round(best_connector[1], 3),
                    y0=round(best_connector[2], 3),
                    x1=round(best_connector[3], 3),
                    y1=round(best_connector[4], 3)
                )
            )

        for staff_idx_in_sys, idx in enumerate(indices, start=1):
            group_system_mapping[idx] = {"system_index": system_idx, "staff_index": staff_idx_in_sys}
            global_staff_idx += 1

    for idx, group in enumerate(notation_groups):
        mapping = group_system_mapping[idx]
        system_idx = mapping["system_index"]
        staff_idx = mapping["staff_index"]
        gb = group_bounds[idx]

        line_ys = gb["line_ys"]
        x0 = gb["x0"]
        x1 = gb["x1"]
        y0 = gb["y0"]
        y1 = gb["y1"]
        staff_space = gb["staff_space"]

        staff_geom = NotationStaffGeometry(
            page_index=page_index,
            system_index=system_idx,
            staff_index=staff_idx,
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

        primitives_for_clustering = []

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
                                ptype = "staff_line_horizontal"
                            else:
                                non_staff_horizontal += 1
                                ptype = "non_staff_horizontal"
                        elif dx <= 1.0 and dy >= 5.0:
                            vertical_stroke_candidate += 1
                            ptype = "vertical_stroke_candidate"
                        else:
                            diagonal_stroke_candidate += 1
                            ptype = "diagonal_stroke_candidate"
                        if ptype != "staff_line_horizontal":
                            primitives_for_clustering.append(PrimitiveGeometry(ptype, ix0, iy0, ix1, iy1))
                elif itype == "re" and len(item) >= 2:
                    rect = item[1]
                    ix0 = min(rect.x0, rect.x1)
                    ix1 = max(rect.x0, rect.x1)
                    iy0 = min(rect.y0, rect.y1)
                    iy1 = max(rect.y0, rect.y1)
                    if ix0 >= x0_limit and ix1 <= x1_limit and iy0 >= y0_limit and iy1 <= y1_limit:
                        rectangle_candidate += 1
                        primitives_for_clustering.append(PrimitiveGeometry("rect", ix0, iy0, ix1, iy1))
                elif itype == "c" and len(item) >= 2:
                    pts = item[1:]
                    ix0 = min(p.x for p in pts)
                    ix1 = max(p.x for p in pts)
                    iy0 = min(p.y for p in pts)
                    iy1 = max(p.y for p in pts)
                    if ix0 >= x0_limit and ix1 <= x1_limit and iy0 >= y0_limit and iy1 <= y1_limit:
                        curve_candidate += 1
                        primitives_for_clustering.append(PrimitiveGeometry("curve", ix0, iy0, ix1, iy1))

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
                            primitives_for_clustering.append(PrimitiveGeometry("text_span", sx0, sy0, sx1, sy1))

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

        if len(line_ys) >= 2:
            gaps = [line_ys[i+1] - line_ys[i] for i in range(len(line_ys)-1)]
            staff_space = statistics.median(gaps)
        else:
            staff_space = 0.0

        clustering_diags = None
        left_margin_diags = None
        if staff_space > 0.0:
            clusters = cluster_x_aligned_primitives(primitives_for_clustering, staff_space)
            x_aligned_cluster_count = len(clusters)
            max_prims = 0
            clusters_with_vertical = 0
            max_vspan = 0.0

            lines_total = 0
            curves_total = 0
            rects_total = 0
            text_spans_total = 0

            for cluster in clusters:
                prim_count = len(cluster)
                if prim_count > max_prims:
                    max_prims = prim_count

                c_x0 = min(p.x0 for p in cluster)
                c_x1 = max(p.x1 for p in cluster)
                c_y0 = min(p.y0 for p in cluster)
                c_y1 = max(p.y1 for p in cluster)
                vspan = (c_y1 - c_y0) / staff_space
                if vspan > max_vspan:
                    max_vspan = vspan

                has_vertical = False
                compact_members = [p for p in cluster if p.type != "vertical_stroke_candidate"]

                for p in cluster:
                    if "line" in p.type or "stroke" in p.type or "horizontal" in p.type:
                        lines_total += 1
                    elif p.type == "curve":
                        curves_total += 1
                    elif p.type == "rect":
                        rects_total += 1
                    elif p.type == "text_span":
                        text_spans_total += 1

                    if not has_vertical and p.type == "vertical_stroke_candidate":
                        height_norm = abs(p.y1 - p.y0) / staff_space
                        if compact_members and height_norm >= 2.5:
                            cc_x0 = min(cm.x0 for cm in compact_members)
                            cc_x1 = max(cm.x1 for cm in compact_members)
                            cc_y0 = min(cm.y0 for cm in compact_members)
                            cc_y1 = max(cm.y1 for cm in compact_members)
                            cc_center_x = (cc_x0 + cc_x1) / 2.0

                            dx_norm = abs(p.center_x - cc_center_x) / staff_space
                            x_overlap = not (p.x1 < cc_x0 - staff_space or p.x0 > cc_x1 + staff_space)
                            y_overlap = not (p.y1 < cc_y0 - staff_space or p.y0 > cc_y1 + staff_space)
                            if dx_norm <= 1.0 and x_overlap and y_overlap:
                                has_vertical = True

                if has_vertical:
                    clusters_with_vertical += 1

            clustering_diags = XAlignedClusterAggregateDiagnostics(
                x_aligned_cluster_count=x_aligned_cluster_count,
                max_primitives_per_x_aligned_cluster=max_prims,
                clusters_with_vertical_stroke_candidate=clusters_with_vertical,
                max_cluster_vertical_span_staff_spaces=round(max_vspan, 3),
                cluster_primitive_count_summary=ClusterPrimitiveCountSummary(
                    lines_total=lines_total,
                    curves_total=curves_total,
                    rects_total=rects_total,
                    text_spans_total=text_spans_total
                )
            )

            margin_x_limit = staff_geom.x0 + (10.0 * staff_space)

            margin_curves = 0
            margin_vertical_strokes = 0
            margin_rects = 0

            for p in primitives_for_clustering:
                if staff_geom.x0 <= p.center_x <= margin_x_limit:
                    if p.type == "curve":
                        margin_curves += 1
                    elif p.type == "vertical_stroke_candidate":
                        margin_vertical_strokes += 1
                    elif p.type == "rect":
                        margin_rects += 1

            margin_font_counts = {}
            for block in text_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if not text.strip():
                            continue
                        span_bbox = span.get("bbox")
                        if span_bbox:
                            sx0, sy0, sx1, sy1 = span_bbox
                            # strict containment check within notation staff box
                            if sx0 >= x0_limit and sx1 <= x1_limit and sy0 >= y0_limit and sy1 <= y1_limit:
                                center_x = (sx0 + sx1) / 2.0
                                if staff_geom.x0 <= center_x <= margin_x_limit:
                                    font_name = span.get("font", "unknown")
                                    margin_font_counts[font_name] = margin_font_counts.get(font_name, 0) + 1

            margin_text_span_count = sum(margin_font_counts.values())
            distinct_font_count = len(margin_font_counts)
            max_spans = max(margin_font_counts.values()) if margin_font_counts else 0

            left_margin_diags = StaffLeftMarginAggregateDiagnostics(
                margin_x_threshold_staff_spaces=10.0,
                text_span_count=margin_text_span_count,
                distinct_font_count=distinct_font_count,
                max_text_spans_for_single_font=max_spans,
                curve_candidate_count=margin_curves,
                vertical_stroke_candidate_count=margin_vertical_strokes,
                rectangle_candidate_count=margin_rects
            )

        staves_diags.append(
            NotationStaffDiagnostics(
                staff=staff_geom,
                primitives=primitives_summary,
                morphology=morphology,
                clustering=clustering_diags,
                left_margin=left_margin_diags
            )
        )

    return PdfStaffNotationGeometryDiagnostics(staves=staves_diags, system_connectors=system_connectors)


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
