def test_logical_clef_backed_staff_pitch_mapping_coverage_proof():
    from score2gp.whole_note_recogniser import (
        map_treble_clef_candidates_to_read_only_outcomes,
        map_quarter_note_candidates_to_read_only_outcomes,
        map_staff_position_to_read_only_outcomes,
        map_clef_resolved_staff_pitch,
        build_clef_resolved_pitch_coverage_report
    )

    # 1. Provide synthetic deterministic logical clef evidence
    clef_diags = [
        {
            "candidate_id": "treble_001",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [50.0, 185.0, 70.0, 245.0],
            "source": "logical_diagnostic_candidate_evidence" # The key condition
        }
    ]

    # 2. Provide synthetic quarter note candidate evidence on the same staff
    note_diags = [
        {
            "candidate_id": "quarter_note_001",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [100.0, 218.0, 110.0, 228.0] # Center is 223.0
        }
    ]

    # 3. Provide staff geometry
    staff_geometries = [
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [50.0, 200.0, 500.0, 240.0],
            # Staff space is 10. lines at 200, 210, 220, 230, 240
            "line_y_coords": [200.0, 210.0, 220.0, 230.0, 240.0]
        }
    ]

    # Map to read-only outcomes
    outcomes = []
    outcomes.extend(map_treble_clef_candidates_to_read_only_outcomes(clef_diags))
    outcomes.extend(map_quarter_note_candidates_to_read_only_outcomes(note_diags))

    # Map staff position (y=223.0, line[0]=200, space/2 = 5) -> pos = (223-200)/5 = 4.6 -> 5
    map_staff_position_to_read_only_outcomes(outcomes, staff_geometries)

    # Note candidate should have staff_position_index = 5 (A4)
    note_outcome = next(o for o in outcomes if o["symbol_type"] == "quarter_note_candidate")
    assert note_outcome["staff_position_index"] == 5

    # Run pitch mapping
    map_clef_resolved_staff_pitch(outcomes)

    # Prove the note was mapped and not skipped
    assert "clef_resolved_staff_pitch" in note_outcome
    assert note_outcome["clef_resolved_staff_pitch"] == "A4"

    # Prove coverage report counts it correctly
    report = build_clef_resolved_pitch_coverage_report(outcomes)

    assert report["total_note_candidates_in_scope"] == 1
    assert report["note_candidates_with_staff_position_index"] == 1
    assert report["note_candidates_on_staves_with_valid_clef"] == 1
    assert report["note_candidates_with_clef_resolved_staff_pitch"] == 1
    assert report["skipped_clef_missing"] == 0

