from .notation_omr.evidence import shape_candidate_evidence
from .notation_omr.staff_geometry import (
    _associate_staves,
    map_ledger_line_candidates_to_read_only_outcomes,
    map_ledger_lines_to_note_candidates,
    map_staff_geometry_to_read_only_report,
    shape_ledger_line_candidate_evidence,
)
from .notation_omr.clef import (
    build_clef_resolved_pitch_coverage_report,
    extract_treble_clef_candidate_evidence,
    map_treble_clef_candidates_to_read_only_outcomes,
)
from .notation_omr.pitch import (
    map_assumed_treble_pitch_to_read_only_outcomes,
    map_clef_resolved_staff_pitch,
    map_staff_position_to_read_only_outcomes,
)
from .notation_omr.notehead import (
    map_half_note_candidates_to_read_only_outcomes,
    map_left_margin_candidates_to_read_only_outcomes,
    map_quarter_note_candidates_to_read_only_outcomes,
    map_whole_note_candidates_to_intermediate_notes,
    map_whole_note_candidates_to_read_only_outcomes,
    map_x_aligned_cluster_candidates_to_read_only_outcomes,
    shape_half_note_candidate_evidence,
    shape_left_margin_candidate_evidence,
    shape_quarter_note_candidate_evidence,
    shape_whole_note_candidate_evidence,
    shape_x_aligned_cluster_candidate_evidence,
)
from .notation_omr.duration import (
    compose_filled_duration_candidates,
    map_beam_candidates_to_read_only_outcomes,
    map_flag_candidates_to_read_only_outcomes,
    shape_beam_candidate_evidence,
    shape_flag_candidate_evidence,
)

from typing import Any, Iterable























