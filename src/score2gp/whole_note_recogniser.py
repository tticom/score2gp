from typing import Any, Iterable
from pathlib import Path

def shape_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    candidate_prefix: str,
    start_index: int = 1
) -> list[dict]:
    """
    Takes raw diagnostic candidates (objects or dicts) for a single page, sorts them
    geometrically, and shapes them into deterministic read-only candidate evidence
    with stable IDs.

    Returns the shaped candidates.
    """
    def get_bbox(c: Any) -> list[float]:
        return c["bbox"] if isinstance(c, dict) else c.bbox

    candidates = list(raw_candidates)
    # Sort geometrically: top, left, bottom, right
    candidates.sort(key=lambda c: (get_bbox(c)[1], get_bbox(c)[0], get_bbox(c)[3], get_bbox(c)[2]))

    shaped = []
    for i, cand in enumerate(candidates):
        candidate_id = f"{candidate_prefix}_{start_index + i:03d}"
        cand_dict = {
            "candidate_id": candidate_id,
            "page_index": page_index,
            "bbox": get_bbox(cand)
        }
        if isinstance(cand, dict):
            if "stem_bbox" in cand:
                cand_dict["stem_bbox"] = cand["stem_bbox"]
            for f in ("font_name", "glyph_ordinal", "origin_x", "origin_y", "source_method"):
                if f in cand:
                    cand_dict[f] = cand[f]
        else:
            if hasattr(cand, "stem_bbox"):
                cand_dict["stem_bbox"] = cand.stem_bbox
            for f in ("font_name", "glyph_ordinal", "origin_x", "origin_y", "source_method"):
                if hasattr(cand, f) and getattr(cand, f) is not None:
                    cand_dict[f] = getattr(cand, f)
        shaped.append(cand_dict)
    return shaped

def extract_treble_clef_candidate_evidence(
    staves_diags: list[dict],
    page_index: int,
    start_index: int = 1,
    page: Any = None
) -> list[dict]:
    """
    Extracts deterministic read-only treble clef candidate evidence by bridging
    existing raster diagnostics and logical clef candidate evidence.
    """
    from .logical_clef_candidate_classifier import classify_logical_clef_candidate
    from .pdf_geometry_candidates import LeftMarginPrimitiveCandidate

    raster_staffs = []
    if page is not None:
        try:
            from .pdf_raster_staff_diagnostics import build_raster_notation_diagnostics
            raster_diags = build_raster_notation_diagnostics(page, page_index, scale=2.0)
            if raster_diags.get("status") == "success":
                scale = raster_diags.get("render_scale")
                if type(scale) in (int, float) and scale > 0.0:
                    raster_staffs = raster_diags.get("staffs", [])
        except Exception:
            pass

    # Build raster matches
    raster_matched_bboxes = {}
    if raster_staffs:
        for r_staff in raster_staffs:
            if not isinstance(r_staff, dict):
                continue

            clf = r_staff.get("raster_opening_symbol_classification", {})
            if clf.get("label") != "treble_clef_candidate":
                continue

            cand = r_staff.get("raster_opening_symbol_candidate", {})
            bbox = cand.get("bbox")
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                continue

            y_coords = r_staff.get("y_coords")
            if not isinstance(y_coords, list) or len(y_coords) != 5:
                continue

            try:
                geom_bbox = [float(b) / scale for b in bbox]
                r_y0 = float(y_coords[0]) / scale
                r_y1 = float(y_coords[4]) / scale
            except (TypeError, ValueError, ZeroDivisionError):
                continue

            # Find matching geometry staves
            matching_geom = []
            for g_staff in staves_diags:
                info = g_staff.get("staff", {})
                g_y0 = info.get("y0")
                g_y1 = info.get("y1")

                if not isinstance(g_y0, (int, float)) or not isinstance(g_y1, (int, float)):
                    continue

                # Within 10 points (approx 2 staff spaces)
                if abs(g_y0 - r_y0) <= 10.0 and abs(g_y1 - r_y1) <= 10.0:
                    matching_geom.append(info)

            # Fail closed if ambiguous or missing
            if len(matching_geom) != 1:
                continue

            info = matching_geom[0]
            sys_idx = info.get("system_index")
            s_idx = info.get("staff_index")

            if sys_idx is None or s_idx is None:
                continue

            key = (sys_idx, s_idx)
            if key in raster_matched_bboxes:
                raster_matched_bboxes[key] = "AMBIGUOUS"
            else:
                raster_matched_bboxes[key] = geom_bbox

    shaped = []
    current_id = start_index

    for g_staff in staves_diags:
        info = g_staff.get("staff", {})
        sys_idx = info.get("system_index")
        s_idx = info.get("staff_index")
        if sys_idx is None or s_idx is None:
            continue

        key = (sys_idx, s_idx)
        raster_bbox = raster_matched_bboxes.get(key)
        if raster_bbox == "AMBIGUOUS":
            continue

        # Evaluate logical clef evidence
        logical_bbox = None
        lm_cands_raw = g_staff.get("left_margin_candidates")
        line_ys = info.get("line_y_coords", [])
        staff_spacing = 10.0
        if len(line_ys) == 5:
            staff_spacing = float(line_ys[-1] - line_ys[0]) / 4.0

        if lm_cands_raw and len(line_ys) == 5:
            lm_cands = []
            for c in lm_cands_raw:
                try:
                    lm_cands.append(LeftMarginPrimitiveCandidate(**c))
                except Exception:
                    pass

            staff_height = float(line_ys[-1] - line_ys[0])
            staff_x0 = float(info.get("x0", 0.0))

            clf = classify_logical_clef_candidate(lm_cands, staff_spacing, staff_height, staff_x0)
            if clf.get("label") == "treble_clef_candidate":
                logical_bbox = clf.get("features", {}).get("bbox")

        if raster_bbox or logical_bbox:
            final_bbox = logical_bbox if logical_bbox else raster_bbox
            if logical_bbox and raster_bbox:
                # Verify spatial compatibility before unifying
                rx0, ry0, rx1, ry1 = raster_bbox
                lx0, ly0, lx1, ly1 = logical_bbox

                # Use a tolerance of 1 staff space
                tol = staff_spacing * 1.0
                overlap_x = max(0, min(rx1 + tol, lx1 + tol) - max(rx0 - tol, lx0 - tol))
                overlap_y = max(0, min(ry1 + tol, ly1 + tol) - max(ry0 - tol, ly0 - tol))

                if overlap_x <= 0 or overlap_y <= 0:
                    # Conflicting evidence -> fail closed
                    continue

                source = "unified_diagnostic_candidate_evidence"
            elif logical_bbox:
                source = "logical_diagnostic_candidate_evidence"
            else:
                source = "raster_diagnostic_candidate_evidence"

            shaped.append({
                "system_index": sys_idx,
                "staff_index": s_idx,
                "page_index": page_index,
                "bbox": final_bbox,
                "source": source,
                "candidate_id": f"treble_{current_id:03d}"
            })
            current_id += 1

    return shaped

def shape_whole_note_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    return shape_candidate_evidence(raw_candidates, page_index, "whole_note_candidate", start_index)

def shape_half_note_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    return shape_candidate_evidence(raw_candidates, page_index, "half_note_candidate", start_index)

def shape_tie_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    system_index: int | None = None,
    staff_index: int | None = None,
    start_index: int = 1
) -> list[dict]:
    shaped = shape_candidate_evidence(raw_candidates, page_index, "tie_candidate", start_index)
    for cand in shaped:
        cand["system_index"] = system_index
        cand["staff_index"] = staff_index
    return shaped

def shape_dot_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    system_index: int | None = None,
    staff_index: int | None = None,
    start_index: int = 1
) -> list[dict]:
    return shape_candidate_evidence(raw_candidates, page_index, "dot_candidate", start_index)

def shape_quarter_note_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    return shape_candidate_evidence(raw_candidates, page_index, "quarter_note_candidate", start_index)

def shape_x_aligned_cluster_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    candidates = list(raw_candidates)

    def get_sort_key(c: Any):
        c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else c.dict())
        return (c_dict.get("system_index", 0), c_dict.get("staff_index", 0), c_dict.get("x0", 0.0), c_dict.get("x1", 0.0))

    candidates.sort(key=get_sort_key)

    shaped = []
    for i, cand in enumerate(candidates):
        candidate_id = f"x_aligned_cluster_candidate_{start_index + i:03d}"
        c_dict = cand if isinstance(cand, dict) else (cand.model_dump() if hasattr(cand, "model_dump") else cand.dict())

        shaped.append({
            "candidate_id": candidate_id,
            "page_index": page_index,
            "system_index": c_dict.get("system_index"),
            "staff_index": c_dict.get("staff_index"),
            "x0": c_dict.get("x0"),
            "x1": c_dict.get("x1"),
            "primitive_count": c_dict.get("primitive_count"),
            "primitives": c_dict.get("primitives", [])
        })
    return shaped

def shape_left_margin_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    candidates = list(raw_candidates)

    def get_sort_key(c: Any):
        c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else c.dict())
        return (c_dict.get("system_index", 0), c_dict.get("staff_index", 0), c_dict.get("x0", 0.0), c_dict.get("y0", 0.0))

    candidates.sort(key=get_sort_key)

    shaped = []
    for i, cand in enumerate(candidates):
        candidate_id = f"left_margin_candidate_{start_index + i:03d}"
        c_dict = cand if isinstance(cand, dict) else (cand.model_dump() if hasattr(cand, "model_dump") else cand.dict())

        shaped.append({
            "candidate_id": candidate_id,
            "page_index": page_index,
            "system_index": c_dict.get("system_index"),
            "staff_index": c_dict.get("staff_index"),
            "x0": c_dict.get("x0"),
            "y0": c_dict.get("y0"),
            "x1": c_dict.get("x1"),
            "y1": c_dict.get("y1"),
            "kind": c_dict.get("kind"),
            "source": c_dict.get("source"),
            "font_name": c_dict.get("font_name"),
            "font_size": c_dict.get("font_size")
        })
    return shaped

def shape_ledger_line_candidate_evidence(
    raw_clusters: Iterable[Any],
    page_index: int,
    start_index: int = 1
) -> list[dict]:
    candidates = []

    clusters = list(raw_clusters)
    def get_sort_key(c: Any):
        c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else c.dict())
        return (c_dict.get("system_index", 0), c_dict.get("staff_index", 0), c_dict.get("x0", 0.0), c_dict.get("x1", 0.0))
    clusters.sort(key=get_sort_key)

    for cluster in clusters:
        c_dict = cluster if isinstance(cluster, dict) else (cluster.model_dump() if hasattr(cluster, "model_dump") else cluster.dict())
        primitives = c_dict.get("primitives", [])

        prims = [p if isinstance(p, dict) else (p.model_dump() if hasattr(p, "model_dump") else p.dict()) for p in primitives]
        horizontals = [p for p in prims if p.get("kind") == "horizontal_stroke"]
        cores = [p for p in prims if p.get("kind") in ("rectangle", "vertical_stroke", "curve")]

        horizontals.sort(key=lambda p: (p.get("y0", 0.0), p.get("x0", 0.0)))

        for h in horizontals:
            overlap = False
            for co in cores:
                hx0, hy0, hx1, hy1 = h.get("x0", 0), h.get("y0", 0), h.get("x1", 0), h.get("y1", 0)
                cx0, cy0, cx1, cy1 = co.get("x0", 0), co.get("y0", 0), co.get("x1", 0), co.get("y1", 0)
                if not (hx1 < cx0 or hx0 > cx1 or hy1 < cy0 - 4.5 or hy0 > cy1 + 4.5):
                    overlap = True
                    break
            if overlap:
                candidates.append({
                    "page_index": page_index,
                    "system_index": c_dict.get("system_index"),
                    "staff_index": c_dict.get("staff_index"),
                    "bbox": [h.get("x0"), h.get("y0"), h.get("x1"), h.get("y1")]
                })

    for i, cand in enumerate(candidates):
        cand["candidate_id"] = f"ledger_line_candidate_{start_index + i:03d}"

    return candidates


def map_treble_clef_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    """
    Consumes diagnostic treble clef candidate evidence and produces a read-only recognition outcome.
    """
    outcomes = []
    seen_ids = set()
    for cand in candidate_locations:
        candidate_id = cand.get("candidate_id")
        page_index = cand.get("page_index")
        system_index = cand.get("system_index")
        staff_index = cand.get("staff_index")
        bbox = cand.get("bbox")

        if not candidate_id or not isinstance(candidate_id, str):
            continue
        if candidate_id in seen_ids:
            continue

        if type(page_index) is not int:
            continue
        if type(system_index) is not int:
            continue
        if type(staff_index) is not int:
            continue

        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue

        try:
            x0, y0, x1, y1 = [float(v) for v in bbox]
        except (TypeError, ValueError):
            continue

        seen_ids.add(candidate_id)
        source = cand.get("source", "diagnostic_candidate_evidence")
        outcomes.append({
            "symbol_type": "treble_clef_candidate",
            "candidate_id": candidate_id,
            "page_index": page_index,
            "system_index": system_index,
            "staff_index": staff_index,
            "bbox": [x0, y0, x1, y1],
            "source": source
        })
    return outcomes

