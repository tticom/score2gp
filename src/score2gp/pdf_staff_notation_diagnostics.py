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
    StaffLeftMarginAggregateDiagnostics,
    PrimitiveGeometryEvidence,
    XAlignedPrimitiveClusterEvidence,
    WholeNoteCandidateDiagnostics
)
from dataclasses import dataclass
import statistics
from .pdf_geometry_candidate_extractor import PdfGeometryCandidateExtractor

def _extract_note_candidates(page: Any) -> tuple[list[WholeNoteCandidateDiagnostics], list[HalfNoteCandidateDiagnostics]]:
    whole_candidates = []
    half_candidates = []
    drawings = page.get_drawings()

    vertical_lines = []
    for draw in drawings:
        for item in draw.get("items", []):
            if item[0] == 'l':
                p0, p1 = item[1], item[2]
                dx = abs(p0.x - p1.x)
                dy = abs(p0.y - p1.y)
                if dy >= 5.0 and dx <= 2.0:
                    vertical_lines.append({
                        "x0": min(p0.x, p1.x),
                        "y0": min(p0.y, p1.y),
                        "x1": max(p0.x, p1.x),
                        "y1": max(p0.y, p1.y)
                    })

    for draw in drawings:
        rect = draw.get("rect")
        if not rect:
            continue

        if hasattr(rect, "x0"):
            x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
        elif isinstance(rect, tuple) and len(rect) == 4:
            x0, y0, x1, y1 = rect
        else:
            continue

        w = x1 - x0
        h = y1 - y0
        if h == 0 or w == 0:
            continue

        aspect = w / h

        items = draw.get("items", [])
        c_count = sum(1 for item in items if item[0] == 'c')

        if 1.2 <= aspect <= 2.0 and c_count >= 2:
            is_hollow = not draw.get("fill")
            if is_hollow:
                has_stem = False
                margin_x = 3.0
                margin_y = 5.0
                for line in vertical_lines:
                    near_left = abs(line["x0"] - x0) <= margin_x
                    near_right = abs(line["x0"] - x1) <= margin_x
                    if near_left or near_right:
                        if not (line["y1"] < y0 - margin_y or line["y0"] > y1 + margin_y):
                            has_stem = True
                            break

                if not has_stem:
                    whole_candidates.append(WholeNoteCandidateDiagnostics(
                        bbox=[round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
                        width=round(w, 3),
                        height=round(h, 3),
                        aspect_ratio=round(aspect, 3)
                    ))
                else:
                    half_candidates.append(HalfNoteCandidateDiagnostics(
                        bbox=[round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
                        width=round(w, 3),
                        height=round(h, 3),
                        aspect_ratio=round(aspect, 3)
                    ))
    return whole_candidates, half_candidates

def _extract_whole_note_candidates(page: Any) -> list[WholeNoteCandidateDiagnostics]:
    return _extract_note_candidates(page)[0]

def _extract_half_note_candidates(page: Any) -> list[HalfNoteCandidateDiagnostics]:
    return _extract_note_candidates(page)[1]

@dataclass(frozen=True)
class PrimitiveGeometry:
    type: str
    x0: float
    y0: float
    x1: float
    y1: float
    font_name: str | None = None
    font_size: float | None = None

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

def _to_evidence(p: PrimitiveGeometry) -> PrimitiveGeometryEvidence | None:
    kind_map = {
        "text_span": "text_span",
        "curve": "curve",
        "vertical_stroke_candidate": "vertical_stroke",
        "diagonal_stroke_candidate": "diagonal_stroke",
        "non_staff_horizontal": "horizontal_stroke",
        "rect": "rectangle"
    }
    k = kind_map.get(p.type)
    if not k:
        raise ValueError(f"Primitive type {p.type} cannot be serialized to evidence")
    return PrimitiveGeometryEvidence(
        x0=round(p.x0, 3),
        y0=round(p.y0, 3),
        x1=round(p.x1, 3),
        y1=round(p.y1, 3),
        kind=k,  # type: ignore
        font_name=p.font_name,
        font_size=round(p.font_size, 3) if p.font_size is not None else None
    )

def _notation_group_bounds(group: list[Any]) -> dict[str, Any]:
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
    return {"line_ys": line_ys, "x0": x0, "x1": x1, "y0": y0, "y1": y1, "staff_space": staff_space}

def _find_system_connector_between_groups(drawings: list[Any], g_prev: dict[str, Any], g_curr: dict[str, Any]) -> tuple[str, float, float, float, float] | None:
    left_x = min(g_prev["x0"], g_curr["x0"])
    for drawing in drawings:
        draw_rect = drawing.get("rect")
        if not draw_rect: continue
        dx0, dy0, dx1, dy1 = draw_rect
        if dx1 < left_x - 30 or dx0 > left_x + 10:
            continue
        if dy0 <= g_prev["y0"] + 5 and dy1 >= g_curr["y1"] - 5:
            for item in drawing.get("items", []):
                if not item: continue
                itype = item[0]
                if itype == "l" and len(item) >= 3:
                    p0, p1 = item[1], item[2]
                    ix0, ix1 = min(p0.x, p1.x), max(p0.x, p1.x)
                    iy0, iy1 = min(p0.y, p1.y), max(p0.y, p1.y)
                    if ix1 - ix0 <= 2.0 and iy1 - iy0 >= (g_curr["y1"] - g_prev["y0"]) - 10:
                        return ("leading_barline", ix0, iy0, ix1, iy1)
                elif itype == "c" and len(item) >= 2:
                    pts = item[1:]
                    iy0, iy1 = min(p.y for p in pts), max(p.y for p in pts)
                    ix0, ix1 = min(p.x for p in pts), max(p.x for p in pts)
                    if iy1 - iy0 >= (g_curr["y1"] - g_prev["y0"]) - 10:
                        return ("brace_curve", ix0, iy0, ix1, iy1)
    return None

def _group_notation_groups_by_system_connectors(drawings: list[Any], group_bounds: list[dict[str, Any]]) -> tuple[list[list[int]], list[dict[str, Any]]]:
    connected_systems = []
    connectors_found = []
    
    i = 0
    while i < len(group_bounds):
        system_group_indices = [i]
        j = i + 1
        
        system_connector = None
        while j < len(group_bounds):
            g_prev = group_bounds[j-1]
            g_curr = group_bounds[j]
            conn = _find_system_connector_between_groups(drawings, g_prev, g_curr)
            if conn:
                system_group_indices.append(j)
                if not system_connector:
                    system_connector = conn
                j += 1
            else:
                break
                
        connected_systems.append(system_group_indices)
        if len(system_group_indices) > 1 and system_connector:
            connectors_found.append({
                "indices": system_group_indices,
                "connector_info": system_connector
            })
        i = j
        
    return connected_systems, connectors_found

def build_notation_diagnostics(
    page: Any,
    page_index: int,
    notation_groups: list[list[Any]]
) -> PdfStaffNotationGeometryDiagnostics:
    from .pdf_staff_geometry import SystemConnectorDiagnostics

    staves_diags = []
    system_connectors = []
    extractor = PdfGeometryCandidateExtractor()

    drawings = page.get_drawings()
    try:
        text_dict = page.get_text("dict")
    except Exception:
        text_dict = {}

    group_bounds = [_notation_group_bounds(g) for g in notation_groups]
    connected_systems, connectors_found = _group_notation_groups_by_system_connectors(drawings, group_bounds)

    group_system_mapping = {}
    for system_idx, indices in enumerate(connected_systems, start=1):
        for staff_idx_in_sys, idx in enumerate(indices, start=1):
            group_system_mapping[idx] = {"system_index": system_idx, "staff_index": staff_idx_in_sys}

    global_idx = 1
    sys_to_global_indices = {}
    for indices in connected_systems:
        sys_to_global_indices[tuple(indices)] = [global_idx + k for k in range(len(indices))]
        global_idx += len(indices)

    for conn_data in connectors_found:
        indices = conn_data["indices"]
        conn_kind, cx0, cy0, cx1, cy1 = conn_data["connector_info"]
        system_connectors.append(
            SystemConnectorDiagnostics(
                connected_staff_indices=sys_to_global_indices[tuple(indices)],
                connector_kind=conn_kind, # type: ignore
                x0=round(cx0, 3),
                y0=round(cy0, 3),
                x1=round(cx1, 3),
                y1=round(cy1, 3)
            )
        )

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
                            font_size = float(span.get("size", 0.0))
                            text_span_by_font[font_name] = text_span_by_font.get(font_name, 0) + 1
                            primitives_for_clustering.append(PrimitiveGeometry("text_span", sx0, sy0, sx1, sy1, font_name, font_size))

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

            cluster_evidence_list = []

            for cluster in clusters:
                prim_count = len(cluster)
                if prim_count > max_prims:
                    max_prims = prim_count

                ev_prims = []
                for p in cluster:
                    ev = _to_evidence(p)
                    if ev:
                        ev_prims.append(ev)

                c_x0 = min(p.x0 for p in cluster)
                c_x1 = max(p.x1 for p in cluster)
                if ev_prims:
                    cluster_evidence_list.append(XAlignedPrimitiveClusterEvidence(
                        x0=round(c_x0, 3),
                        x1=round(c_x1, 3),
                        primitive_count=len(ev_prims),
                        primitives=ev_prims
                    ))

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
                ),
                evidence=cluster_evidence_list
            )

            margin_x_limit = staff_geom.x0 + (10.0 * staff_space)

            margin_curves = 0
            margin_vertical_strokes = 0
            margin_rects = 0
            
            margin_evidence_list = []

            for p in primitives_for_clustering:
                if staff_geom.x0 <= p.center_x <= margin_x_limit:
                    ev = _to_evidence(p)
                    if ev:
                        margin_evidence_list.append(ev)

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
                rectangle_candidate_count=margin_rects,
                evidence=margin_evidence_list
            )

        # --- Candidate extraction (read-only, supplementary) ---
        left_margin_candidates = None
        x_aligned_cluster_candidates = None

        if left_margin_diags is not None and left_margin_diags.evidence is not None:
            left_margin_candidates = extractor.extract_left_margin_candidates(
                page_index, system_idx, staff_idx, left_margin_diags.evidence
            )

        if clustering_diags is not None and clustering_diags.evidence is not None:
            x_aligned_cluster_candidates = extractor.extract_x_aligned_cluster_candidates(
                page_index, system_idx, staff_idx, clustering_diags.evidence
            )

        staves_diags.append(
            NotationStaffDiagnostics(
                staff=staff_geom,
                primitives=primitives_summary,
                morphology=morphology,
                clustering=clustering_diags,
                left_margin=left_margin_diags,
                left_margin_candidates=left_margin_candidates,
                x_aligned_cluster_candidates=x_aligned_cluster_candidates,
            )
        )

    notes = _extract_note_candidates(page)
    return PdfStaffNotationGeometryDiagnostics(
        staves=staves_diags,
        system_connectors=system_connectors,
        whole_note_candidates=notes[0],
        half_note_candidates=notes[1]
    )


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