def build_staff_timeline_preview(
    outcomes: list[dict],
    semantic_candidates: list[dict] | None = None,
    all_staff_geometries: list[dict] | None = None
) -> list[dict]:
    # Group note and barline candidates by (page, sys, staff)
    staves = {}
    for cand in outcomes:
        st_type = cand.get("symbol_type")
        is_note = st_type in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate")
        is_barline = st_type in ("barline_candidate", "barline")
        is_rest = st_type in ("quarter_rest_candidate", "quarter_rest", "whole_rest_candidate", "whole_rest", "half_rest_candidate", "half_rest")
        if not (is_note or is_barline or is_rest):
            continue

        page = cand.get("page_index")
        sys_idx = cand.get("system_index")
        staff_idx = cand.get("staff_index")
        if type(page) is not int or type(sys_idx) is not int or type(staff_idx) is not int:
            continue

        key = (page, sys_idx, staff_idx)
        if key not in staves:
            staves[key] = {
                "notes_rests_barlines": [],
                "geometry": None
            }
        staves[key]["notes_rests_barlines"].append(cand)

    # Collect rests from semantic_candidates
    if semantic_candidates is not None:
        for sc in semantic_candidates:
            page = sc.get("page_index")
            sys_idx = sc.get("system_index")
            staff_idx = sc.get("staff_index")
            if type(page) is not int or type(sys_idx) is not int or type(staff_idx) is not int:
                continue

            key = (page, sys_idx, staff_idx)
            if key not in staves:
                staves[key] = {
                    "notes_rests_barlines": [],
                    "geometry": None
                }

            # Gather rests from sc
            for r_type, dur in [("quarter_rests", 960), ("whole_rests", 3840), ("half_rests", 1920)]:
                rests = sc.get(r_type, [])
                for r in rests:
                    rest_cand = {
                        "symbol_type": r_type[:-1] + "_candidate",  # e.g. "quarter_rest_candidate"
                        "page_index": page,
                        "system_index": sys_idx,
                        "staff_index": staff_idx,
                        "duration_ticks": dur
                    }
                    if "bbox" in r:
                        rest_cand["bbox"] = r["bbox"]
                    if "x0" in r:
                        rest_cand["x0"] = r["x0"]
                    if "y0" in r:
                        rest_cand["y0"] = r["y0"]
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

    def get_x_coord(c):
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
        "half_rest": 1920
    }

    timeline_previews = []

    for key, data in staves.items():
        page, sys_idx, staff_idx = key
        cands = data["notes_rests_barlines"]
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

        # Sort all candidates chronologically by horizontal coordinate
        sorted_cands = sorted(cands, key=get_x_coord)

        # Split candidates into measures separated by barlines
        measures = []
        current_measure_cands = []
        for cand in sorted_cands:
            st_type = cand.get("symbol_type")
            is_barline = st_type in ("barline_candidate", "barline")
            if is_barline:
                if current_measure_cands:
                    measures.append(current_measure_cands)
                    current_measure_cands = []
            else:
                current_measure_cands.append(cand)
        if current_measure_cands:
            measures.append(current_measure_cands)

        timeline_measures = []

        for m_idx, m_cands in enumerate(measures):
            # Cluster measure candidates into vertical time slices
            time_slices = []
            current_slice = []
            for c in sorted(m_cands, key=get_x_coord):
                if not current_slice:
                    current_slice.append(c)
                else:
                    prev_x = get_x_coord(current_slice[-1])
                    curr_x = get_x_coord(c)
                    if curr_x - prev_x < X_tol:
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
                    elif "stem_direction" in c or "stem" in c:
                        stem = c.get("stem_direction") or c.get("stem")
                        if isinstance(stem, str) and "down" in stem.lower():
                            voice = 2
                    elif "rest" in c.get("symbol_type", ""):
                        # Determine rest vertical position
                        y_center = None
                        if "bbox" in c and isinstance(c["bbox"], (list, tuple)) and len(c["bbox"]) >= 4:
                            y_center = (c["bbox"][1] + c["bbox"][3]) / 2.0
                        else:
                            y_center = c.get("y0")

                        if middle_y is not None and y_center is not None:
                            if y_center > middle_y:
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

                # Process voice 1
                for c in slice_v1:
                    dur = TICK_MAPPINGS.get(c.get("symbol_type"), 960)
                    if "duration_ticks" in c:
                        dur = c["duration_ticks"]
                    c["timeline_start_tick"] = start_tick
                    c["timeline_duration_ticks"] = dur
                    measure_events.append({
                        "candidate_id": c.get("candidate_id"),
                        "symbol_type": c.get("symbol_type"),
                        "voice": 1,
                        "start_tick": start_tick,
                        "duration_ticks": dur,
                        "resolved_pitch": c.get("clef_resolved_staff_pitch")
                    })
                    cursor_1 = max(cursor_1, start_tick + dur)

                # Process voice 2
                for c in slice_v2:
                    dur = TICK_MAPPINGS.get(c.get("symbol_type"), 960)
                    if "duration_ticks" in c:
                        dur = c["duration_ticks"]
                    c["timeline_start_tick"] = start_tick
                    c["timeline_duration_ticks"] = dur
                    measure_events.append({
                        "candidate_id": c.get("candidate_id"),
                        "symbol_type": c.get("symbol_type"),
                        "voice": 2,
                        "start_tick": start_tick,
                        "duration_ticks": dur,
                        "resolved_pitch": c.get("clef_resolved_staff_pitch")
                    })
                    cursor_2 = max(cursor_2, start_tick + dur)

            # Pad measure voices up to expected duration
            D_measure = 3840
            if cursor_1 < D_measure:
                measure_events.append({
                    "candidate_id": None,
                    "symbol_type": "padding_rest",
                    "voice": 1,
                    "start_tick": cursor_1,
                    "duration_ticks": D_measure - cursor_1,
                    "resolved_pitch": None
                })
                cursor_1 = D_measure
            elif cursor_1 > D_measure:
                invalid = True

            if cursor_2 < D_measure:
                measure_events.append({
                    "candidate_id": None,
                    "symbol_type": "padding_rest",
                    "voice": 2,
                    "start_tick": cursor_2,
                    "duration_ticks": D_measure - cursor_2,
                    "resolved_pitch": None
                })
                cursor_2 = D_measure
            elif cursor_2 > D_measure:
                invalid = True

            # Sort events by start_tick then voice
            measure_events = sorted(measure_events, key=lambda e: (e["start_tick"], e["voice"]))

            timeline_measures.append({
                "measure_index": m_idx + 1,
                "valid": not invalid,
                "voice_1_final_tick": cursor_1,
                "voice_2_final_tick": cursor_2,
                "events": measure_events
            })

        timeline_previews.append({
            "page_index": page,
            "system_index": sys_idx,
            "staff_index": staff_idx,
            "measures": timeline_measures
        })

    return timeline_previews




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
    x_aligned_cluster_locations = []
    left_margin_locations = []
    flag_locations = []
    beam_locations = []
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

        # Extract page/staff-level semantic candidates using same logic as Req-119
        try:
            from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics
            from score2gp.pdf_geometry_candidate_extraction import extract_geometry_candidates
            from score2gp.pdf_candidate_semantic_gate import evaluate_logical_clef_gate
            from score2gp.pdf_candidate_quarter_rest import extract_quarter_rest_candidates
            from score2gp.pdf_candidate_whole_half_rest import extract_whole_half_rest_candidates

            diags_model = PdfStaffNotationGeometryDiagnostics.model_validate(page_diags)
            for staff_diag in diags_model.staves:
                geometry = extract_geometry_candidates(staff_diag)

                line_y_coords = staff_diag.staff.line_y_coords
                staff_spacing = (line_y_coords[-1] - line_y_coords[0]) / 4.0 if len(line_y_coords) == 5 else 10.0
                staff_height = line_y_coords[-1] - line_y_coords[0] if len(line_y_coords) == 5 else (staff_diag.staff.y1 - staff_diag.staff.y0)
                staff_x0 = staff_diag.staff.x0
                staff_center_y = sum(line_y_coords) / len(line_y_coords) if line_y_coords else (staff_diag.staff.y0 + staff_diag.staff.y1) / 2.0

                clef_res = evaluate_logical_clef_gate(geometry, staff_spacing, staff_height, staff_x0)
                qr_cands = extract_quarter_rest_candidates(geometry, staff_spacing, staff_center_y)
                whole_cands, half_cands = extract_whole_half_rest_candidates(geometry, staff_spacing, staff_center_y)

                semantic_candidates.append({
                    "page_index": page_index,
                    "system_index": staff_diag.staff.system_index,
                    "staff_index": staff_diag.staff.staff_index,
                    "logical_clef": clef_res.model_dump(mode="json"),
                    "quarter_rests": [qr.model_dump(mode="json") for qr in qr_cands],
                    "whole_rests": [wr.model_dump(mode="json") for wr in whole_cands],
                    "half_rests": [hr.model_dump(mode="json") for hr in half_cands]
                })
        except Exception:
            pass

    outcomes = map_whole_note_candidates_to_read_only_outcomes(whole_note_locations)
    outcomes.extend(map_half_note_candidates_to_read_only_outcomes(half_note_locations))
    outcomes.extend(map_quarter_note_candidates_to_read_only_outcomes(quarter_note_locations))
    outcomes.extend(map_treble_clef_candidates_to_read_only_outcomes(clef_locations))

    if include_x_aligned_clusters:
        outcomes.extend(map_x_aligned_cluster_candidates_to_read_only_outcomes(x_aligned_cluster_locations))

    if include_left_margin_candidates:
        outcomes.extend(map_left_margin_candidates_to_read_only_outcomes(left_margin_locations))

    if include_ledger_line_candidates:
        outcomes.extend(map_ledger_line_candidates_to_read_only_outcomes(ledger_line_locations))

    if include_flag_beam_candidates:
        outcomes.extend(map_flag_candidates_to_read_only_outcomes(flag_locations))
        outcomes.extend(map_beam_candidates_to_read_only_outcomes(beam_locations))

        composed_durations = compose_filled_duration_candidates(outcomes)
        outcomes.extend(composed_durations)

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

    try:
        timeline_preview = build_staff_timeline_preview(outcomes, semantic_candidates, all_staff_geometries)
    except Exception:
        timeline_preview = []

    return {
        "source": pdf_path.name,
        "recognition_mode": "read_only_diagnostic_derived",
        "staff_geometry": all_staff_geometries,
        "read_only_recognition_outcomes": outcomes,
        "clef_resolved_pitch_coverage": coverage_report,
        "semantic_candidates": semantic_candidates,
        "timeline_preview": timeline_preview
    }
