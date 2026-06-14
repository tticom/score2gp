from typing import Any, Iterable

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
        shaped.append({
            "candidate_id": candidate_id,
            "page_index": page_index,
            "bbox": get_bbox(cand)
        })
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
        outcomes.append({
            "symbol_type": "whole_note_candidate",
            "candidate_id": cand.get("candidate_id"),
            "bbox": cand.get("bbox"),
            "page_index": cand.get("page_index"),
            "system_index": cand.get("system_index"),
            "staff_index": cand.get("staff_index"),
            "source": "diagnostic_candidate_evidence"
        })
    return outcomes

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

def _associate_staves(shaped_candidates: list[dict], staves: list[dict]) -> None:
    if not staves:
        return
    for cand in shaped_candidates:
        bbox = cand.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        c_x0, c_y0, c_x1, c_y1 = bbox
        c_y = (c_y0 + c_y1) / 2.0
        best_staff = None
        best_dist = float('inf')
        for staff_dict in staves:
            staff = staff_dict.get("staff", {})
            if not staff:
                continue
            s_y0 = staff.get("y0", 0.0)
            s_y1 = staff.get("y1", 0.0)
            s_x0 = staff.get("x0", 0.0)
            s_x1 = staff.get("x1", 0.0)
            s_y = (s_y0 + s_y1) / 2.0

            staff_height = s_y1 - s_y0
            staff_space = staff_height / 4.0 if staff_height > 0 else 10.0

            vertical_margin = 6.0 * staff_space
            horizontal_margin = 1.0 * staff_space

            vertical_ok = (s_y0 - vertical_margin) <= c_y <= (s_y1 + vertical_margin)
            horizontal_ok = c_x1 >= (s_x0 - horizontal_margin) and c_x0 <= (s_x1 + horizontal_margin)

            if vertical_ok and horizontal_ok:
                dist = abs(c_y - s_y)
                if dist < best_dist:
                    best_dist = dist
                    best_staff = staff
        if best_staff:
            cand["system_index"] = best_staff.get("system_index")
            cand["staff_index"] = best_staff.get("staff_index")

def compose_eighth_note_candidates(outcomes: list[dict]) -> list[dict]:
    quarters = [o for o in outcomes if o.get("symbol_type") == "quarter_note_candidate"]
    flags = [o for o in outcomes if o.get("symbol_type") == "flag_candidate"]
    beams = [o for o in outcomes if o.get("symbol_type") == "beam_candidate"]

    def bboxes_intersect(b1, b2, x_margin=5.0, y_margin=40.0):
        # We need a large vertical margin to allow the beam to connect to the quarter notehead
        # across the height of the stem. Stem is roughly 30-35 points.
        return not (b1[2] < b2[0] - x_margin or
                    b1[0] > b2[2] + x_margin or
                    b1[3] < b2[1] - y_margin or
                    b1[1] > b2[3] + y_margin)

    def bboxes_strictly_overlap(b1, b2):
        # True if bboxes overlap in both dimensions without just touching edges
        return not (b1[2] <= b2[0] or
                    b1[0] >= b2[2] or
                    b1[3] <= b2[1] or
                    b1[1] >= b2[3])

    def bbox_union(b1, b2):
        return [
            min(b1[0], b2[0]),
            min(b1[1], b2[1]),
            max(b1[2], b2[2]),
            max(b1[3], b2[3])
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

    eighth_notes = []
    eighth_idx = 1

    for q in quarters:
        q_page = q.get("page_index")
        q_sys = q.get("system_index")
        q_staff = q.get("staff_index")
        q_bbox = q.get("bbox")

        if q_page is None or q_sys is None or q_staff is None or not is_valid_bbox(q_bbox):
            continue

        composed = False

        # Check flags
        for f in flags:
            f_bbox = f.get("bbox")
            if f.get("page_index") == q_page and f.get("system_index") == q_sys and f.get("staff_index") == q_staff and is_valid_bbox(f_bbox):
                # Ignore notehead quadrants incorrectly extracted as flag candidates.
                # A real flag does not strictly overlap the quarter notehead.
                if bboxes_strictly_overlap(q_bbox, f_bbox):
                    continue

                if bboxes_intersect(q_bbox, f_bbox, x_margin=5.0, y_margin=40.0):
                    eighth_notes.append({
                        "candidate_id": f"eighth_note_candidate_{eighth_idx:03d}",
                        "symbol_type": "eighth_note_candidate",
                        "page_index": q_page,
                        "system_index": q_sys,
                        "staff_index": q_staff,
                        "bbox": bbox_union(q_bbox, f_bbox),
                        "source": q.get("source"),
                        "quarter_component_id": q.get("candidate_id"),
                        "modifier_component_id": f.get("candidate_id"),
                        "modifier_type": "flag_candidate"
                    })
                    eighth_idx += 1
                    composed = True
                    break

        if composed:
            continue

        # Check beams
        for b in beams:
            b_bbox = b.get("bbox")
            if b.get("page_index") == q_page and b.get("system_index") == q_sys and b.get("staff_index") == q_staff and is_valid_bbox(b_bbox):
                if bboxes_intersect(q_bbox, b_bbox, x_margin=5.0, y_margin=40.0):
                    eighth_notes.append({
                        "candidate_id": f"eighth_note_candidate_{eighth_idx:03d}",
                        "symbol_type": "eighth_note_candidate",
                        "page_index": q_page,
                        "system_index": q_sys,
                        "staff_index": q_staff,
                        "bbox": bbox_union(q_bbox, b_bbox),
                        "source": q.get("source"),
                        "quarter_component_id": q.get("candidate_id"),
                        "modifier_component_id": b.get("candidate_id"),
                        "modifier_type": "beam_candidate"
                    })
                    eighth_idx += 1
                    composed = True
                    break

    return eighth_notes

def run_recognition_on_file(
    pdf_path,
    include_x_aligned_clusters: bool = False,
    include_left_margin_candidates: bool = False,
    include_flag_beam_candidates: bool = False
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

    for i in range(len(doc)):
        page = doc[i]
        page_index = i + 1

        page_diags = extract_notation_diagnostics_dict(page, page_index)
        staves = page_diags.get("staves", [])

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

        if include_flag_beam_candidates:
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
                        shaped_beams = shape_beam_candidate_evidence(
                            beams,
                            page_index=page_index,
                            system_index=sys_idx,
                            staff_index=staff_idx,
                            start_index=len(beam_locations) + 1
                        )
                        beam_locations.extend(shaped_beams)

    outcomes = map_whole_note_candidates_to_read_only_outcomes(whole_note_locations)
    outcomes.extend(map_half_note_candidates_to_read_only_outcomes(half_note_locations))
    outcomes.extend(map_quarter_note_candidates_to_read_only_outcomes(quarter_note_locations))

    if include_x_aligned_clusters:
        outcomes.extend(map_x_aligned_cluster_candidates_to_read_only_outcomes(x_aligned_cluster_locations))

    if include_left_margin_candidates:
        outcomes.extend(map_left_margin_candidates_to_read_only_outcomes(left_margin_locations))

    if include_flag_beam_candidates:
        outcomes.extend(map_flag_candidates_to_read_only_outcomes(flag_locations))
        outcomes.extend(map_beam_candidates_to_read_only_outcomes(beam_locations))

        eighth_notes = compose_eighth_note_candidates(outcomes)
        outcomes.extend(eighth_notes)

    return {
        "source": pdf_path.name,
        "recognition_mode": "read_only_diagnostic_derived",
        "read_only_recognition_outcomes": outcomes
    }
