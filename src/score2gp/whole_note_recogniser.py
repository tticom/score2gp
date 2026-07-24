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

from typing import Any, Iterable


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

        intersect_beams = []
        for b in beams:
            b_bbox = b.get("bbox")
            if b.get("page_index") == q_page and b.get("system_index") == q_sys and b.get("staff_index") == q_staff and is_valid_bbox(b_bbox):
                beam_y_margin = 2.0 if q_stem else 20.0
                if bboxes_intersect(full_bbox, b_bbox, x_margin=2.0, y_margin=beam_y_margin):
                    intersect_beams.append(b)

        units = 0
        modifiers = []
        if intersect_beams:
            units = len(intersect_beams)
            modifiers = intersect_beams
        else:
            flag_count = len(intersect_flags)
            if flag_count == 0:
                units = 0
            elif flag_count < 25:
                units = 1
            elif flag_count < 45:
                units = 2
            elif flag_count < 65:
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
            "duration": duration_type,
            "source": q.get("source"),
            "quarter_component_id": q.get("candidate_id"),
            "modifier_component_ids": mod_ids,
            "modifier_type": mod_type
        })
        idx += 1
        
        q["association_status"] = "suppressed"

    return composed_notes





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
