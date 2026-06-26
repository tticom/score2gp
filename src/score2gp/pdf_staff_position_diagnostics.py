from typing import Any, Literal
from pydantic import BaseModel, ConfigDict
from .pdf_staff_notation_diagnostics import extract_measure_bucket_diagnostics_dict, extract_notation_diagnostics_dict

class StaffPositionCandidateDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_index: int
    system_index: int
    staff_index: int
    measure_region_index: int
    candidate_type: str
    candidate_bbox: list[float]
    center_x: float
    center_y: float
    center_y_source: str
    staff_step_index: float | None = None
    nearest_staff_line_index: int | None = None
    nearest_staff_space_index: int | None = None
    staff_spacing: float | None = None
    staff_line_y_coords: list[float] | None = None
    position_status: Literal[
        "positioned",
        "ledger_positioned",
        "missing_staff_geometry",
        "outside_staff_bounds",
        "ambiguous_vertical_position",
        "ambiguous_notehead_center",
        "unsupported_candidate_type",
        "upstream_measure_bucket_failed",
        "upstream_assignment_failed"
    ]
    failure_reasons: list[str]

class StaffPositionDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    diagnostic_status: Literal["pass", "fail", "ambiguous"]
    positioned_candidates: list[StaffPositionCandidateDiagnostics]
    failure_reasons: list[str]

def extract_staff_position_diagnostics_dict(page: Any, page_index: int) -> dict[str, Any]:
    try:
        bucket_diags_dict = extract_measure_bucket_diagnostics_dict(page, page_index)
        geom_diags_dict = extract_notation_diagnostics_dict(page, page_index)

        staff_geom_map = {}
        if geom_diags_dict.get("status") != "fail":
            for staff_diag in geom_diags_dict.get("staves", []):
                s = staff_diag.get("staff", {})
                sys_idx = s.get("system_index")
                stf_idx = s.get("staff_index")
                if sys_idx is not None and stf_idx is not None:
                    staff_geom_map[(sys_idx, stf_idx)] = s

        if bucket_diags_dict.get("diagnostic_status") == "fail":
            return StaffPositionDiagnostics(
                diagnostic_status="fail",
                positioned_candidates=[],
                failure_reasons=["upstream_measure_bucket_failed"]
            ).model_dump()

        positioned_candidates = []
        for bucket in bucket_diags_dict.get("buckets", []):
            sys_idx = bucket.get("system_index")
            stf_idx = bucket.get("staff_index")
            mr_idx = bucket.get("measure_region_index")
            
            s_geom = staff_geom_map.get((sys_idx, stf_idx))

            for candidate in bucket.get("ordered_candidates", []):
                ctype = candidate.get("candidate_type")
                bbox = candidate.get("candidate_bbox", [0.0, 0.0, 0.0, 0.0])
                cx = candidate.get("center_x", 0.0)

                cy = (bbox[1] + bbox[3]) / 2.0
                center_y_source = "full_bbox_center"
                
                pos_status = "ambiguous_vertical_position"
                failure_reasons = []
                staff_step_index = None
                nearest_staff_line_index = None
                nearest_staff_space_index = None
                staff_spacing = None
                line_y_coords = None

                if ctype not in ("whole_note", "half_note", "quarter_note"):
                    pos_status = "unsupported_candidate_type"
                    failure_reasons.append("unsupported_candidate_type")
                elif not s_geom:
                    pos_status = "missing_staff_geometry"
                    failure_reasons.append("missing_staff_geometry")
                else:
                    line_y_coords = s_geom.get("line_y_coords", [])
                    if len(line_y_coords) >= 2:
                        staff_spacing = line_y_coords[1] - line_y_coords[0]
                        if staff_spacing > 0:
                            staff_step_index = (cy - line_y_coords[0]) / (staff_spacing / 2.0)
                            
                            nearest_int = round(staff_step_index)
                            if nearest_int % 2 == 0:
                                nearest_staff_line_index = nearest_int // 2
                            else:
                                nearest_staff_space_index = (nearest_int - 1) // 2
                            
                            if -1 <= staff_step_index <= 9:
                                if ctype in ("half_note", "quarter_note"):
                                    pos_status = "ambiguous_notehead_center"
                                    failure_reasons.append("unreliable_candidate_center")
                                else:
                                    pos_status = "positioned"
                            else:
                                pos_status = "ledger_positioned"
                                if ctype in ("half_note", "quarter_note"):
                                    # Still unreliable, but ledger position takes precedence in status, or we append to failure_reasons
                                    failure_reasons.append("unreliable_candidate_center")
                        else:
                            pos_status = "ambiguous_vertical_position"
                            failure_reasons.append("malformed_staff_spacing")
                    else:
                        pos_status = "ambiguous_vertical_position"
                        failure_reasons.append("missing_staff_lines")

                positioned_candidates.append(StaffPositionCandidateDiagnostics(
                    page_index=page_index,
                    system_index=sys_idx,
                    staff_index=stf_idx,
                    measure_region_index=mr_idx,
                    candidate_type=ctype,
                    candidate_bbox=bbox,
                    center_x=cx,
                    center_y=cy,
                    center_y_source=center_y_source,
                    staff_step_index=staff_step_index,
                    nearest_staff_line_index=nearest_staff_line_index,
                    nearest_staff_space_index=nearest_staff_space_index,
                    staff_spacing=staff_spacing,
                    staff_line_y_coords=line_y_coords,
                    position_status=pos_status,
                    failure_reasons=failure_reasons
                ))

        return StaffPositionDiagnostics(
            diagnostic_status="pass",
            positioned_candidates=positioned_candidates,
            failure_reasons=[]
        ).model_dump()
    except Exception as e:
        return {"diagnostic_status": "fail", "positioned_candidates": [], "failure_reasons": ["extraction_failed"]}
