"""Top-level notation OMR recognition facade."""

from .clef import (
    build_clef_resolved_pitch_coverage_report,
    extract_treble_clef_candidate_evidence,
    map_treble_clef_candidates_to_read_only_outcomes,
)
from .duration import (
    compose_filled_duration_candidates,
    map_beam_candidates_to_read_only_outcomes,
    map_flag_candidates_to_read_only_outcomes,
    shape_beam_candidate_evidence,
    shape_flag_candidate_evidence,
)
from .notehead import (
    map_half_note_candidates_to_read_only_outcomes,
    map_left_margin_candidates_to_read_only_outcomes,
    map_quarter_note_candidates_to_read_only_outcomes,
    map_whole_note_candidates_to_read_only_outcomes,
    map_x_aligned_cluster_candidates_to_read_only_outcomes,
    shape_half_note_candidate_evidence,
    shape_left_margin_candidate_evidence,
    shape_quarter_note_candidate_evidence,
    shape_whole_note_candidate_evidence,
    shape_x_aligned_cluster_candidate_evidence,
)
from .pitch import (
    map_assumed_treble_pitch_to_read_only_outcomes,
    map_clef_resolved_staff_pitch,
    map_staff_position_to_read_only_outcomes,
)
from .staff_geometry import (
    _associate_staves,
    map_ledger_line_candidates_to_read_only_outcomes,
    map_ledger_lines_to_note_candidates,
    map_staff_geometry_to_read_only_report,
    shape_ledger_line_candidate_evidence,
)
from .timeline import build_staff_timeline_preview


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
