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


def test_multi_clef_pitch_mapping_semantic_candidates():
    from score2gp.whole_note_recogniser import (
        map_quarter_note_candidates_to_read_only_outcomes,
        map_staff_position_to_read_only_outcomes,
        map_clef_resolved_staff_pitch,
        build_clef_resolved_pitch_coverage_report
    )

    # 1. Staff geometries
    staff_geometries = [
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [50.0, 200.0, 500.0, 240.0],
            "line_y_coords": [200.0, 210.0, 220.0, 230.0, 240.0]
        },
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 2,
            "bbox": [50.0, 300.0, 500.0, 340.0],
            "line_y_coords": [300.0, 310.0, 320.0, 330.0, 340.0]
        },
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 3,
            "bbox": [50.0, 400.0, 500.0, 440.0],
            "line_y_coords": [400.0, 410.0, 420.0, 430.0, 440.0]
        },
        # Staff 4: unknown clef
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 4,
            "bbox": [50.0, 500.0, 500.0, 540.0],
            "line_y_coords": [500.0, 510.0, 520.0, 530.0, 540.0]
        },
        # Staff 5: ambiguous clef
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 5,
            "bbox": [50.0, 600.0, 500.0, 640.0],
            "line_y_coords": [600.0, 610.0, 620.0, 630.0, 640.0]
        }
    ]

    # 2. Note candidate evidence
    note_diags = [
        # Staff 1: treble note (pos=4 -> Line 2)
        {
            "candidate_id": "note_treble",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [100.0, 220.0, 110.0, 220.0]
        },
        # Staff 2: bass note (pos=4 -> Line 2)
        {
            "candidate_id": "note_bass",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 2,
            "bbox": [100.0, 320.0, 110.0, 320.0]
        },
        # Staff 3: alto note (pos=4 -> Line 2)
        {
            "candidate_id": "note_alto",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 3,
            "bbox": [100.0, 420.0, 110.0, 420.0]
        },
        # Staff 4: unknown clef note
        {
            "candidate_id": "note_unknown",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 4,
            "bbox": [100.0, 520.0, 110.0, 520.0]
        },
        # Staff 5: ambiguous clef note
        {
            "candidate_id": "note_ambiguous",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 5,
            "bbox": [100.0, 620.0, 110.0, 620.0]
        }
    ]

    # 3. Semantic candidates representing resolved clefs
    semantic_candidates = [
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "logical_clef": {
                "status": "logical_clef_candidate",
                "clef_kind": "treble",
                "reason": "treble clef detected"
            }
        },
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 2,
            "logical_clef": {
                "status": "logical_clef_candidate",
                "clef_kind": "bass",
                "reason": "bass clef detected"
            }
        },
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 3,
            "logical_clef": {
                "status": "logical_clef_candidate",
                "clef_kind": "alto",
                "reason": "alto clef detected"
            }
        },
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 4,
            "logical_clef": {
                "status": "logical_clef_candidate",
                "clef_kind": "unknown",
                "reason": "unknown clef"
            }
        },
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 5,
            "logical_clef": {
                "status": "ambiguous_candidate",
                "clef_kind": None,
                "reason": "ambiguous clef"
            }
        }
    ]

    outcomes = map_quarter_note_candidates_to_read_only_outcomes(note_diags)
    map_staff_position_to_read_only_outcomes(outcomes, staff_geometries)

    map_clef_resolved_staff_pitch(outcomes, semantic_candidates=semantic_candidates)

    # Asserts
    treble_outcome = next(o for o in outcomes if o["candidate_id"] == "note_treble")
    bass_outcome = next(o for o in outcomes if o["candidate_id"] == "note_bass")
    alto_outcome = next(o for o in outcomes if o["candidate_id"] == "note_alto")
    unknown_outcome = next(o for o in outcomes if o["candidate_id"] == "note_unknown")
    ambiguous_outcome = next(o for o in outcomes if o["candidate_id"] == "note_ambiguous")

    # Treble: Middle Line 2 (index 4) -> B4, MIDI 71
    assert treble_outcome.get("clef_resolved_staff_pitch") == "B4"
    assert treble_outcome.get("clef_resolved_midi_pitch") == 71

    # Bass: Middle Line 2 (index 4) -> D3, MIDI 50
    assert bass_outcome.get("clef_resolved_staff_pitch") == "D3"
    assert bass_outcome.get("clef_resolved_midi_pitch") == 50

    # Alto: Middle Line 2 (index 4) -> C4, MIDI 60
    assert alto_outcome.get("clef_resolved_staff_pitch") == "C4"
    assert alto_outcome.get("clef_resolved_midi_pitch") == 60

    # Fail closed for unknown, missing, or ambiguous clef
    assert "clef_resolved_staff_pitch" not in unknown_outcome
    assert "clef_resolved_staff_pitch" not in ambiguous_outcome

    # Verify coverage report
    report = build_clef_resolved_pitch_coverage_report(outcomes, semantic_candidates=semantic_candidates)
    assert report["total_note_candidates_in_scope"] == 5
    assert report["note_candidates_on_staves_with_valid_clef"] == 3
    assert report["note_candidates_with_clef_resolved_staff_pitch"] == 3
    assert report["skipped_clef_missing"] == 1  # note_unknown counts as missing
    assert report["skipped_clef_ambiguous"] == 1  # note_ambiguous is ambiguous

