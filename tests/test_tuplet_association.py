import pytest
from score2gp.whole_note_recogniser import extract_and_apply_tuplet_associations

def test_tuplet_association_synthetic():
    # Setup staves
    staff_geometries = [
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [50.0, 100.0, 500.0, 140.0]  # height = 40, staff_space = 10
            # lane: 100.0 - 20 = 80.0 to 100.0
        },
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 2, # TAB staff below
            "bbox": [50.0, 200.0, 500.0, 240.0]
        }
    ]
    
    # Setup outcomes
    outcomes = [
        # Barline to define spans
        {"symbol_type": "barline", "page_index": 1, "system_index": 1, "staff_index": 1, "x0": 50.0},
        {"symbol_type": "barline", "page_index": 1, "system_index": 1, "staff_index": 1, "x0": 500.0},
        
        # 3 eighth notes forming a valid tuplet group in span 0
        {"candidate_id": "n1", "symbol_type": "eighth_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1, "bbox": [100.0, 100.0, 110.0, 110.0]},
        {"candidate_id": "n2", "symbol_type": "eighth_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1, "bbox": [150.0, 100.0, 160.0, 110.0]},
        {"candidate_id": "n3", "symbol_type": "eighth_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1, "bbox": [200.0, 100.0, 210.0, 110.0]},
    ]
    
    # Setup text blocks
    all_text_blocks = [
        # Genuine 3 above staff 1
        {"text": "3", "page_index": 1, "bbox": [150.0, 85.0, 160.0, 95.0], "marker_id": "m1"},
        
        # TAB digit 3 (in TAB staff, y=210)
        {"text": "3", "page_index": 1, "bbox": [150.0, 205.0, 160.0, 215.0], "marker_id": "m2"},
        
        # Measure label 3 (too high above staff, y=60)
        {"text": "3", "page_index": 1, "bbox": [50.0, 60.0, 60.0, 70.0], "marker_id": "m3"},
        
        # Metadata 3 (page number, bottom of page)
        {"text": "3", "page_index": 1, "bbox": [250.0, 800.0, 260.0, 810.0], "marker_id": "m4"},
        
        # Ambiguous 3 above staff 1, but no notes underneath
        {"text": "3", "page_index": 1, "bbox": [400.0, 85.0, 410.0, 95.0], "marker_id": "m5"}
    ]
    
    associations = extract_and_apply_tuplet_associations(outcomes, staff_geometries, all_text_blocks)
    
    # We should have 2 associations found (m1 and m5 fall into the lane of staff 1).
    # m1 should be associated, m5 ambiguous. m2, m3, m4 should be completely rejected.
    assert len(associations) == 2
    
    a1 = next((a for a in associations if a.marker_id == "m1"), None)
    assert a1 is not None
    assert a1.status == "associated"
    assert a1.candidate_ids == ["n1", "n2", "n3"]
    assert a1.ratio == "3:2"
    
    a5 = next((a for a in associations if a.marker_id == "m5"), None)
    assert a5 is not None
    assert a5.status == "ambiguous"
    assert len(a5.candidate_ids) == 0
    
    # Verify outcomes were updated with duration_ticks and tuplet ratio
    for n_id in ["n1", "n2", "n3"]:
        n = next(c for c in outcomes if c.get("candidate_id") == n_id)
        assert n["duration_ticks"] == 320  # 480 * 2 / 3
        assert n["tuplet_ratio"] == "3:2"
        assert n["tuplet_marker_id"] == "m1"
