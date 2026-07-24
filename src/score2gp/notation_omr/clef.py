"""Clef evidence extraction and clef coverage diagnostics."""

from typing import Any


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
    from ..logical_clef_candidate_classifier import classify_logical_clef_candidate
    from ..pdf_geometry_candidates import LeftMarginPrimitiveCandidate

    raster_staffs = []
    if page is not None:
        try:
            from ..pdf_raster_staff_diagnostics import build_raster_notation_diagnostics
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
                    if pos < -7 or pos > 15:
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