def map_whole_note_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    """
    Consumes diagnostic whole-note candidate evidence and produces a read-only
    recognition outcome without inferring broad musical semantics like pitch, rhythm, or staff position.
    This acts as the first safe product seam from diagnostics to notation.
    """
    outcomes = []
    for cand in candidate_locations:
        outcome = {
            "symbol_type": "whole_note_candidate",
            "candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "association_status": cand.get("association_status"),
            "font_name": cand.get("font_name"),
            "glyph_ordinal": cand.get("glyph_ordinal"),
            "origin_x": cand.get("origin_x"),
            "origin_y": cand.get("origin_y"),
            "source_method": cand.get("source_method"),
            "duration": "whole",
            "source": "diagnostic_candidate_evidence"
        }
        if "association_reason" in cand:
            outcome["association_reason"] = cand.get("association_reason")
        outcomes.append(outcome)
    return outcomes

def map_whole_note_candidates_to_intermediate_notes(outcomes: list[dict]) -> list[dict]:
    """
    Consumes read-only recognition outcomes and emits whole-note intermediate representations
    for valid staff-associated whole note candidates.
    """
    intermediate_notes = []

    for cand in outcomes:
        if cand.get("symbol_type") != "whole_note_candidate":
            continue

        intermediate_note = {
            "source_candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "source": cand.get("source", "intermediate_representation")
        }

        # We need successful staff association
        if cand.get("association_status") != "success":
            intermediate_note["symbol_type"] = "whole_note_mapping_failure"
            intermediate_note["mapping_status"] = "failed"
            intermediate_note["mapping_reason"] = f"invalid_association_status: {cand.get('association_status')}"
            intermediate_notes.append(intermediate_note)
            continue

        page_index = cand.get("page_index")
        system_index = cand.get("system_index")
        staff_index = cand.get("staff_index")
        staff_position_index = cand.get("staff_position_index")
        bbox = cand.get("bbox")

        if page_index is None or system_index is None or staff_index is None:
            intermediate_note["symbol_type"] = "whole_note_mapping_failure"
            intermediate_note["mapping_status"] = "failed"
            intermediate_note["mapping_reason"] = "missing_staff_indices"
            intermediate_notes.append(intermediate_note)
            continue

        if type(staff_position_index) is not int:
            intermediate_note["symbol_type"] = "whole_note_mapping_failure"
            intermediate_note["mapping_status"] = "failed"
            intermediate_note["mapping_reason"] = "missing_or_invalid_staff_position_index"
            intermediate_notes.append(intermediate_note)
            continue

        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            intermediate_note["symbol_type"] = "whole_note_mapping_failure"
            intermediate_note["mapping_status"] = "failed"
            intermediate_note["mapping_reason"] = "missing_or_malformed_bbox"
            intermediate_notes.append(intermediate_note)
            continue

        intermediate_note["symbol_type"] = "whole_note"
        intermediate_note["note_kind"] = "whole_note"
        intermediate_note["duration_kind"] = "whole"
        intermediate_note["page_index"] = page_index
        intermediate_note["system_index"] = system_index
        intermediate_note["staff_index"] = staff_index
        intermediate_note["staff_position_index"] = staff_position_index
        intermediate_note["mapping_status"] = "success"

        intermediate_notes.append(intermediate_note)

    return intermediate_notes

def map_half_note_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    """
    Consumes diagnostic half-note candidate evidence and produces a read-only
    recognition outcome without inferring broad musical semantics like pitch, rhythm, or staff position.
    """
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "half_note_candidate",
            "candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "duration": "half",
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_quarter_note_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    """
    Consumes diagnostic quarter-note candidate evidence and produces a read-only
    recognition outcome without inferring broad musical semantics like pitch, rhythm, or staff position.
    """
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "quarter_note_candidate",
            "candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "duration": "quarter",
            "stem_bbox": cand.get("stem_bbox"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_x_aligned_cluster_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "x_aligned_cluster_candidate",
            "candidate_id": cand.get("candidate_id"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "x0": cand.get("x0"),
            "x1": cand.get("x1"),
            "primitive_count": cand.get("primitive_count"),
            "primitives": cand.get("primitives"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_left_margin_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "left_margin_candidate",
            "candidate_id": cand.get("candidate_id"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "x0": cand.get("x0"),
            "y0": cand.get("y0"),
            "x1": cand.get("x1"),
            "y1": cand.get("y1"),
            "kind": cand.get("kind"),
            "source": "diagnostic_candidate_evidence",
            "font_name": cand.get("font_name"),
            "font_size": cand.get("font_size")
        })
    return outcomes

def map_ledger_line_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "ledger_line_candidate",
            "candidate_id": cand.get("candidate_id"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "bbox": cand.get("bbox"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def shape_flag_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    system_index: int,
    staff_index: int,
    start_index: int = 1
) -> list[dict]:
    candidates = list(raw_candidates)

    def get_sort_key(c: Any):
        c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else c.dict())
        bbox = c_dict.get("bbox", [0.0, 0.0, 0.0, 0.0])
        return (bbox[0], bbox[1])

    candidates.sort(key=get_sort_key)

    shaped = []
    for i, cand in enumerate(candidates):
        candidate_id = f"flag_candidate_{start_index + i:03d}"
        c_dict = cand if isinstance(cand, dict) else (cand.model_dump() if hasattr(cand, "model_dump") else cand.dict())

        shaped.append({
            "candidate_id": candidate_id,
            "page_index": page_index,
            "system_index": system_index,
            "staff_index": staff_index,
            "bbox": c_dict.get("bbox"),
            "primitive_kind": c_dict.get("primitive_kind"),
            "width": c_dict.get("width"),
            "height": c_dict.get("height")
        })
    return shaped

def shape_beam_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    system_index: int,
    staff_index: int,
    start_index: int = 1
) -> list[dict]:
    candidates = list(raw_candidates)

    def get_sort_key(c: Any):
        c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else c.dict())
        bbox = c_dict.get("bbox", [0.0, 0.0, 0.0, 0.0])
        return (bbox[0], bbox[1])

    candidates.sort(key=get_sort_key)

    shaped = []
    for i, cand in enumerate(candidates):
        candidate_id = f"beam_candidate_{start_index + i:03d}"
        c_dict = cand if isinstance(cand, dict) else (cand.model_dump() if hasattr(cand, "model_dump") else cand.dict())

        shaped.append({
            "candidate_id": candidate_id,
            "page_index": page_index,
            "system_index": system_index,
            "staff_index": staff_index,
            "bbox": c_dict.get("bbox"),
            "primitive_kind": c_dict.get("primitive_kind"),
            "width": c_dict.get("width"),
            "height": c_dict.get("height")
        })
    return shaped

