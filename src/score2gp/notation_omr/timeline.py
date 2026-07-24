"""Staff timeline preview generation."""


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
                    evt1 = {
                        "candidate_id": c.get("candidate_id"),
                        "symbol_type": c.get("symbol_type"),
                        "voice": 1,
                        "start_tick": start_tick,
                        "duration_ticks": dur,
                        "resolved_pitch": c.get("clef_resolved_staff_pitch")
                    }
                    if "tuplet_association" in c:
                        evt1["tuplet_association"] = c["tuplet_association"]
                    measure_events.append(evt1)
                    cursor_1 = max(cursor_1, start_tick + dur)

                # Process voice 2
                for c in slice_v2:
                    dur = TICK_MAPPINGS.get(c.get("symbol_type"), 960)
                    if "duration_ticks" in c:
                        dur = c["duration_ticks"]
                    c["timeline_start_tick"] = start_tick
                    c["timeline_duration_ticks"] = dur
                    evt2 = {
                        "candidate_id": c.get("candidate_id"),
                        "symbol_type": c.get("symbol_type"),
                        "voice": 2,
                        "start_tick": start_tick,
                        "duration_ticks": dur,
                        "resolved_pitch": c.get("clef_resolved_staff_pitch")
                    }
                    if "tuplet_association" in c:
                        evt2["tuplet_association"] = c["tuplet_association"]
                    measure_events.append(evt2)
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
