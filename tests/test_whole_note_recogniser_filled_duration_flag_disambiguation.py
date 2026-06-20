from score2gp.whole_note_recogniser import compose_filled_duration_candidates

def test_compose_filled_duration_excludes_flags_contained_in_notehead():
    # Simulate a quarter note and a flag curve that happens to be a notehead curve
    # meaning it is entirely contained within the notehead bounds
    outcomes = [
        {
            "candidate_id": "q_1",
            "symbol_type": "quarter_note_candidate",
            "bbox": [10, 50, 20, 60],
            "stem_bbox": [19, 20, 20, 55],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        },
        {
            "candidate_id": "f_1",
            "symbol_type": "flag_candidate",
            # This flag curve is entirely inside the notehead (10-20, 50-60)
            "bbox": [12, 52, 18, 58],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        }
    ]
    
    composed = compose_filled_duration_candidates(outcomes)
    assert len(composed) == 0
    assert outcomes[0].get("association_status", "") != "suppressed"

def test_compose_filled_duration_excludes_flags_far_from_stem_horizontally():
    outcomes = [
        {
            "candidate_id": "q_1",
            "symbol_type": "quarter_note_candidate",
            "bbox": [10, 50, 20, 60],
            "stem_bbox": [19, 20, 20, 55],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        },
        {
            "candidate_id": "f_1",
            "symbol_type": "flag_candidate",
            # This flag is vertically overlapping the stem, but horizontally it starts
            # at 24 (which is stem_x 19 + 5.0, so it fails f_bbox[0] <= stem_x + 4.0)
            # This simulates an adjacent note's notehead curves.
            "bbox": [25, 20, 35, 30],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        }
    ]
    
    composed = compose_filled_duration_candidates(outcomes)
    assert len(composed) == 0

def test_compose_filled_duration_includes_valid_flags():
    # Simulate a valid flag attached to the stem tip
    outcomes = [
        {
            "candidate_id": "q_1",
            "symbol_type": "quarter_note_candidate",
            "bbox": [10, 50, 20, 60],
            "stem_bbox": [19, 20, 20, 55],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        },
        {
            "candidate_id": "f_1",
            "symbol_type": "flag_candidate",
            # This flag curve starts at the stem (19) and extends right (to 25)
            "bbox": [19, 20, 25, 30],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        }
    ]
    
    composed = compose_filled_duration_candidates(outcomes)
    assert len(composed) == 1
    assert composed[0]["duration"] == "eighth"
    assert outcomes[0].get("association_status") == "suppressed"