def map_flag_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "flag_candidate",
            "candidate_id": cand.get("candidate_id"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "bbox": cand.get("bbox"),
            "primitive_kind": cand.get("primitive_kind"),
            "width": cand.get("width"),
            "height": cand.get("height"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_beam_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "beam_candidate",
            "candidate_id": cand.get("candidate_id"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "bbox": cand.get("bbox"),
            "primitive_kind": cand.get("primitive_kind"),
            "width": cand.get("width"),
            "height": cand.get("height"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_tie_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "tie_candidate",
            "candidate_id": cand.get("candidate_id"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "bbox": cand.get("bbox"),
            "primitive_kind": cand.get("primitive_kind"),
            "width": cand.get("width"),
            "height": cand.get("height"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_dot_candidates_to_read_only_outcomes(candidate_locations: list[dict]) -> list[dict]:
    outcomes = []
    for cand in candidate_locations:
        outcomes.append({
            "symbol_type": "dot_candidate",
            "candidate_id": cand.get("candidate_id"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "bbox": cand.get("bbox"),
            "primitive_kind": cand.get("primitive_kind"),
            "width": cand.get("width"),
            "height": cand.get("height"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

def map_staff_geometry_to_read_only_report(staves_diags: list[dict]) -> list[dict]:
    staff_geometries = []
    for staff_diag in staves_diags:
        staff = staff_diag.get("staff", {})
        if not staff:
            continue
        try:
            bbox = [staff["x0"], staff["y0"], staff["x1"], staff["y1"]]
            page_index = staff["page_index"]
            system_index = staff["system_index"]
            staff_index = staff["staff_index"]
            line_y_coords = staff["line_y_coords"]
            staff_geometries.append({
                "page_index": page_index,
                "system_index": system_index,
                "staff_index": staff_index,
                "bbox": bbox,
                "line_y_coords": line_y_coords
            })
        except KeyError:
            continue
    return staff_geometries

def _associate_staves(shaped_candidates: list[dict], staves: list[dict]) -> None:
    if not staves:
        for cand in shaped_candidates:
            cand["association_status"] = "failed"
            cand["association_reason"] = "missing_staff_geometry"
        return
    for cand in shaped_candidates:
        bbox = cand.get("bbox")
        if not bbox or len(bbox) < 4:
            cand["association_status"] = "failed"
            cand["association_reason"] = "malformed_candidate_bbox"
            continue
        c_x0, c_y0, c_x1, c_y1 = bbox
        if "origin_y" in cand and cand["origin_y"] is not None:
            c_y = cand["origin_y"]
        else:
            c_y = (c_y0 + c_y1) / 2.0

        matched_staves = []
        for staff_dict in staves:
            staff = staff_dict.get("staff", {})
            if not staff:
                continue
            s_y0 = staff.get("y0")
            s_y1 = staff.get("y1")
            s_x0 = staff.get("x0")
            s_x1 = staff.get("x1")

            if s_y0 is None or s_y1 is None or s_x0 is None or s_x1 is None:
                continue

            staff_height = s_y1 - s_y0
            if staff_height <= 0:
                continue

            staff_space = staff_height / 4.0

            vertical_margin = 6.0 * staff_space
            horizontal_margin = 1.0 * staff_space

            vertical_ok = (s_y0 - vertical_margin) <= c_y <= (s_y1 + vertical_margin)
            horizontal_ok = c_x1 >= (s_x0 - horizontal_margin) and c_x0 <= (s_x1 + horizontal_margin)

            if vertical_ok and horizontal_ok:
                staff_center_y = (s_y0 + s_y1) / 2.0
                dist = abs(c_y - staff_center_y)
                matched_staves.append({
                    "staff": staff,
                    "dist": dist,
                    "staff_space": staff_space
                })

        if len(matched_staves) == 1:
            best_staff = matched_staves[0]["staff"]
            cand["system_index"] = best_staff.get("system_index")
            cand["staff_index"] = best_staff.get("staff_index")
            cand["association_status"] = "success"
        elif len(matched_staves) == 0:
            cand["association_status"] = "failed"
            cand["association_reason"] = "outside_staff_bounds"
        else:
            matched_staves.sort(key=lambda x: x["dist"])
            nearest = matched_staves[0]
            second_nearest = matched_staves[1]

            ambiguity_threshold = 1.0 * nearest["staff_space"]
            if (second_nearest["dist"] - nearest["dist"]) <= ambiguity_threshold:
                cand["association_status"] = "failed"
                cand["association_reason"] = "ambiguous_staff_match"
            else:
                best_staff = nearest["staff"]
                cand["system_index"] = best_staff.get("system_index")
                cand["staff_index"] = best_staff.get("staff_index")
                cand["association_status"] = "success"

def compose_filled_duration_candidates(outcomes: list[dict]) -> list[dict]:
    quarters = [o for o in outcomes if o.get("symbol_type") == "quarter_note_candidate"]
    flags = [o for o in outcomes if o.get("symbol_type") == "flag_candidate"]
    beams = [o for o in outcomes if o.get("symbol_type") == "beam_candidate"]

    def bboxes_intersect(b1, b2, x_margin=1.0, y_margin=20.0):
        return not (b1[2] < b2[0] - x_margin or
                    b1[0] > b2[2] + x_margin or
                    b1[3] < b2[1] - y_margin or
                    b1[1] > b2[3] + y_margin)

    def bbox_union(bboxes):
        if not bboxes:
            return None
        return [
            min(b[0] for b in bboxes),
            min(b[1] for b in bboxes),
            max(b[2] for b in bboxes),
            max(b[3] for b in bboxes)
        ]

    def is_valid_bbox(bbox):
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return False
        try:
            x0, y0, x1, y1 = [float(v) for v in bbox]
            if x0 > x1 or y0 > y1:
                return False
            return True
        except (TypeError, ValueError):
            return False

    composed_notes = []
    idx = 1

    for q in quarters:
        q_page = q.get("page_index")
        q_sys = q.get("system_index")
        q_staff = q.get("staff_index")
        q_bbox = q.get("bbox")

        if q_page is None or q_sys is None or q_staff is None or not is_valid_bbox(q_bbox):
            continue

        q_stem = q.get("stem_bbox")
        full_bbox = bbox_union([q_bbox, q_stem]) if q_stem else q_bbox

        intersect_flags = []
        for f in flags:
            f_bbox = f.get("bbox")
            if f.get("page_index") == q_page and f.get("system_index") == q_sys and f.get("staff_index") == q_staff and is_valid_bbox(f_bbox):
                # A flag must be to the right of the stem (or slightly left of stem x0)
                # and its Y must be within the stem's Y bounds (plus some margin)
                stem_x = q_stem[0] if q_stem else q_bbox[2]
                if f_bbox[0] >= stem_x - 2.0 and f_bbox[0] <= stem_x + 3.0 and f_bbox[2] <= stem_x + 15.0:
                    y_min = full_bbox[1] - 2.0
                    y_max = full_bbox[3] + 2.0
                    if f_bbox[1] >= y_min and f_bbox[3] <= y_max:
                        # exclude curves that are entirely contained within the notehead bbox
                        if not (f_bbox[0] >= q_bbox[0] - 1.0 and f_bbox[2] <= q_bbox[2] + 1.0 and
                                f_bbox[1] >= q_bbox[1] - 1.0 and f_bbox[3] <= q_bbox[3] + 1.0):
                            intersect_flags.append(f)

        staff_space = max(0.1, q_bbox[3] - q_bbox[1])
        intersect_beams = []
        for b in beams:
            b_bbox = b.get("bbox")
            if b.get("page_index") == q_page and b.get("system_index") == q_sys and b.get("staff_index") == q_staff and is_valid_bbox(b_bbox):
                w = abs(b_bbox[2] - b_bbox[0])
                # Suppress short horizontal strokes (like ledger lines) from being treated as beams.
                # Ledger lines are centered on noteheads and are short (w < 2.0 * staff_space).
                # Actual beams span across multiple notes and are wide (w >= 2.0 * staff_space).
                if b.get("primitive_kind") == "non_staff_horizontal" and w < 2.0 * staff_space:
                    continue
                beam_y_margin = 2.0 if q_stem else 20.0
                if bboxes_intersect(full_bbox, b_bbox, x_margin=2.0, y_margin=beam_y_margin):
                    intersect_beams.append(b)

        units = 0
        modifiers = []
        if intersect_beams:
            stem_x = q_stem[0] if q_stem else q_bbox[2]

            def get_y_at_x(bbox, x):
                x0, y0, x1, y1 = bbox
                if x1 == x0:
                    return (y0 + y1) / 2.0
                x_clamped = max(x0, min(x1, x))
                return y0 + (y1 - y0) * (x_clamped - x0) / (x1 - x0)

            ys = sorted([get_y_at_x(b.get("bbox"), stem_x) for b in intersect_beams])
            if len(ys) == 1:
                units = 1
            else:
                span = ys[-1] - ys[0]
                if span < 3.2:
                    units = 1
                elif span < 6.5:
                    units = 2
                elif span < 9.5:
                    units = 3
                else:
                    units = 4
            modifiers = intersect_beams
        else:
            if intersect_flags:
                min_y = min([f.get("bbox")[1] for f in intersect_flags])
                max_y = max([f.get("bbox")[3] for f in intersect_flags])
                flag_height = max_y - min_y
                ratio = flag_height / staff_space

                if ratio < 2.8:
                    units = 1
                elif ratio < 4.5:
                    units = 2
                elif ratio < 6.5:
                    units = 3
                else:
                    units = 4
                modifiers = intersect_flags

        if units == 0:
            continue

        duration_type = "eighth"
        if units == 2:
            duration_type = "sixteenth"
        elif units == 3:
            duration_type = "thirty_second"
        elif units >= 4:
            duration_type = "sixty_fourth"

        sym_type = f"{duration_type}_note_candidate"
        mod_type = "beam_candidate" if intersect_beams else "flag_candidate"
        mod_ids = [m.get("candidate_id") for m in modifiers]
        mod_bboxes = [m.get("bbox") for m in modifiers]

        composed_bbox = bbox_union([q_bbox] + mod_bboxes)

        composed_notes.append({
            "candidate_id": f"{sym_type}_{idx:03d}",
            "symbol_type": sym_type,
            "page_index": q_page,
            "system_index": q_sys,
            "staff_index": q_staff,
            "bbox": composed_bbox,
            "notehead_bbox": q_bbox,
            "duration": duration_type,
            "source": q.get("source"),
            "quarter_component_id": q.get("candidate_id"),
            "modifier_component_ids": mod_ids,
            "modifier_type": mod_type
        })
        idx += 1

        q["association_status"] = "suppressed"

    return composed_notes

def apply_dots_to_notes(outcomes: list[dict]) -> None:
    dots = [o for o in outcomes if o.get("symbol_type") == "dot_candidate"]
    notes = [o for o in outcomes if o.get("symbol_type") in (
        "whole_note_candidate", "half_note_candidate", "quarter_note_candidate",
        "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate"
    ) and o.get("association_status") != "suppressed"]

    # Gather all possible valid matches between dots and notes
    possible_matches = []
    for dot in dots:
        d_page = dot.get("page_index")
        d_sys = dot.get("system_index")
        d_staff = dot.get("staff_index")
        d_bbox = dot.get("bbox")
        if not d_bbox: continue

        for note in notes:
            if note.get("page_index") != d_page or note.get("system_index") != d_sys or note.get("staff_index") != d_staff:
                continue

            n_bbox = note.get("bbox")
            if not n_bbox: continue

            dy = abs((d_bbox[1] + d_bbox[3])/2.0 - (n_bbox[1] + n_bbox[3])/2.0)
            dx = d_bbox[0] - n_bbox[2]

            # Augmentation dots must be to the right of the notehead and tightly aligned vertically
            # Relaxed dx up to 35.0 to account for flags which push the dot further right
            if 0.0 < dx < 35.0 and dy < 4.5:
                dist = dx + dy * 2.0  # Weight dy more to prefer the vertically closest note in a chord
                possible_matches.append((dist, dot, note))

    # Sort matches by distance (closest first)
    possible_matches.sort(key=lambda x: x[0])

    # Greedily assign matches uniquely
    assigned_dots = set()
    assigned_notes = {}  # note_id -> list of dot dictionaries
    for dist, dot, note in possible_matches:
        dot_id = dot.get("candidate_id")
        note_id = note.get("candidate_id")
        if dot_id in assigned_dots:
            continue

        # Allow multiple dots on the same notehead only if they are horizontally separated (i.e. different X)
        existing_dots = assigned_notes.get(note_id, [])
        if existing_dots:
            is_duplicate_x = False
            for ed in existing_dots:
                if abs(ed["bbox"][0] - dot["bbox"][0]) < 2.0:
                    is_duplicate_x = True
                    break
            if is_duplicate_x:
                continue

        assigned_dots.add(dot_id)
        assigned_notes.setdefault(note_id, []).append(dot)
        note["is_dotted"] = True
        note.setdefault("dot_component_ids", []).append(dot_id)
        dot["association_status"] = "consumed"
        dot["associated_note_id"] = note_id

    TICK_MAPPINGS = {
        "whole_note_candidate": 3840,
        "half_note_candidate": 1920,
        "quarter_note_candidate": 960,
        "eighth_note_candidate": 480,
        "sixteenth_note_candidate": 240,
        "thirty_second_note_candidate": 120,
        "sixty_fourth_note_candidate": 60,
    }

    # Now calculate durations for all dotted notes
    for note in notes:
        dots = note.get("dot_component_ids", [])
        if not dots: continue

        base_dur = TICK_MAPPINGS.get(note.get("symbol_type"), 960)
        modifier = 0.0
        # If it happens to swallow multiple dots incorrectly, cap it at 3 (triple dotted)
        num_dots = min(len(dots), 3)
        for i in range(1, num_dots + 1):
            modifier += 1.0 / (2 ** i)

        note["duration_ticks"] = int(base_dur * (1.0 + modifier))
        note["is_dotted"] = True

    # Propagate the longest duration in a chord to all other notes in that chord
    for n1 in notes:
        if "duration_ticks" not in n1:
            continue
        # Find all notes in the same chord (X-aligned and same staff)
        chord_notes = [
            n2 for n2 in notes
            if n2.get("page_index") == n1.get("page_index")
            and n2.get("system_index") == n1.get("system_index")
            and n2.get("staff_index") == n1.get("staff_index")
            and "bbox" in n1 and "bbox" in n2
            and abs(n1["bbox"][0] - n2["bbox"][0]) < 10.0
        ]

        max_dur = max([n.get("duration_ticks", TICK_MAPPINGS.get(n.get("symbol_type"), 960)) for n in chord_notes])

        for n2 in chord_notes:
            n2["duration_ticks"] = max_dur
            if max_dur != TICK_MAPPINGS.get(n2.get("symbol_type"), 960):
                n2["is_dotted"] = True

def map_staff_position_to_read_only_outcomes(outcomes: list[dict], staff_geometries: list[dict]) -> None:
    staff_geom_lookup = {}
    for sg in staff_geometries:
        key = (sg.get("page_index"), sg.get("system_index"), sg.get("staff_index"))
        staff_geom_lookup[key] = sg

    candidate_lookup = {c.get("candidate_id"): c for c in outcomes if c.get("candidate_id")}

    for cand in outcomes:
        st_type = cand.get("symbol_type")
        if st_type not in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate", "ledger_line_candidate", "x_aligned_cluster_candidate"):
            continue

        if cand.get("association_status") in ("failed", "suppressed"):
            continue

        sg_key = (cand.get("page_index"), cand.get("system_index"), cand.get("staff_index"))
        sg = staff_geom_lookup.get(sg_key)
        if not sg:
            cand["association_status"] = "failed"
            cand["association_reason"] = "missing_staff_geometry"
            continue

        line_y_coords = sg.get("line_y_coords")
        if not line_y_coords or not isinstance(line_y_coords, list) or len(line_y_coords) != 5:
            cand["association_status"] = "failed"
            cand["association_reason"] = "missing_staff_line_coordinates"
            continue

        try:
            line_y_coords = [float(y) for y in line_y_coords]
        except (TypeError, ValueError):
            cand["association_status"] = "failed"
            cand["association_reason"] = "malformed_staff_line_coordinates"
            continue

        notehead_y = None
        if st_type == "x_aligned_cluster_candidate":
            primitives = cand.get("primitives", [])
            ys = []
            has_notehead_like = False
            for p in primitives:
                if p.get("kind") in ("text_span", "curve", "rectangle"):
                    has_notehead_like = True
                if "y0" in p and "y1" in p:
                    ys.extend([p["y0"], p["y1"]])
            if ys and has_notehead_like:
                notehead_y = (min(ys) + max(ys)) / 2.0
            else:
                continue
        elif st_type in ("eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate"):
            q_id = cand.get("quarter_component_id")
            if not q_id:
                continue
            q_cand = candidate_lookup.get(q_id)
            if not q_cand:
                continue
            bbox = q_cand.get("bbox")
        else:
            bbox = cand.get("bbox")

        if notehead_y is None:
            if "origin_y" in cand and cand["origin_y"] is not None:
                notehead_y = float(cand["origin_y"])
            else:
                if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                    continue
                try:
                    x0, y0, x1, y1 = [float(v) for v in bbox]
                    if x0 > x1 or y0 > y1:
                        continue
                    notehead_y = (y0 + y1) / 2.0
                except (TypeError, ValueError):
                    continue

        if notehead_y is None:
            continue

        staff_space = (line_y_coords[-1] - line_y_coords[0]) / 4.0
        if staff_space <= 0:
            cand["association_status"] = "failed"
            cand["association_reason"] = "malformed_staff_spacing"
            continue

        pos_float = (notehead_y - line_y_coords[0]) / (staff_space / 2.0)
        cand["staff_position_index"] = int(round(pos_float))
        cand["association_status"] = "success"

def map_assumed_treble_pitch_to_read_only_outcomes(outcomes: list[dict]) -> None:
    pitches = ["F5", "E5", "D5", "C5", "B4", "A4", "G4", "F4", "E4"]
    for cand in outcomes:
        if cand.get("symbol_type") in ("ledger_line_candidate",):
            continue
        pos_idx = cand.get("staff_position_index")
        if type(pos_idx) is int and 0 <= pos_idx <= 8:
            cand["assumed_treble_pitch"] = pitches[pos_idx]

def map_clef_resolved_staff_pitch(
    outcomes: list[dict],
    explicit_clef: str | None = None,
    semantic_candidates: list[dict] | None = None,
    explicit_key_signature: str | None = None
) -> None:
    from score2gp.pdf_pitch_mapper import (
        map_staff_step_to_midi_pitch,
        midi_to_note_name,
        get_spelled_note_name,
        KEY_SIGNATURE_ALTERATIONS,
        LOCAL_ACCIDENTAL_MODIFIERS
    )

    clef_map = {}

    if explicit_clef is not None:
        pass
    elif semantic_candidates is not None:
        for sc in semantic_candidates:
            page = sc.get("page_index")
            sys_idx = sc.get("system_index")
            staff_idx = sc.get("staff_index")
            if type(page) is not int or type(sys_idx) is not int or type(staff_idx) is not int:
                continue
            logical_clef = sc.get("logical_clef", {})
            status = logical_clef.get("status")
            clef_kind = logical_clef.get("clef_kind")
            if status == "logical_clef_candidate" and clef_kind in ("treble", "bass", "alto"):
                clef_map[(page, sys_idx, staff_idx)] = clef_kind
    else:
        # Legacy fallback
        for cand in outcomes:
            if cand.get("symbol_type") == "treble_clef_candidate":
                cand_id = cand.get("candidate_id")
                if not isinstance(cand_id, str) or not cand_id:
                    continue
                source = cand.get("source")
                if source not in (
                    "diagnostic_candidate_evidence",
                    "raster_diagnostic_candidate_evidence",
                    "logical_diagnostic_candidate_evidence",
                    "unified_diagnostic_candidate_evidence"
                ):
                    continue
                page = cand.get("page_index")
                sys_idx = cand.get("system_index")
                staff_idx = cand.get("staff_index")
                if type(page) is not int or type(sys_idx) is not int or type(staff_idx) is not int:
                    continue
                key = (page, sys_idx, staff_idx)
                if key in clef_map:
                    clef_map[key] = "AMBIGUOUS"
                else:
                    clef_map[key] = "treble"
        # Filter out ambiguous keys
        clef_map = {k: v for k, v in clef_map.items() if v != "AMBIGUOUS"}

    # Group all notes and barlines by (page, sys_idx, staff_idx)
    groups = {}
    for cand in outcomes:
        st_type = cand.get("symbol_type")
        is_note = st_type in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate")
        is_barline = st_type in ("barline_candidate", "barline")
        if not (is_note or is_barline):
            continue

        page = cand.get("page_index")
        sys_idx = cand.get("system_index")
        staff_idx = cand.get("staff_index")

        # Fallback key if indices are missing but explicit_clef is provided
        if (page is None or sys_idx is None or staff_idx is None) and explicit_clef is not None:
            key = (0, 0, 0)
        else:
            if type(page) is not int or type(sys_idx) is not int or type(staff_idx) is not int:
                continue
            key = (page, sys_idx, staff_idx)

        if key not in groups:
            groups[key] = []
        groups[key].append(cand)

    def get_x_coord(c):
        if "notehead_bbox" in c:
            return c["notehead_bbox"][0]
        if "bbox" in c and isinstance(c["bbox"], (list, tuple)) and len(c["bbox"]) >= 1:
            return c["bbox"][0]
        return c.get("x0", 0.0)

    # Process each staff group
    for key, cands in groups.items():
        # Resolve clef
        if explicit_clef is not None:
            clef = explicit_clef
        else:
            clef = clef_map.get(key)

        if clef not in ("treble", "bass", "alto"):
            continue

        # Resolve key signature
        key_sig = "C Major"
        if explicit_key_signature is not None:
            key_sig = explicit_key_signature
        elif semantic_candidates is not None:
            for sc in semantic_candidates:
                sc_page = sc.get("page_index")
                sc_sys = sc.get("system_index")
                sc_staff = sc.get("staff_index")
                if sc_page == key[0] and sc_sys == key[1] and sc_staff == key[2]:
                    # Nested key signature candidate check
                    ks_obj = sc.get("key_signature")
                    if isinstance(ks_obj, dict):
                        key_sig = ks_obj.get("key_kind", "C Major")
                    elif sc.get("symbol_type") == "key_signature_candidate":
                        key_sig = sc.get("key_kind", "C Major")
                    break

        if key_sig not in KEY_SIGNATURE_ALTERATIONS:
            key_sig = "C Major"

        sig_alts = KEY_SIGNATURE_ALTERATIONS[key_sig]

        # Sort candidates chronologically (by x coord)
        sorted_cands = sorted(cands, key=get_x_coord)

        measure_memory = {}  # maps (letter, octave) to local modifier offset (semitones)

        for cand in sorted_cands:
            st_type = cand.get("symbol_type")
            is_barline = st_type in ("barline_candidate", "barline")

            if is_barline:
                measure_memory.clear()
                continue

            # Process note candidate
            pos = cand.get("staff_position_index")
            if type(pos) is not int:
                continue

            # Keep ledger bounds check
            if pos < -12 or pos > 15:
                continue

            # Explicit check for staff bounds compat
            if pos < 0 or pos > 8:
                required_ledgers = abs(pos) // 2 if pos < 0 else (pos - 8) // 2
                if required_ledgers < 4:
                    attached = cand.get("attached_ledger_line_candidate_ids", [])
                    if not isinstance(attached, list) or len(attached) != required_ledgers:
                        continue

            try:
                natural_midi = map_staff_step_to_midi_pitch(pos, clef)
                natural_name = midi_to_note_name(natural_midi)
                letter = natural_name[0]
                octave = int(natural_name[1:])

                # Resolve modifier based on precedence rules
                # Level 1: Direct local accidental
                cand_acc = cand.get("accidental")
                acc_val = None
                if cand_acc is not None:
                    if isinstance(cand_acc, int):
                        acc_val = cand_acc
                    elif isinstance(cand_acc, str):
                        acc_val = LOCAL_ACCIDENTAL_MODIFIERS.get(cand_acc.lower())

                if cand_acc is not None and acc_val is not None:
                    # Update local measure memory
                    measure_memory[(letter, octave)] = acc_val
                    modifier = acc_val
                # Level 2: Previous accidental in measure on same pitch class and octave
                elif (letter, octave) in measure_memory:
                    modifier = measure_memory[(letter, octave)]
                # Level 3: Key signature alteration
                elif letter in sig_alts:
                    modifier = sig_alts[letter]
                # Level 4: Natural baseline
                else:
                    modifier = 0

                final_midi = natural_midi + modifier
                cand["clef_resolved_staff_pitch"] = get_spelled_note_name(natural_midi, modifier)
                cand["clef_resolved_midi_pitch"] = final_midi
            except Exception:
                continue

def extract_measure_anchors_from_text(pdf_path, staff_geometries: list[dict]) -> dict:
    import fitz
    import re

    staves_sorted = sorted(staff_geometries, key=lambda s: (s["page_index"], s.get("bbox", [0,0,0,0])[1], s.get("bbox", [0,0,0,0])[0]))
    anchors = {}
    expected_measure = 1

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return anchors

    for staff in staves_sorted:
        if staff.get("staff_index") != 1:
            continue

        p_idx = staff["page_index"]
        key = (p_idx, staff.get("system_index"), staff.get("staff_index"))
        bbox = staff.get("bbox")
        if not bbox or p_idx < 1 or p_idx > len(doc):
            continue

        page = doc[p_idx - 1]
        search_rect = fitz.Rect(0, bbox[1] - 25, page.rect.width, bbox[1] + 5)

        try:
            words = [w for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(search_rect)]
            # Filter to keep only words whose top edge y0 is between 6.0 and 9.0 points above the staff top
            words = [w for w in words if 6.0 <= (bbox[1] - w[1]) <= 9.0]
        except Exception:
            continue

        words.sort(key=lambda w: w[0])

        staff_anchors = []
        for w in words:
            w_clean = re.sub(r'[^\w\s]', '', w[4])
            if w_clean.isdigit():
                num = int(w_clean)
                if num == expected_measure:
                    staff_anchors.append(w[0])
                    expected_measure += 1
                elif num > expected_measure and num <= expected_measure + 2:
                    staff_anchors.append(w[0])
                    expected_measure = num + 1

        if staff_anchors:
            anchors[key] = staff_anchors

    return anchors


def detect_time_signature(staves, pdf_path, measure_anchors=None) -> tuple[int, int] | None:
    # 1. Try text-based detection first
    if pdf_path is not None:
        try:
            import fitz
            import re
            doc = fitz.open(pdf_path)
            text = ""
            for i in range(min(3, len(doc))):
                text += doc[i].get_text()
            m = re.findall(r'\b(4/4|6/8|12/8)\b', text)
            if m:
                from collections import Counter
                most_common = Counter(m).most_common(1)[0][0]
                num, den = map(int, most_common.split("/"))
                return num, den
        except Exception:
            pass

    # 2. Duration evidence heuristics
    TICK_MAPPINGS = {
        "whole_note_candidate": 3840, "whole_note": 3840,
        "half_note_candidate": 1920, "half_note": 1920,
        "quarter_note_candidate": 960, "quarter_note": 960,
        "eighth_note_candidate": 480, "eighth_note": 480,
        "sixteenth_note_candidate": 240, "sixteenth_note": 240,
        "thirty_second_note_candidate": 120, "thirty_second_note": 120,
        "sixty_fourth_note_candidate": 60, "sixty_fourth_note": 60,
        "quarter_rest_candidate": 960, "quarter_rest": 960,
        "whole_rest_candidate": 3840, "whole_rest": 3840,
        "half_rest_candidate": 1920, "half_rest": 1920,
        "eighth_rest_candidate": 480, "eighth_rest": 480,
        "sixteenth_rest_candidate": 240, "sixteenth_rest": 240
    }

    raw_lengths = []

    def get_x_coord_local(c):
        if "notehead_bbox" in c:
            return c["notehead_bbox"][0]
        if "bbox" in c and isinstance(c["bbox"], (list, tuple)) and len(c["bbox"]) >= 1:
            return c["bbox"][0]
        return c.get("x0", 0.0)

    for key, data in staves.items():
        page, sys_idx, staff_idx = key
        cands = list(data["notes_rests_barlines"])
        geom = data["geometry"]
        
        staff_spacing = 10.0
        middle_y = None
        if geom is not None:
            line_y = geom.get("line_y_coords", [])
            if len(line_y) == 5:
                staff_spacing = (line_y[4] - line_y[0]) / 4.0
                middle_y = line_y[2]
            else:
                bbox = geom.get("bbox")
                if bbox and len(bbox) >= 4:
                    middle_y = (bbox[1] + bbox[3]) / 2.0
                    
        X_tol = 1.5 * staff_spacing
        
        staff_anchors = measure_anchors.get(key, []) if measure_anchors else []
        anchors_to_use = list(staff_anchors)
        if len(anchors_to_use) >= 1:
            if geom and "bbox" in geom and len(geom["bbox"]) >= 3:
                x1_staff = geom["bbox"][2]
                if not any(abs(a - x1_staff) <= 10.0 for a in anchors_to_use):
                    anchors_to_use.append(x1_staff)
                    
            omr_barlines = [c for c in cands if c.get("symbol_type") in ("barline_candidate", "barline")]
            cands = [c for c in cands if c.get("symbol_type") not in ("barline_candidate", "barline")]
            for anchor_x in anchors_to_use[1:]:
                cands.append({
                    "symbol_type": "barline_candidate",
                    "x0": anchor_x - 2.0,
                    "bbox": [anchor_x - 2.0, 0, anchor_x - 1.0, 0]
                })

        measures = []
        current_measure_cands = []
        for cand in sorted(cands, key=get_x_coord_local):
            st_type = cand.get("symbol_type")
            is_barline = st_type in ("barline_candidate", "barline")
            if is_barline:
                measures.append(current_measure_cands)
                current_measure_cands = []
            else:
                current_measure_cands.append(cand)
        if current_measure_cands:
            measures.append(current_measure_cands)

        for m_cands in measures:
            time_slices = []
            current_slice = []
            for c in sorted(m_cands, key=get_x_coord_local):
                if not current_slice:
                    current_slice.append(c)
                else:
                    prev_x = get_x_coord_local(current_slice[-1])
                    curr_x = get_x_coord_local(c)
                    if curr_x - prev_x < X_tol:
                        current_slice.append(c)
                    else:
                        time_slices.append(current_slice)
                        current_slice = [c]
            if current_slice:
                time_slices.append(current_slice)

            cursor_1 = 0
            cursor_2 = 0
            for slice_cands in time_slices:
                slice_v1 = []
                slice_v2 = []
                for c in slice_cands:
                    voice = 1
                    if "voice" in c:
                        voice = c["voice"]
                    elif "rest" in c.get("symbol_type", ""):
                        y_center = None
                        if "bbox" in c and isinstance(c["bbox"], (list, tuple)) and len(c["bbox"]) >= 4:
                            y_center = (c["bbox"][1] + c["bbox"][3]) / 2.0
                        else:
                            y_center = c.get("y0")
                        if middle_y is not None and y_center is not None:
                            if y_center >= middle_y + 10.0:
                                voice = 2
                    if voice == 2:
                        slice_v2.append(c)
                    else:
                        slice_v1.append(c)

                if slice_v1 and slice_v2:
                    start_tick = max(cursor_1, cursor_2)
                elif slice_v1:
                    start_tick = cursor_1
                elif slice_v2:
                    start_tick = cursor_2
                else:
                    continue

                if slice_v1:
                    cursor_1 = start_tick
                if slice_v2:
                    cursor_2 = start_tick

                has_notes_v1 = any("note" in c.get("symbol_type", "") for c in slice_v1)
                if has_notes_v1:
                    slice_v1 = [c for c in slice_v1 if "rest" not in c.get("symbol_type", "")]
                elif len(slice_v1) > 1:
                    slice_v1 = [max(slice_v1, key=lambda c: TICK_MAPPINGS.get(c.get("symbol_type", ""), c.get("duration_ticks", 960)))]

                has_notes_v2 = any("note" in c.get("symbol_type", "") for c in slice_v2)
                if has_notes_v2:
                    slice_v2 = [c for c in slice_v2 if "rest" not in c.get("symbol_type", "")]
                elif len(slice_v2) > 1:
                    slice_v2 = [max(slice_v2, key=lambda c: TICK_MAPPINGS.get(c.get("symbol_type", ""), c.get("duration_ticks", 960)))]

                for c in slice_v1:
                    dur = TICK_MAPPINGS.get(c.get("symbol_type"), 960)
                    if "duration_ticks" in c:
                        dur = c["duration_ticks"]
                    cursor_1 = max(cursor_1, start_tick + dur)

                for c in slice_v2:
                    dur = TICK_MAPPINGS.get(c.get("symbol_type"), 960)
                    if "duration_ticks" in c:
                        dur = c["duration_ticks"]
                    cursor_2 = max(cursor_2, start_tick + dur)

            raw_lengths.append(max(cursor_1, cursor_2))

    if not raw_lengths:
        return 4, 4

    from collections import Counter
    counts = Counter(raw_lengths)
    scores = {
        (4, 4): 0.0,
        (6, 8): 0.0,
        (12, 8): 0.0
    }
    for length, count in counts.items():
        if length == 0:
            continue
        d_44 = abs(length - 3840)
        d_68 = abs(length - 2880)
        d_128 = abs(length - 5760)
        min_d = min(d_44, d_68, d_128)
        if min_d <= 960:
            if min_d == d_44:
                scores[(4, 4)] += count
            elif min_d == d_68:
                scores[(6, 8)] += count
            else:
                scores[(12, 8)] += count

        # Overfull penalties to avoid selecting invalid meters
        if length > 3840 + 240:
            scores[(4, 4)] -= 100.0 * count
        if length > 2880 + 240:
            scores[(6, 8)] -= 100.0 * count
        if length > 5760 + 240:
            scores[(12, 8)] -= 100.0 * count

    best_meter = max(scores, key=scores.get)
    max_score = scores[best_meter]
    if max_score == 0:
        return None
    if list(scores.values()).count(max_score) > 1:
        return None
    return best_meter


def build_staff_timeline_preview(
    outcomes: list[dict],
    semantic_candidates: list[dict] | None = None,
    all_staff_geometries: list[dict] | None = None,
    measure_anchors: dict | None = None,
    pdf_path: str | Path | None = None
) -> list[dict]:
    # Group note and barline candidates by (page, sys, staff)
    staves = {}
    for cand in outcomes:
        st_type = cand.get("symbol_type")
        is_note = st_type in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate")
        is_barline = st_type in ("barline_candidate", "barline")
        is_rest = st_type in ("quarter_rest_candidate", "quarter_rest", "whole_rest_candidate", "whole_rest", "half_rest_candidate", "half_rest")
        is_tie = st_type == "tie_candidate"
        if not (is_note or is_barline or is_rest or is_tie):
            continue

        page = cand.get("page_index")
        sys_idx = cand.get("system_index")
        staff_idx = cand.get("staff_index")
        if page is None or sys_idx is None or staff_idx is None:
            continue

        key = (page, sys_idx, staff_idx)
        if key not in staves:
            staves[key] = {
                "notes_rests_barlines": [],
                "ties": [],
                "geometry": None
            }

        if is_note and not cand.get("clef_resolved_staff_pitch"):
            continue

        if is_tie:
            staves[key]["ties"].append(cand)
        else:
            staves[key]["notes_rests_barlines"].append(cand)

    # Collect rests from semantic_candidates
    if semantic_candidates is not None:
        for sc in semantic_candidates:
            page = sc.get("page_index")
            sys_idx = sc.get("system_index")
            staff_idx = sc.get("staff_index")
            if page is None or sys_idx is None or staff_idx is None:
                continue

            key = (page, sys_idx, staff_idx)
            if key not in staves:
                staves[key] = {
                    "notes_rests_barlines": [],
                    "geometry": None
                }

            # Gather rests from sc
            for r_type, dur in [("quarter_rests", 960), ("whole_rests", 3840), ("half_rests", 1920), ("eighth_rests", 480), ("sixteenth_rests", 240)]:
                rests = sc.get(r_type, [])
                for r in rests:
                    rest_cand = {
                        "symbol_type": r_type[:-1] + "_candidate",  # e.g. "quarter_rest_candidate"
                        "page_index": page,
                        "system_index": sys_idx,
                        "staff_index": staff_idx,
                        "duration_ticks": dur
                    }
                    if "bbox" in r and r["bbox"] is not None:
                        rest_cand["bbox"] = r["bbox"]
                    if "x0" in r and r["x0"] is not None:
                        rest_cand["x0"] = r["x0"]
                    if "y0" in r and r["y0"] is not None:
                        rest_cand["y0"] = r["y0"]

                    if "bbox" not in rest_cand and "x0" not in rest_cand:
                        continue

                    staves[key]["notes_rests_barlines"].append(rest_cand)

    # Attach staff geometry
    if all_staff_geometries is not None:
        for geom in all_staff_geometries:
            page = geom.get("page_index")
            sys_idx = geom.get("system_index")
            staff_idx = geom.get("staff_index")
            key = (page, sys_idx, staff_idx)
            if key in staves:
                staves[key]["geometry"] = geom

    detected_meter = (4, 4)
    if staves:
        detected_meter = detect_time_signature(staves, pdf_path, measure_anchors)
        if detected_meter is None:
            if pdf_path is None:
                detected_meter = (4, 4)
            else:
                raise ValueError("Insufficient time signature meter evidence.")

    def get_x_coord(c):
        if "notehead_bbox" in c:
            return c["notehead_bbox"][0]
        if "bbox" in c and isinstance(c["bbox"], (list, tuple)) and len(c["bbox"]) >= 1:
            return c["bbox"][0]
        return c.get("x0", 0.0)

    # Tick mappings
    TICK_MAPPINGS = {
        "whole_note_candidate": 3840,
        "whole_note": 3840,
        "half_note_candidate": 1920,
        "half_note": 1920,
        "quarter_note_candidate": 960,
        "quarter_note": 960,
        "eighth_note_candidate": 480,
        "eighth_note": 480,
        "sixteenth_note_candidate": 240,
        "sixteenth_note": 240,
        "thirty_second_note_candidate": 120,
        "sixty_fourth_note_candidate": 60,
        "quarter_rest_candidate": 960,
        "quarter_rest": 960,
        "whole_rest_candidate": 3840,
        "whole_rest": 3840,
        "half_rest_candidate": 1920,
        "half_rest": 1920,
        "eighth_rest_candidate": 480,
        "eighth_rest": 480,
        "sixteenth_rest_candidate": 240,
        "sixteenth_rest": 240
    }

    if detected_meter is not None and detected_meter[1] == 8:
        TICK_MAPPINGS["quarter_note_candidate"] = 480
        TICK_MAPPINGS["quarter_note"] = 480
        TICK_MAPPINGS["quarter_rest_candidate"] = 480
        TICK_MAPPINGS["quarter_rest"] = 480

    timeline_previews = []

    for key, data in staves.items():
        page, sys_idx, staff_idx = key
        cands = data["notes_rests_barlines"]

        # Filter out false barline candidates that are actually note stems
        cands_filtered = []
        for c in cands:
            if c.get("symbol_type") in ("barline_candidate", "barline"):
                bx = get_x_coord(c)
                is_stem = False
                for n in cands:
                    if "note" in n.get("symbol_type", ""):
                        stem = n.get("stem_bbox")
                        if stem and isinstance(stem, (list, tuple)) and len(stem) >= 1:
                            if abs(bx - stem[0]) < 1.0:
                                is_stem = True
                                break
                if is_stem:
                    continue
            cands_filtered.append(c)
        cands = cands_filtered

        geom = data["geometry"]

        # Resolve staff spacing and middle line y coordinate
        staff_spacing = 10.0
        middle_y = None
        if geom is not None:
            line_y = geom.get("line_y_coords", [])
            if len(line_y) == 5:
                staff_spacing = (line_y[4] - line_y[0]) / 4.0
                middle_y = line_y[2]
            else:
                bbox = geom.get("bbox")
                if bbox and len(bbox) >= 4:
                    middle_y = (bbox[1] + bbox[3]) / 2.0

        X_tol = 1.5 * staff_spacing

        # Use textual measure anchors if available and sufficiently dense
        staff_anchors = measure_anchors.get(key, []) if measure_anchors else []
        is_dense = len(staff_anchors) >= 2
        discarded_omr_barlines = []
        if is_dense:
            anchors_to_use = list(staff_anchors)
            if geom and "bbox" in geom and len(geom["bbox"]) >= 3:
                x1_staff = geom["bbox"][2]
                if not any(abs(a - x1_staff) <= 10.0 for a in anchors_to_use):
                    anchors_to_use.append(x1_staff)

            omr_barlines = [c for c in cands if c.get("symbol_type") in ("barline_candidate", "barline")]
            discarded_omr_barlines = list(omr_barlines)
            cands = [c for c in cands if c.get("symbol_type") not in ("barline_candidate", "barline")]
            for anchor_x in anchors_to_use[1:]:
                style = "simple"
                if omr_barlines:
                    nearest_omr = min(omr_barlines, key=lambda b: abs(get_x_coord(b) - anchor_x))
                    if abs(get_x_coord(nearest_omr) - anchor_x) <= 15.0:
                        style = nearest_omr.get("barline_style", "simple")
                cands.append({
                    "symbol_type": "barline_candidate",
                    "page_index": page,
                    "system_index": sys_idx,
                    "staff_index": staff_idx,
                    "x0": anchor_x - 2.0,
                    "bbox": [anchor_x - 2.0, 0, anchor_x - 1.0, 0],
                    "barline_style": style
                })
        else:
            if len(staff_anchors) >= 1:
                anchors_to_use = list(staff_anchors)
                if geom and "bbox" in geom and len(geom["bbox"]) >= 3:
                    x1_staff = geom["bbox"][2]
                    if not any(abs(a - x1_staff) <= 10.0 for a in anchors_to_use):
                        anchors_to_use.append(x1_staff)

                omr_barlines = [c for c in cands if c.get("symbol_type") in ("barline_candidate", "barline")]
                for anchor_x in anchors_to_use[1:]:
                    if any(abs(get_x_coord(b) - anchor_x) <= 20.0 for b in omr_barlines):
                        continue
                    style = "simple"
                    if omr_barlines:
                        nearest_omr = min(omr_barlines, key=lambda b: abs(get_x_coord(b) - anchor_x))
                        if abs(get_x_coord(nearest_omr) - anchor_x) <= 15.0:
                            style = nearest_omr.get("barline_style", "simple")
                    cands.append({
                        "symbol_type": "barline_candidate",
                        "page_index": page,
                        "system_index": sys_idx,
                        "staff_index": staff_idx,
                        "x0": anchor_x - 2.0,
                        "bbox": [anchor_x - 2.0, 0, anchor_x - 1.0, 0],
                        "barline_style": style
                    })

        # Sort all candidates chronologically by horizontal coordinate and split into measures
        iteration = 0
        while iteration < 10:
            sorted_cands = sorted(cands, key=get_x_coord)
            measures_with_x = []
            current_measure_cands = []
            current_start_x = geom["bbox"][0] if (geom and "bbox" in geom and len(geom["bbox"]) >= 1) else 0.0

            for cand in sorted_cands:
                st_type = cand.get("symbol_type")
                is_barline = st_type in ("barline_candidate", "barline")
                if is_barline:
                    bar_x = get_x_coord(cand)
                    measures_with_x.append((current_measure_cands, cand.get("barline_style", "simple"), current_start_x, bar_x))
                    current_measure_cands = []
                    current_start_x = bar_x
                else:
                    current_measure_cands.append(cand)
            if current_measure_cands:
                end_x = geom["bbox"][2] if (geom and "bbox" in geom and len(geom["bbox"]) >= 3) else current_start_x + 1000.0
                measures_with_x.append((current_measure_cands, "simple", current_start_x, end_x))

            # Check if any measure is overfull and can be split using discarded barlines
            barlines_to_restore = []
            num, den = detected_meter
            D_measure = int(num * 960 * 4 / den)

            for m_cands, b_style, x_start, x_end in measures_with_x:
                if not m_cands:
                    continue

                filtered_m_cands = []
                for c in m_cands:
                    st_type = c.get("symbol_type", "")
                    is_note = ("note" in st_type) and ("clef" not in st_type)
                    is_rest = ("rest" in st_type)
                    if is_note and not c.get("clef_resolved_staff_pitch"):
                        continue
                    if is_note or is_rest:
                        filtered_m_cands.append(c)

                # Simple sequence check to calculate measure_ticks
                time_slices = []
                current_slice = []
                for c in sorted(filtered_m_cands, key=get_x_coord):
                    if not current_slice:
                        current_slice.append(c)
                    else:
                        prev_c = current_slice[-1]
                        prev_x = get_x_coord(prev_c)
                        curr_x = get_x_coord(c)

                        if curr_x - prev_x < 1.2 * staff_spacing:
                            group_together = True
                        elif curr_x - prev_x < 2.5 * staff_spacing:
                            has_same_stem = False
                            if "bbox" in prev_c and "bbox" in c and isinstance(prev_c["bbox"], (list, tuple)) and isinstance(c["bbox"], (list, tuple)) and len(prev_c["bbox"]) >= 1 and len(c["bbox"]) >= 1:
                                has_same_stem = (abs(prev_c["bbox"][0] - c["bbox"][0]) < 1.0)
                            group_together = has_same_stem
                        else:
                            group_together = False

                        if group_together:
                            current_slice.append(c)
                        else:
                            time_slices.append(current_slice)
                            current_slice = [c]
                if current_slice:
                    time_slices.append(current_slice)

                cursor_1 = 0
                cursor_2 = 0
                for slice_cands in time_slices:
                    slice_v1 = []
                    slice_v2 = []
                    for c in slice_cands:
                        voice = 1
                        if "voice" in c:
                            voice = c["voice"]
                        elif c.get("stem_direction") == "down":
                            voice = 2
                        elif "rest" in c.get("symbol_type", ""):
                            y_center = None
                            if "bbox" in c and isinstance(c["bbox"], (list, tuple)) and len(c["bbox"]) >= 4:
                                y_center = (c["bbox"][1] + c["bbox"][3]) / 2.0
                            else:
                                y_center = c.get("y0")
                            if middle_y is not None and y_center is not None:
                                if y_center >= middle_y + 10.0:
                                    voice = 2
                        if voice == 2:
                            slice_v2.append(c)
                        else:
                            slice_v1.append(c)

                    start_tick = 0
                    if slice_v1 and slice_v2:
                        start_tick = max(cursor_1, cursor_2)
                    elif slice_v1:
                        start_tick = cursor_1
                    elif slice_v2:
                        start_tick = cursor_2
                    else:
                        continue

                    dur_v1 = 960
                    if slice_v1:
                        durs_v1 = []
                        for c in slice_v1:
                            d = TICK_MAPPINGS.get(c.get("symbol_type"), 960)
                            if "duration_ticks" in c:
                                d = c["duration_ticks"]
                            durs_v1.append(d)
                        dur_v1 = max(durs_v1) if durs_v1 else 960
                    dur_v2 = 960
                    if slice_v2:
                        durs_v2 = []
                        for c in slice_v2:
                            d = TICK_MAPPINGS.get(c.get("symbol_type"), 960)
                            if "duration_ticks" in c:
                                d = c["duration_ticks"]
                            durs_v2.append(d)
                        dur_v2 = max(durs_v2) if durs_v2 else 960

                    if slice_v1:
                        cursor_1 = max(cursor_1, start_tick + dur_v1)
                    if slice_v2:
                        cursor_2 = max(cursor_2, start_tick + dur_v2)

                measure_ticks = max(cursor_1, cursor_2)
                if measure_ticks > D_measure:
                    # Overfull! Look for a discarded barline in (x_start + 30.0, x_end - 30.0)
                    for b in discarded_omr_barlines:
                        bx = get_x_coord(b)
                        if x_start + 30.0 < bx < x_end - 30.0:
                            barlines_to_restore.append(b)

            if barlines_to_restore:
                # Add to active cands and remove from discarded list
                for b in barlines_to_restore:
                    cands.append(b)
                    if b in discarded_omr_barlines:
                        discarded_omr_barlines.remove(b)
                iteration += 1
                continue
            else:
                measures = [(mc, bs) for mc, bs, _, _ in measures_with_x]
                break
        else:
            measures = [(mc, bs) for mc, bs, _, _ in measures_with_x]

        timeline_measures = []

        for m_idx, (m_cands, b_style) in enumerate(measures):
            filtered_m_cands = []
            for c in m_cands:
                st_type = c.get("symbol_type", "")
                is_note = ("note" in st_type) and ("clef" not in st_type)
                is_rest = ("rest" in st_type)
                if is_note and not c.get("clef_resolved_staff_pitch"):
                    continue
                if is_note or is_rest:
                    filtered_m_cands.append(c)

            # Cluster measure candidates into vertical time slices
            time_slices = []
            current_slice = []
            for c in sorted(filtered_m_cands, key=get_x_coord):
                if not current_slice:
                    current_slice.append(c)
                else:
                    prev_c = current_slice[-1]
                    prev_x = get_x_coord(prev_c)
                    curr_x = get_x_coord(c)

                    if curr_x - prev_x < 1.2 * staff_spacing:
                        group_together = True
                    elif curr_x - prev_x < 2.5 * staff_spacing:
                        has_same_stem = False
                        if "bbox" in prev_c and "bbox" in c and isinstance(prev_c["bbox"], (list, tuple)) and isinstance(c["bbox"], (list, tuple)) and len(prev_c["bbox"]) >= 1 and len(c["bbox"]) >= 1:
                            has_same_stem = (abs(prev_c["bbox"][0] - c["bbox"][0]) < 1.0)
                        group_together = has_same_stem
                    else:
                        group_together = False

                    if group_together:
                        current_slice.append(c)
                    else:
                        time_slices.append(current_slice)
                        current_slice = [c]
            if current_slice:
                time_slices.append(current_slice)

            cursor_1 = 0
            cursor_2 = 0
            measure_events = []
            invalid = False

            for slice_cands in time_slices:
                slice_v1 = []
                slice_v2 = []
                for c in slice_cands:
                    # Resolve voice assignment
                    voice = 1
                    if "voice" in c:
                        voice = c["voice"]
                    elif c.get("stem_direction") == "down":
                        voice = 2
                    elif "rest" in c.get("symbol_type", ""):
                        # Determine rest vertical position
                        y_center = None
                        if "bbox" in c and isinstance(c["bbox"], (list, tuple)) and len(c["bbox"]) >= 4:
                            y_center = (c["bbox"][1] + c["bbox"][3]) / 2.0
                        else:
                            y_center = c.get("y0")

                        if middle_y is not None and y_center is not None:
                            if y_center >= middle_y + 10.0:  # slightly below middle to count as voice 2
                                voice = 2

                    if voice == 2:
                        slice_v2.append(c)
                    else:
                        slice_v1.append(c)

                # Compute slice start tick
                if slice_v1 and slice_v2:
                    start_tick = max(cursor_1, cursor_2)
                elif slice_v1:
                    start_tick = cursor_1
                elif slice_v2:
                    start_tick = cursor_2
                else:
                    continue

                # Align cursors
                if slice_v1:
                    cursor_1 = start_tick
                if slice_v2:
                    cursor_2 = start_tick

                # Discard rests if there are valid notes in the same slice for the same voice
                has_notes_v1 = any("note" in c.get("symbol_type", "") for c in slice_v1)
                if has_notes_v1:
                    slice_v1 = [c for c in slice_v1 if "rest" not in c.get("symbol_type", "")]
                elif len(slice_v1) > 1:
                    slice_v1 = [max(slice_v1, key=lambda c: TICK_MAPPINGS.get(c.get("symbol_type", ""), c.get("duration_ticks", 960)))]

                has_notes_v2 = any("note" in c.get("symbol_type", "") for c in slice_v2)
                if has_notes_v2:
                    slice_v2 = [c for c in slice_v2 if "rest" not in c.get("symbol_type", "")]
                elif len(slice_v2) > 1:
                    slice_v2 = [max(slice_v2, key=lambda c: TICK_MAPPINGS.get(c.get("symbol_type", ""), c.get("duration_ticks", 960)))]

                # Resolve a single duration for all notes in slice_v1
                dur_v1 = 960
                if slice_v1:
                    durs_v1 = []
                    for c in slice_v1:
                        d = TICK_MAPPINGS.get(c.get("symbol_type"), 960)
                        if "duration_ticks" in c:
                            d = c["duration_ticks"]
                        durs_v1.append(d)
                    dur_v1 = max(durs_v1) if durs_v1 else 960

                # Resolve a single duration for all notes in slice_v2
                dur_v2 = 960
                if slice_v2:
                    durs_v2 = []
                    for c in slice_v2:
                        d = TICK_MAPPINGS.get(c.get("symbol_type"), 960)
                        if "duration_ticks" in c:
                            d = c["duration_ticks"]
                        durs_v2.append(d)
                    dur_v2 = max(durs_v2) if durs_v2 else 960

                # Process voice 1
                for c in slice_v1:
                    c["timeline_start_tick"] = start_tick
                    c["timeline_duration_ticks"] = dur_v1
                    measure_events.append({
                        "candidate_id": c.get("candidate_id"),
                        "symbol_type": c.get("symbol_type"),
                        "voice": 1,
                        "start_tick": start_tick,
                        "duration_ticks": dur_v1,
                        "resolved_pitch": c.get("clef_resolved_staff_pitch"),
                        "bbox": c.get("bbox")
                    })
                if slice_v1:
                    cursor_1 = max(cursor_1, start_tick + dur_v1)

                # Process voice 2
                for c in slice_v2:
                    c["timeline_start_tick"] = start_tick
                    c["timeline_duration_ticks"] = dur_v2
                    measure_events.append({
                        "candidate_id": c.get("candidate_id"),
                        "symbol_type": c.get("symbol_type"),
                        "voice": 2,
                        "start_tick": start_tick,
                        "duration_ticks": dur_v2,
                        "resolved_pitch": c.get("clef_resolved_staff_pitch"),
                        "bbox": c.get("bbox")
                    })
                if slice_v2:
                    cursor_2 = max(cursor_2, start_tick + dur_v2)

            num, den = detected_meter
            D_measure = int(num * 960 * 4 / den)

            # Pad only voices that are musically active. An inactive secondary voice should not
            # introduce a visible whole-measure rest over a complete single-voice measure.
            active_voice_1 = any(e["voice"] == 1 for e in measure_events) or not measure_events
            active_voice_2 = any(e["voice"] == 2 for e in measure_events)
            if active_voice_1 and cursor_1 < D_measure:
                measure_events.append({
                    "candidate_id": None,
                    "symbol_type": "padding_rest",
                    "voice": 1,
                    "start_tick": cursor_1,
                    "duration_ticks": D_measure - cursor_1,
                    "resolved_pitch": None
                })
                cursor_1 = D_measure
            elif active_voice_1 and cursor_1 > D_measure:
                invalid = True

            if active_voice_2 and cursor_2 < D_measure:
                measure_events.append({
                    "candidate_id": None,
                    "symbol_type": "padding_rest",
                    "voice": 2,
                    "start_tick": cursor_2,
                    "duration_ticks": D_measure - cursor_2,
                    "resolved_pitch": None
                })
                cursor_2 = D_measure
            elif active_voice_2 and cursor_2 > D_measure:
                invalid = True

            overflow_diagnostics = None
            if invalid:
                v1_notes = sum(1 for e in measure_events if e["voice"] == 1 and "note" in e["symbol_type"])
                v1_rests = sum(1 for e in measure_events if e["voice"] == 1 and "rest" in e["symbol_type"])
                v2_notes = sum(1 for e in measure_events if e["voice"] == 2 and "note" in e["symbol_type"])
                v2_rests = sum(1 for e in measure_events if e["voice"] == 2 and "rest" in e["symbol_type"])
                overflow_diagnostics = {
                    "measure_number": m_idx + 1,
                    "expected_duration": D_measure,
                    "actual_cursor_duration_v1": cursor_1,
                    "actual_cursor_duration_v2": cursor_2,
                    "event_count": len(measure_events),
                    "note_count": v1_notes + v2_notes,
                    "rest_count": v1_rests + v2_rests,
                    "cause": "cumulative_duration_exceeds_measure_capacity"
                }

            # Sort events by start_tick then voice
            measure_events = sorted(measure_events, key=lambda e: (e["start_tick"], e["voice"]))

            timeline_measures.append({
                "measure_index": m_idx + 1,
                "valid": not invalid,
                "voice_1_final_tick": cursor_1,
                "voice_2_final_tick": cursor_2,
                "events": measure_events,
                "overflow_diagnostics": overflow_diagnostics,
                "barline_style": b_style
            })

        # Process ties for this staff
        staff_ties = data.get("ties", [])
        if staff_ties:
            # gather all notes
            all_notes = []
            for m in timeline_measures:
                for ev in m["events"]:
                    if "bbox" in ev and ev.get("symbol_type", "").endswith("note_candidate"):
                        all_notes.append(ev)

            for tie in staff_ties:
                tb = tie.get("bbox")
                if not tb:
                    continue
                tx0, ty0, tx1, ty1 = tb
                tie_y = (ty0 + ty1) / 2.0

                best_start = None
                best_start_dist = float('inf')
                best_end = None
                best_end_dist = float('inf')

                for n in all_notes:
                    nb = n["bbox"]
                    nx0, ny0, nx1, ny1 = nb
                    ny = (ny0 + ny1) / 2.0

                    # start note: tie's left side (tx0) is near note's right side (nx1)
                    dx_start = tx0 - nx1
                    # allow tie to start slightly inside or after note
                    if -10.0 <= dx_start <= 40.0:
                        dist = dx_start*dx_start + (tie_y - ny)*(tie_y - ny)
                        if dist < best_start_dist:
                            best_start_dist = dist
                            best_start = n

                    # end note: tie's right side (tx1) is near note's left side (nx0)
                    dx_end = nx0 - tx1
                    if -10.0 <= dx_end <= 40.0:
                        dist = dx_end*dx_end + (tie_y - ny)*(tie_y - ny)
                        if dist < best_end_dist:
                            best_end_dist = dist
                            best_end = n

                if best_start and best_end and best_start != best_end:
                    if best_start.get("resolved_pitch") == best_end.get("resolved_pitch"):
                        best_start["is_tie_start"] = True
                        best_end["is_tie_stop"] = True

        timeline_previews.append({
            "page_index": page,
            "system_index": sys_idx,
            "staff_index": staff_idx,
            "measures": timeline_measures,
            "detected_meter": detected_meter
        })

    # Parse and apply section markers / double barlines / tempo markings
    section_markers = {}
    tempo_markers = {}
    if pdf_path is not None and all_staff_geometries:
        try:
            import fitz
            import re
            tempo_pattern = re.compile(r'(?:[♩qQ]|\bBPM|\btempo)?\s*=\s*(\d+)', re.IGNORECASE)
            doc = fitz.open(pdf_path)
            for page_idx, page in enumerate(doc):
                page_staves = [s for s in all_staff_geometries if s.get("page_index") == page_idx + 1]
                if not page_staves:
                    continue
                blocks = page.get_text("blocks")
                for b in blocks:
                    text = b[4].strip()
                    if "Example" in text:
                        lines = [line.strip() for line in text.split("\n") if line.strip()]
                        if not lines:
                            continue
                        section_name = lines[0]
                        best_staff = None
                        min_dist = 1000.0
                        for s in page_staves:
                            staff_y0 = s["bbox"][1]
                            dist = staff_y0 - b[1]
                            if 0.0 < dist < 45.0:
                                if dist < min_dist:
                                    min_dist = dist
                                    best_staff = s
                        if best_staff is not None:
                            sys_idx = best_staff.get("system_index")
                            section_markers[(page_idx + 1, sys_idx)] = section_name

                    m = tempo_pattern.search(text)
                    if m:
                        bpm = int(m.group(1))
                        if 20 <= bpm <= 400:
                            best_staff = None
                            min_dist = 1000.0
                            for s in page_staves:
                                staff_y0 = s["bbox"][1]
                                dist = staff_y0 - b[1]
                                if 0.0 < dist < 120.0:
                                    if dist < min_dist:
                                        min_dist = dist
                                        best_staff = s
                            if best_staff is not None:
                                sys_idx = best_staff.get("system_index")
                                tempo_markers[(page_idx + 1, sys_idx)] = bpm
        except Exception:
            pass

    # Map measure_index -> measure dict for easy lookup
    measure_by_index = {}
    for preview in timeline_previews:
        for m in preview["measures"]:
            measure_by_index[m["measure_index"]] = m

    for preview in timeline_previews:
        key = (preview["page_index"], preview["system_index"])
        if key in section_markers:
            sect_name = section_markers[key]
            first_m = preview["measures"][0]
            first_m["section_name"] = sect_name
            prev_idx = first_m["measure_index"] - 1
            if prev_idx in measure_by_index:
                measure_by_index[prev_idx]["barline_style"] = "double"
        if key in tempo_markers:
            bpm = tempo_markers[key]
            first_m = preview["measures"][0]
            first_m["tempo_bpm"] = bpm

    timeline_previews = sorted(timeline_previews, key=lambda p: (p["page_index"], p["system_index"], p["staff_index"]))
    return timeline_previews


def build_clef_resolved_pitch_coverage_report(
    outcomes: list[dict],
    assume_treble_clef: bool = False,
    semantic_candidates: list[dict] | None = None
) -> dict:
    report = {
        "total_note_candidates_in_scope": 0,
        "note_candidates_with_staff_position_index": 0,
        "note_candidates_on_staves_with_valid_clef": 0,
        "note_candidates_on_staves_with_assumed_clef": 0,
        "note_candidates_with_clef_resolved_staff_pitch": 0,
        "note_candidates_with_assumed_treble_clef_pitch": 0,
        "assumed_clef_mode": assume_treble_clef,
        "in_staff_mapped_notes": 0,
        "out_of_staff_mapped_notes": 0,
        "skipped_missing_required_ledger_support": 0,
        "skipped_clef_missing": 0,
        "skipped_clef_ambiguous": 0,
        "skipped_staff_association_malformed": 0,
        "skipped_staff_position_malformed": 0,
        "sample_diagnostics": []
    }

    if not isinstance(outcomes, list):
        return report

    clef_policy = {}
    for cand in outcomes:
        if not isinstance(cand, dict):
            continue
        if cand.get("symbol_type") == "treble_clef_candidate":
            cand_id = cand.get("candidate_id")
            if not isinstance(cand_id, str) or not cand_id:
                continue
            source = cand.get("source")
            if source not in (
                "diagnostic_candidate_evidence",
                "raster_diagnostic_candidate_evidence",
                "logical_diagnostic_candidate_evidence",
                "unified_diagnostic_candidate_evidence"
            ):
                continue
            page = cand.get("page_index")
            sys_idx = cand.get("system_index")
            staff_idx = cand.get("staff_index")
            if type(page) is not int or type(sys_idx) is not int or type(staff_idx) is not int:
                continue
            key = (page, sys_idx, staff_idx)
            clef_policy[key] = clef_policy.get(key, 0) + 1

    note_types = ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate")

    for cand in outcomes:
        if not isinstance(cand, dict):
            continue
        if cand.get("symbol_type") not in note_types:
            continue

        report["total_note_candidates_in_scope"] += 1

        pos = cand.get("staff_position_index")
        has_pos = (type(pos) is int)
        if has_pos:
            report["note_candidates_with_staff_position_index"] += 1

        page = cand.get("page_index")
        sys_idx = cand.get("system_index")
        staff_idx = cand.get("staff_index")

        malformed_staff = (type(page) is not int or type(sys_idx) is not int or type(staff_idx) is not int)

        clef = None
        has_valid_clef = False
        has_assumed_clef = False
        is_ambiguous = False

        if not malformed_staff:
            if semantic_candidates is not None:
                sc_match = None
                for sc in semantic_candidates:
                    if sc.get("page_index") == page and sc.get("system_index") == sys_idx and sc.get("staff_index") == staff_idx:
                        sc_match = sc
                        break
                if sc_match is not None:
                    logical_clef = sc_match.get("logical_clef", {})
                    status = logical_clef.get("status")
                    clef_kind = logical_clef.get("clef_kind")
                    if status == "logical_clef_candidate" and clef_kind in ("treble", "bass", "alto"):
                        clef = clef_kind
                        has_valid_clef = True
                    elif status == "ambiguous_candidate":
                        is_ambiguous = True
            else:
                clef_count = clef_policy.get((page, sys_idx, staff_idx), 0)
                if clef_count == 1:
                    clef = "treble"
                    has_valid_clef = True
                elif clef_count > 1:
                    is_ambiguous = True

        if has_valid_clef:
            report["note_candidates_on_staves_with_valid_clef"] += 1
        elif assume_treble_clef and not has_valid_clef and not is_ambiguous:
            report["note_candidates_on_staves_with_assumed_clef"] += 1
            has_assumed_clef = True

        if cand.get("clef_resolved_staff_pitch"):
            report["note_candidates_with_clef_resolved_staff_pitch"] += 1
            if assume_treble_clef and not has_valid_clef:
                report["note_candidates_with_assumed_treble_clef_pitch"] += 1
            if type(pos) is int and 0 <= pos <= 8:
                report["in_staff_mapped_notes"] += 1
            else:
                report["out_of_staff_mapped_notes"] += 1
        else:
            reason = None
            if malformed_staff:
                report["skipped_staff_association_malformed"] += 1
                reason = "malformed_staff_association"
            elif is_ambiguous:
                report["skipped_clef_ambiguous"] += 1
                reason = "ambiguous_clef_evidence"
            elif not has_valid_clef and not has_assumed_clef:
                report["skipped_clef_missing"] += 1
                reason = "missing_clef_evidence"
            elif not has_pos:
                report["skipped_staff_position_malformed"] += 1
                reason = "malformed_staff_position"
            else:
                if type(pos) is int:
                    if pos < -12 or pos > 15:
                        reason = "pitch_out_of_range_or_unsupported"
                    elif pos < 0 or pos > 8:
                        report["skipped_missing_required_ledger_support"] += 1
                        reason = "missing_required_ledger_support"
                    else:
                        reason = "pitch_out_of_range_or_unsupported"
                else:
                    reason = "pitch_out_of_range_or_unsupported"

            if reason and len(report["sample_diagnostics"]) < 5:
                report["sample_diagnostics"].append({
                    "candidate_id": cand.get("candidate_id"),
                    "skip_reason": reason
                })

    return report


def map_ledger_lines_to_note_candidates(outcomes: list[dict]) -> None:
    candidate_lookup = {c.get("candidate_id"): c for c in outcomes if c.get("candidate_id")}

    valid_ledgers = []
    notes = []

    for cand in outcomes:
        st_type = cand.get("symbol_type")
        if st_type == "ledger_line_candidate":
            pos = cand.get("staff_position_index")
            if type(pos) is not int:
                continue
            bbox = cand.get("bbox")
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                continue
            try:
                float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            except (TypeError, ValueError):
                continue
            if cand.get("page_index") is None or cand.get("system_index") is None or cand.get("staff_index") is None:
                continue
            if not cand.get("candidate_id"):
                continue
            valid_ledgers.append(cand)
        elif st_type in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate"):
            notes.append(cand)

    for note in notes:
        n_pos = note.get("staff_position_index")
        if type(n_pos) is not int or 0 <= n_pos <= 8:
            continue

        n_page = note.get("page_index")
        n_sys = note.get("system_index")
        n_staff = note.get("staff_index")
        if n_page is None or n_sys is None or n_staff is None:
            continue

        n_bbox = None
        if note.get("symbol_type") in ("eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate"):
            q_id = note.get("quarter_component_id")
            if q_id:
                q_cand = candidate_lookup.get(q_id)
                if q_cand:
                    n_bbox = q_cand.get("bbox")
        else:
            n_bbox = note.get("bbox")

        if not isinstance(n_bbox, (list, tuple)) or len(n_bbox) != 4:
            continue
        try:
            nx0, ny0, nx1, ny1 = [float(v) for v in n_bbox]
        except (TypeError, ValueError):
            continue

        attached = []
        for l in valid_ledgers:
            if l.get("page_index") != n_page or l.get("system_index") != n_sys or l.get("staff_index") != n_staff:
                continue

            l_pos = l.get("staff_position_index")
            if n_pos < 0 and (l_pos >= 0 or l_pos < n_pos):
                continue
            if n_pos > 8 and (l_pos <= 8 or l_pos > n_pos):
                continue

            lx0, ly0, lx1, ly1 = [float(v) for v in l["bbox"]]
            if max(nx0, lx0) <= min(nx1, lx1):
                attached.append(l.get("candidate_id"))

        if attached:
            note["attached_ledger_line_candidate_ids"] = sorted(attached)

def run_recognition_on_file(
    pdf_path,
    include_x_aligned_clusters: bool = False,
    include_left_margin_candidates: bool = False,
    include_ledger_line_candidates: bool = False,
    include_flag_beam_candidates: bool = False,
    assume_treble_clef: bool = False
) -> dict | None:
    import sys
    import fitz  # type: ignore
    from score2gp.pdf_staff_notation_diagnostics import (
        _extract_whole_note_candidates,
        _extract_half_note_candidates,
        _extract_quarter_note_candidates,
        extract_notation_diagnostics_dict
    )

    if not pdf_path.exists():
        print(f"Error: File {pdf_path} not found", file=sys.stderr)
        return None

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening {pdf_path.name}: {e}", file=sys.stderr)
        return None

    whole_note_locations = []
    half_note_locations = []
    quarter_note_locations = []
    barline_locations = []
    x_aligned_cluster_locations = []
    left_margin_locations = []
    flag_locations = []
    beam_locations = []
    tie_locations = []
    dot_locations = []
    ledger_line_locations = []
    clef_locations = []
    semantic_candidates = []

    all_staff_geometries = []

    for i in range(len(doc)):
        page = doc[i]
        page_index = i + 1

        page_diags = extract_notation_diagnostics_dict(page, page_index)
        staves = page_diags.get("staves", [])

        all_staff_geometries.extend(map_staff_geometry_to_read_only_report(staves))

        clef_cands = extract_treble_clef_candidate_evidence(
            staves,
            page_index=page_index,
            start_index=len(clef_locations) + 1,
            page=page
        )
        clef_locations.extend(clef_cands)

        whole_cands = _extract_whole_note_candidates(page)
        shaped_whole = shape_whole_note_candidate_evidence(
            whole_cands,
            page_index=page_index,
            start_index=len(whole_note_locations) + 1
        )
        _associate_staves(shaped_whole, staves)
        whole_note_locations.extend(shaped_whole)

        half_cands = _extract_half_note_candidates(page)
        shaped_half = shape_half_note_candidate_evidence(
            half_cands,
            page_index=page_index,
            start_index=len(half_note_locations) + 1
        )
        _associate_staves(shaped_half, staves)
        half_note_locations.extend(shaped_half)

        quarter_cands = _extract_quarter_note_candidates(page)
        shaped_quarter = shape_quarter_note_candidate_evidence(
            quarter_cands,
            page_index=page_index,
            start_index=len(quarter_note_locations) + 1
        )
        _associate_staves(shaped_quarter, staves)
        quarter_note_locations.extend(shaped_quarter)

        if include_x_aligned_clusters:
            x_aligned_cands = []
            for staff in page_diags.get("staves", []):
                if staff.get("x_aligned_cluster_candidates"):
                    x_aligned_cands.extend(staff["x_aligned_cluster_candidates"])

            shaped_x_aligned = shape_x_aligned_cluster_candidate_evidence(
                x_aligned_cands,
                page_index=page_index,
                start_index=len(x_aligned_cluster_locations) + 1
            )
            x_aligned_cluster_locations.extend(shaped_x_aligned)

        if include_left_margin_candidates:
            left_margin_cands = []
            for staff in page_diags.get("staves", []):
                if staff.get("left_margin_candidates"):
                    left_margin_cands.extend(staff["left_margin_candidates"])

            shaped_left_margin = shape_left_margin_candidate_evidence(
                left_margin_cands,
                page_index=page_index,
                start_index=len(left_margin_locations) + 1
            )
            left_margin_locations.extend(shaped_left_margin)

        if include_ledger_line_candidates:
            x_aligned_cands_for_ledger = []
            for staff in page_diags.get("staves", []):
                if staff.get("x_aligned_cluster_candidates"):
                    x_aligned_cands_for_ledger.extend(staff["x_aligned_cluster_candidates"])

            ledger_cands = shape_ledger_line_candidate_evidence(
                x_aligned_cands_for_ledger,
                page_index=page_index,
                start_index=len(ledger_line_locations) + 1
            )
            ledger_line_locations.extend(ledger_cands)

        if include_flag_beam_candidates:
            ledger_suppression_keys = {
                (l.get("page_index"), l.get("system_index"), l.get("staff_index"), tuple(l["bbox"]))
                for l in ledger_line_locations
            } if include_ledger_line_candidates else set()

            for staff in page_diags.get("staves", []):
                fb = staff.get("flag_beam_candidates")
                if fb:
                    staff_geom = staff.get("staff", {})
                    sys_idx = staff_geom.get("system_index")
                    staff_idx = staff_geom.get("staff_index")

                    flags = fb.get("flags", [])
                    if flags:
                        shaped_flags = shape_flag_candidate_evidence(
                            flags,
                            page_index=page_index,
                            system_index=sys_idx,
                            staff_index=staff_idx,
                            start_index=len(flag_locations) + 1
                        )
                        flag_locations.extend(shaped_flags)

                    beams = fb.get("beams", [])
                    if beams:
                        filtered_beams = []
                        for b in beams:
                            b_dict = b if isinstance(b, dict) else (b.model_dump() if hasattr(b, "model_dump") else b.dict())
                            key = (page_index, sys_idx, staff_idx, tuple(b_dict["bbox"]))
                            if key not in ledger_suppression_keys:
                                filtered_beams.append(b)

                        shaped_beams = shape_beam_candidate_evidence(
                            filtered_beams,
                            page_index=page_index,
                            system_index=sys_idx,
                            staff_index=staff_idx,
                            start_index=len(beam_locations) + 1
                        )
                        beam_locations.extend(shaped_beams)

                    ties = staff.get("tie_candidates", [])
                    if ties:
                        shaped_ties = shape_tie_candidate_evidence(
                            ties,
                            page_index=page_index,
                            system_index=sys_idx,
                            staff_index=staff_idx,
                            start_index=len(tie_locations) + 1
                        )
                        tie_locations.extend(shaped_ties)

        dots = page_diags.get("dot_candidates", [])
        if dots:
            shaped_dots = shape_dot_candidate_evidence(
                dots,
                page_index=page_index,
                start_index=len(dot_locations) + 1
            )
            _associate_staves(shaped_dots, staves)
            dot_locations.extend(shaped_dots)

        # Extract page/staff-level semantic candidates using same logic as Req-119
        try:
            from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics
            from score2gp.pdf_geometry_candidate_extraction import extract_geometry_candidates
            from score2gp.pdf_candidate_semantic_gate import evaluate_logical_clef_gate
            from score2gp.pdf_candidate_quarter_rest import extract_quarter_rest_candidates
            from score2gp.pdf_candidate_whole_half_rest import extract_whole_half_rest_candidates
            from score2gp.pdf_candidate_eighth_sixteenth_rest import extract_eighth_sixteenth_rest_candidates
            from score2gp.pdf_staff_notation_diagnostics import (
                extract_notation_diagnostics_dict,
                extract_structural_skeleton_diagnostics_dict
            )

            diags_model = PdfStaffNotationGeometryDiagnostics.model_validate(page_diags)
            skeleton_diags = extract_structural_skeleton_diagnostics_dict(page, page_index)

            # Extract barline candidates from skeleton diagnostics
            skeleton_staves = {}
            skeleton_pages = skeleton_diags.get("pages", [])
            if skeleton_pages:
                for sys in skeleton_pages[0].get("systems", []):
                    for staff in sys.get("staves", []):
                        key = (page_index, sys.get("system_index"), staff.get("staff_index"))
                        skeleton_staves[key] = staff.get("barline_candidates", [])

            for staff_diag in diags_model.staves:
                sys_idx = staff_diag.staff.system_index
                staff_idx = staff_diag.staff.staff_index
                key = (page_index, sys_idx, staff_idx)
                barlines = skeleton_staves.get(key, [])
                confirmed = [bc for bc in barlines if bc.get("classification") == "confirmed_barline"]
                confirmed.sort(key=lambda bc: bc["x0"])

                merged = []
                skip_indices = set()
                for i in range(len(confirmed)):
                    if i in skip_indices:
                        continue
                    bc1 = confirmed[i]
                    if i + 1 < len(confirmed):
                        bc2 = confirmed[i+1]
                        dist = bc2["x0"] - bc1["x0"]
                        if dist <= 5.0:
                            w1 = bc1["x1"] - bc1["x0"]
                            w2 = bc2["x1"] - bc2["x0"]
                            is_final = (w1 >= 1.5 or w2 >= 1.5)
                            bar_style = "final" if is_final else "double"
                            merged.append({
                                "page_index": page_index,
                                "system_index": sys_idx,
                                "staff_index": staff_idx,
                                "bbox": [bc1["x0"], min(bc1["y0"], bc2["y0"]), bc2["x1"], max(bc1["y1"], bc2["y1"])],
                                "candidate_id": f"barline_{bc1['x0']}_{bc1['y0']}",
                                "symbol_type": "barline_candidate",
                                "barline_style": bar_style
                            })
                            skip_indices.add(i + 1)
                            continue

                    merged.append({
                        "page_index": page_index,
                        "system_index": sys_idx,
                        "staff_index": staff_idx,
                        "bbox": [bc1["x0"], bc1["y0"], bc1["x1"], bc1["y1"]],
                        "candidate_id": f"barline_{bc1['x0']}_{bc1['y0']}",
                        "symbol_type": "barline_candidate",
                        "barline_style": "simple"
                    })

                for m_bc in merged:
                    barline_locations.append(m_bc)

                geometry = extract_geometry_candidates(staff_diag)

                line_y_coords = staff_diag.staff.line_y_coords
                staff_spacing = (line_y_coords[-1] - line_y_coords[0]) / 4.0 if len(line_y_coords) == 5 else 10.0
                staff_height = line_y_coords[-1] - line_y_coords[0] if len(line_y_coords) == 5 else (staff_diag.staff.y1 - staff_diag.staff.y0)
                staff_x0 = staff_diag.staff.x0
                staff_center_y = sum(line_y_coords) / len(line_y_coords) if line_y_coords else (staff_diag.staff.y0 + staff_diag.staff.y1) / 2.0

                clef_res = evaluate_logical_clef_gate(geometry, staff_spacing, staff_height, staff_x0)
                qr_cands = extract_quarter_rest_candidates(geometry, staff_spacing, staff_center_y)
                whole_cands, half_cands = extract_whole_half_rest_candidates(geometry, staff_spacing, staff_center_y)
                eighth_cands, sixteenth_cands = extract_eighth_sixteenth_rest_candidates(geometry, staff_spacing, staff_center_y)

                semantic_candidates.append({
                    "page_index": page_index,
                    "system_index": staff_diag.staff.system_index,
                    "staff_index": staff_diag.staff.staff_index,
                    "logical_clef": clef_res.model_dump(mode="json"),
                    "quarter_rests": [qr.model_dump(mode="json") for qr in qr_cands],
                    "whole_rests": [wr.model_dump(mode="json") for wr in whole_cands],
                    "half_rests": [hr.model_dump(mode="json") for hr in half_cands],
                    "eighth_rests": [er.model_dump(mode="json") for er in eighth_cands],
                    "sixteenth_rests": [sr.model_dump(mode="json") for sr in sixteenth_cands]
                })
        except Exception as e:
            print("EXC:", e)
            import traceback
            traceback.print_exc()
            pass

    outcomes = map_whole_note_candidates_to_read_only_outcomes(whole_note_locations)
    outcomes.extend(map_half_note_candidates_to_read_only_outcomes(half_note_locations))
    outcomes.extend(map_quarter_note_candidates_to_read_only_outcomes(quarter_note_locations))
    outcomes.extend(map_treble_clef_candidates_to_read_only_outcomes(clef_locations))
    outcomes.extend(barline_locations)

    if include_x_aligned_clusters:
        outcomes.extend(map_x_aligned_cluster_candidates_to_read_only_outcomes(x_aligned_cluster_locations))

    if include_left_margin_candidates:
        outcomes.extend(map_left_margin_candidates_to_read_only_outcomes(left_margin_locations))

    if include_ledger_line_candidates:
        outcomes.extend(map_ledger_line_candidates_to_read_only_outcomes(ledger_line_locations))

    if include_flag_beam_candidates:
        outcomes.extend(map_flag_candidates_to_read_only_outcomes(flag_locations))
        outcomes.extend(map_beam_candidates_to_read_only_outcomes(beam_locations))
        outcomes.extend(map_tie_candidates_to_read_only_outcomes(tie_locations))
        outcomes.extend(map_dot_candidates_to_read_only_outcomes(dot_locations))

        composed_durations = compose_filled_duration_candidates(outcomes)
        outcomes.extend(composed_durations)
        apply_dots_to_notes(outcomes)

        from score2gp.quarter_rest_recogniser import extract_quarter_rest_candidates
        quarter_rests = extract_quarter_rest_candidates(outcomes)
        outcomes.extend(quarter_rests)

    map_staff_position_to_read_only_outcomes(outcomes, all_staff_geometries)
    if include_ledger_line_candidates:
        map_ledger_lines_to_note_candidates(outcomes)
    if assume_treble_clef:
        map_assumed_treble_pitch_to_read_only_outcomes(outcomes)

    map_clef_resolved_staff_pitch(outcomes, explicit_clef="treble" if assume_treble_clef else None, semantic_candidates=semantic_candidates)
    coverage_report = build_clef_resolved_pitch_coverage_report(outcomes, assume_treble_clef=assume_treble_clef, semantic_candidates=semantic_candidates)

    measure_anchors = extract_measure_anchors_from_text(pdf_path, all_staff_geometries)

    try:
        timeline_preview = build_staff_timeline_preview(
            outcomes,
            semantic_candidates,
            all_staff_geometries,
            measure_anchors=measure_anchors,
            pdf_path=pdf_path
        )
    except Exception:
        timeline_preview = []

    detected_meter = timeline_preview[0].get("detected_meter") if timeline_preview else None

    return {
        "source": pdf_path.name,
        "recognition_mode": "read_only_diagnostic_derived",
        "staff_geometry": all_staff_geometries,
        "read_only_recognition_outcomes": outcomes,
        "clef_resolved_pitch_coverage": coverage_report,
        "semantic_candidates": semantic_candidates,
        "timeline_preview": timeline_preview,
        "detected_meter": detected_meter
    }
