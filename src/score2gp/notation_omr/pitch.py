"""Staff-position and clef-resolved pitch mapping."""


def map_staff_position_to_read_only_outcomes(outcomes: list[dict], staff_geometries: list[dict]) -> None:
    staff_geom_lookup = {}
    for sg in staff_geometries:
        key = (sg.get("page_index"), sg.get("system_index"), sg.get("staff_index"))
        staff_geom_lookup[key] = sg

    candidate_lookup = {c.get("candidate_id"): c for c in outcomes if c.get("candidate_id")}

    for cand in outcomes:
        st_type = cand.get("symbol_type")
        if st_type not in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate", "ledger_line_candidate", "x_aligned_cluster_candidate"):
            continue

        if cand.get("association_status") in ("failed", "suppressed"):
            continue

        sg_key = (cand.get("page_index"), cand.get("system_index"), cand.get("staff_index"))
        sg = staff_geom_lookup.get(sg_key)
        if not sg:
            cand["association_status"] = "failed"
            cand["association_reason"] = "missing_staff_geometry"
            continue

        line_y_coords = sg.get("line_y_coords")
        if not line_y_coords or not isinstance(line_y_coords, list) or len(line_y_coords) != 5:
            cand["association_status"] = "failed"
            cand["association_reason"] = "missing_staff_line_coordinates"
            continue

        try:
            line_y_coords = [float(y) for y in line_y_coords]
        except (TypeError, ValueError):
            cand["association_status"] = "failed"
            cand["association_reason"] = "malformed_staff_line_coordinates"
            continue

        notehead_y = None
        if st_type == "x_aligned_cluster_candidate":
            primitives = cand.get("primitives", [])
            ys = []
            has_notehead_like = False
            for p in primitives:
                if p.get("kind") in ("text_span", "curve", "rectangle"):
                    has_notehead_like = True
                if "y0" in p and "y1" in p:
                    ys.extend([p["y0"], p["y1"]])
            if ys and has_notehead_like:
                notehead_y = (min(ys) + max(ys)) / 2.0
            else:
                continue
        elif st_type in ("eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate"):
            q_id = cand.get("quarter_component_id")
            if not q_id:
                continue
            q_cand = candidate_lookup.get(q_id)
            if not q_cand:
                continue
            bbox = q_cand.get("bbox")
        else:
            bbox = cand.get("bbox")

        if notehead_y is None:
            if "origin_y" in cand and cand["origin_y"] is not None:
                notehead_y = float(cand["origin_y"])
            else:
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
            cand["association_status"] = "failed"
            cand["association_reason"] = "malformed_staff_spacing"
            continue

        pos_float = (notehead_y - line_y_coords[0]) / (staff_space / 2.0)
        cand["staff_position_index"] = int(round(pos_float))
        cand["association_status"] = "success"

def map_assumed_treble_pitch_to_read_only_outcomes(outcomes: list[dict]) -> None:
    pitches = ["F5", "E5", "D5", "C5", "B4", "A4", "G4", "F4", "E4"]
    for cand in outcomes:
        if cand.get("symbol_type") in ("ledger_line_candidate",):
            continue
        pos_idx = cand.get("staff_position_index")
        if type(pos_idx) is int and 0 <= pos_idx <= 8:
            cand["assumed_treble_pitch"] = pitches[pos_idx]

