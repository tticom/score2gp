"""Flag and beam evidence with filled-note duration composition."""

from typing import Any, Iterable


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
