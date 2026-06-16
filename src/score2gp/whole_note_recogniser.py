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
                if not (hx1 < cx0 or hx0 > cx1 or hy1 < cy0 or hy0 > cy1):
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

def map_staff_position_to_read_only_outcomes(outcomes: list[dict], staff_geometries: list[dict]) -> None:
    staff_geom_lookup = {}
    for sg in staff_geometries:
        key = (sg.get("page_index"), sg.get("system_index"), sg.get("staff_index"))
        staff_geom_lookup[key] = sg

    candidate_lookup = {c.get("candidate_id"): c for c in outcomes if c.get("candidate_id")}

    for cand in outcomes:
        st_type = cand.get("symbol_type")
        if st_type not in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate", "ledger_line_candidate"):
            continue

        sg_key = (cand.get("page_index"), cand.get("system_index"), cand.get("staff_index"))
        sg = staff_geom_lookup.get(sg_key)
        if not sg:
            continue

        line_y_coords = sg.get("line_y_coords")
        if not line_y_coords or not isinstance(line_y_coords, list) or len(line_y_coords) != 5:
            continue

        try:
            line_y_coords = [float(y) for y in line_y_coords]
        except (TypeError, ValueError):
            continue

        notehead_y = None
        if st_type == "eighth_note_candidate":
            q_id = cand.get("quarter_component_id")
            if not q_id:
                continue
            q_cand = candidate_lookup.get(q_id)
            if not q_cand:
                continue
            bbox = q_cand.get("bbox")
        else:
            bbox = cand.get("bbox")
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
            continue

        pos_float = (notehead_y - line_y_coords[0]) / (staff_space / 2.0)
        cand["staff_position_index"] = int(round(pos_float))

def map_assumed_treble_pitch_to_read_only_outcomes(outcomes: list[dict]) -> None:
    pitches = ["F5", "E5", "D5", "C5", "B4", "A4", "G4", "F4", "E4"]
    for cand in outcomes:
        if cand.get("symbol_type") == "ledger_line_candidate":
            continue
        pos_idx = cand.get("staff_position_index")
        if type(pos_idx) is int and 0 <= pos_idx <= 8:
            cand["assumed_treble_pitch"] = pitches[pos_idx]

def map_clef_resolved_staff_pitch(outcomes: list[dict], explicit_clef: str | None = None) -> None:
    if not explicit_clef or explicit_clef != "treble":
        return

    pitches = [
        "F6", "E6", "D6", "C6", "B5", "A5", "G5", # -7 to -1
        "F5", "E5", "D5", "C5", "B4", "A4", "G4", "F4", "E4", # 0 to 8
        "D4", "C4", "B3", "A3", "G3", "F3", "E3" # 9 to 15
    ]

    for cand in outcomes:
        st_type = cand.get("symbol_type")
        if st_type not in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate"):
            continue

        pos = cand.get("staff_position_index")
        if type(pos) is not int:
            continue

        idx = pos + 7
        if idx < 0 or idx >= len(pitches):
            continue

        pitch = pitches[idx]

        required_ledgers = 0
        if pos < 0:
            required_ledgers = abs(pos) // 2
        elif pos > 8:
            required_ledgers = (pos - 8) // 2

        if required_ledgers > 0:
            attached = cand.get("attached_ledger_line_candidate_ids")
            if type(attached) is not list or len(attached) != required_ledgers:
                continue

        cand["clef_resolved_staff_pitch"] = pitch


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
        elif st_type in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate"):
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
        if note.get("symbol_type") == "eighth_note_candidate":
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
    include_flag_beam_candidates: bool = False,
    assume_treble_clef: bool = False,
    include_ledger_line_candidates: bool = False
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

    all_staff_geometries = []

    for i in range(len(doc)):
        page = doc[i]
        page_index = i + 1

        page_diags = extract_notation_diagnostics_dict(page, page_index)
        staves = page_diags.get("staves", [])

        all_staff_geometries.extend(map_staff_geometry_to_read_only_report(staves))

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

    outcomes = map_whole_note_candidates_to_read_only_outcomes(whole_note_locations)
    outcomes.extend(map_half_note_candidates_to_read_only_outcomes(half_note_locations))
    outcomes.extend(map_quarter_note_candidates_to_read_only_outcomes(quarter_note_locations))

    if include_x_aligned_clusters:
        outcomes.extend(map_x_aligned_cluster_candidates_to_read_only_outcomes(x_aligned_cluster_locations))

    if include_left_margin_candidates:
        outcomes.extend(map_left_margin_candidates_to_read_only_outcomes(left_margin_locations))

    if include_ledger_line_candidates:
        outcomes.extend(map_ledger_line_candidates_to_read_only_outcomes(ledger_line_locations))

    if include_flag_beam_candidates:
        outcomes.extend(map_flag_candidates_to_read_only_outcomes(flag_locations))
        outcomes.extend(map_beam_candidates_to_read_only_outcomes(beam_locations))

        eighth_notes = compose_eighth_note_candidates(outcomes)
        outcomes.extend(eighth_notes)

    map_staff_position_to_read_only_outcomes(outcomes, all_staff_geometries)
    if include_ledger_line_candidates:
        map_ledger_lines_to_note_candidates(outcomes)
    if assume_treble_clef:
        map_assumed_treble_pitch_to_read_only_outcomes(outcomes)

    return {
        "source": pdf_path.name,
        "recognition_mode": "read_only_diagnostic_derived",
        "staff_geometry": all_staff_geometries,
        "read_only_recognition_outcomes": outcomes
    }
