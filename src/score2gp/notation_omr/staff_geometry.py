"""Staff bounds, system clustering, and ledger line geometry."""

from typing import Any, Iterable
from .evidence import shape_candidate_evidence


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