def map_clef_resolved_staff_pitch(
    outcomes: list[dict],
    explicit_clef: str | None = None,
    semantic_candidates: list[dict] | None = None,
    explicit_key_signature: str | None = None
) -> None:
    from score2gp.pdf_pitch_mapper import (
        map_staff_step_to_midi_pitch,
        midi_to_note_name,
        get_spelled_note_name,
        KEY_SIGNATURE_ALTERATIONS,
        LOCAL_ACCIDENTAL_MODIFIERS
    )

    clef_map = {}

    if explicit_clef is not None:
        pass
    elif semantic_candidates is not None:
        for sc in semantic_candidates:
            page = sc.get("page_index")
            sys_idx = sc.get("system_index")
            staff_idx = sc.get("staff_index")
            if type(page) is not int or type(sys_idx) is not int or type(staff_idx) is not int:
                continue
            logical_clef = sc.get("logical_clef", {})
            status = logical_clef.get("status")
            clef_kind = logical_clef.get("clef_kind")
            if status == "logical_clef_candidate" and clef_kind in ("treble", "bass", "alto"):
                clef_map[(page, sys_idx, staff_idx)] = clef_kind
    else:
        # Legacy fallback
        for cand in outcomes:
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
                if key in clef_map:
                    clef_map[key] = "AMBIGUOUS"
                else:
                    clef_map[key] = "treble"
        # Filter out ambiguous keys
        clef_map = {k: v for k, v in clef_map.items() if v != "AMBIGUOUS"}

    # Group all notes and barlines by (page, sys_idx, staff_idx)
    groups = {}
    for cand in outcomes:
        st_type = cand.get("symbol_type")
        is_note = st_type in ("whole_note_candidate", "half_note_candidate", "quarter_note_candidate", "eighth_note_candidate", "sixteenth_note_candidate", "thirty_second_note_candidate", "sixty_fourth_note_candidate")
        is_barline = st_type in ("barline_candidate", "barline")
        if not (is_note or is_barline):
            continue

        page = cand.get("page_index")
        sys_idx = cand.get("system_index")
        staff_idx = cand.get("staff_index")

        # Fallback key if indices are missing but explicit_clef is provided
        if (page is None or sys_idx is None or staff_idx is None) and explicit_clef is not None:
            key = (0, 0, 0)
        else:
            if type(page) is not int or type(sys_idx) is not int or type(staff_idx) is not int:
                continue
            key = (page, sys_idx, staff_idx)

        if key not in groups:
            groups[key] = []
        groups[key].append(cand)

    def get_x_coord(c):
        if "bbox" in c and isinstance(c["bbox"], (list, tuple)) and len(c["bbox"]) >= 1:
            return c["bbox"][0]
        return c.get("x0", 0.0)

    # Process each staff group
    for key, cands in groups.items():
        # Resolve clef
        if explicit_clef is not None:
            clef = explicit_clef
        else:
            clef = clef_map.get(key)

        if clef not in ("treble", "bass", "alto"):
            continue

        # Resolve key signature
        key_sig = "C Major"
        if explicit_key_signature is not None:
            key_sig = explicit_key_signature
        elif semantic_candidates is not None:
            for sc in semantic_candidates:
                sc_page = sc.get("page_index")
                sc_sys = sc.get("system_index")
                sc_staff = sc.get("staff_index")
                if sc_page == key[0] and sc_sys == key[1] and sc_staff == key[2]:
                    # Nested key signature candidate check
                    ks_obj = sc.get("key_signature")
                    if isinstance(ks_obj, dict):
                        key_sig = ks_obj.get("key_kind", "C Major")
                    elif sc.get("symbol_type") == "key_signature_candidate":
                        key_sig = sc.get("key_kind", "C Major")
                    break

        if key_sig not in KEY_SIGNATURE_ALTERATIONS:
            key_sig = "C Major"

        sig_alts = KEY_SIGNATURE_ALTERATIONS[key_sig]

        # Sort candidates chronologically (by x coord)
        sorted_cands = sorted(cands, key=get_x_coord)

        measure_memory = {}  # maps (letter, octave) to local modifier offset (semitones)

        for cand in sorted_cands:
            st_type = cand.get("symbol_type")
            is_barline = st_type in ("barline_candidate", "barline")

            if is_barline:
                measure_memory.clear()
                continue

            # Process note candidate
            pos = cand.get("staff_position_index")
            if type(pos) is not int:
                continue

            # Keep ledger bounds check
            if pos < -7 or pos > 15:
                continue

            # Explicit check for staff bounds compat
            if pos < 0 or pos > 8:
                required_ledgers = 0
                if pos < 0:
                    required_ledgers = abs(pos) // 2
                elif pos > 8:
                    required_ledgers = (pos - 8) // 2

                if "attached_ledger_line_candidate_ids" in cand:
                    attached = cand["attached_ledger_line_candidate_ids"]
                    if type(attached) is not list or len(attached) != required_ledgers:
                        continue
                else:
                    if required_ledgers > 0:
                        continue

            try:
                natural_midi = map_staff_step_to_midi_pitch(pos, clef)
                natural_name = midi_to_note_name(natural_midi)
                letter = natural_name[0]
                octave = int(natural_name[1:])

                # Resolve modifier based on precedence rules
                # Level 1: Direct local accidental
                cand_acc = cand.get("accidental")
                acc_val = None
                if cand_acc is not None:
                    if isinstance(cand_acc, int):
                        acc_val = cand_acc
                    elif isinstance(cand_acc, str):
                        acc_val = LOCAL_ACCIDENTAL_MODIFIERS.get(cand_acc.lower())

                if cand_acc is not None and acc_val is not None:
                    # Update local measure memory
                    measure_memory[(letter, octave)] = acc_val
                    modifier = acc_val
                # Level 2: Previous accidental in measure on same pitch class and octave
                elif (letter, octave) in measure_memory:
                    modifier = measure_memory[(letter, octave)]
                # Level 3: Key signature alteration
                elif letter in sig_alts:
                    modifier = sig_alts[letter]
                # Level 4: Natural baseline
                else:
                    modifier = 0

                final_midi = natural_midi + modifier
                cand["clef_resolved_staff_pitch"] = get_spelled_note_name(natural_midi, modifier)
                cand["clef_resolved_midi_pitch"] = final_midi
            except Exception:
                continue
