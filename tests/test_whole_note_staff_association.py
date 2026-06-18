import pytest
from pathlib import Path
from score2gp.whole_note_recogniser import run_recognition_on_file, _associate_staves

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdf"
WHOLE_NOTE_PDF = FIXTURES_DIR / "generated_standard_staff_whole_note.pdf"

def test_whole_note_staff_association_on_fixture():
    assert WHOLE_NOTE_PDF.exists()
    
    result = run_recognition_on_file(WHOLE_NOTE_PDF)
    assert result is not None
    
    outcomes = result.get("read_only_recognition_outcomes", [])
    whole_notes = [o for o in outcomes if o.get("symbol_type") == "whole_note_candidate"]
    
    assert len(whole_notes) == 2, f"Expected 2 whole notes, got {len(whole_notes)}"
    
    # Assert exact expected indexes matching the PR evidence table
    cand1 = next(wn for wn in whole_notes if wn["candidate_id"] == "whole_note_candidate_001")
    assert cand1.get("staff_position_index") == 2

    cand2 = next(wn for wn in whole_notes if wn["candidate_id"] == "whole_note_candidate_002")
    assert cand2.get("staff_position_index") == 4
    
    for wn in whole_notes:
        assert wn.get("association_status") == "success"
        assert wn.get("system_index") == 1
        assert wn.get("staff_index") == 1
        
        # Ensure no pitch was named
        assert "assumed_treble_pitch" not in wn
        assert "clef_resolved_staff_pitch" not in wn

def test_whole_note_staff_association_failure_mode():
    # Construct a mock candidate and mock staves to prove missing/malformed failure modes
    
    # 1. Missing staff geometry entirely
    candidates = [{"bbox": [100.0, 100.0, 110.0, 110.0]}]
    staves = []
    _associate_staves(candidates, staves)
    assert candidates[0].get("association_status") == "failed"
    assert candidates[0].get("association_reason") == "missing_staff_geometry"
    
    # 2. Outside staff bounds
    candidates = [{"bbox": [100.0, 800.0, 110.0, 810.0]}]  # Way below staff
    staves = [{"staff": {"system_index": 1, "staff_index": 1, "x0": 50.0, "y0": 100.0, "x1": 500.0, "y1": 150.0}}]
    _associate_staves(candidates, staves)
    assert candidates[0].get("association_status") == "failed"
    assert candidates[0].get("association_reason") == "outside_staff_bounds"

    # 3. Ambiguous staff match (candidate falls inside two overlapping staves)
    candidates = [{"bbox": [100.0, 120.0, 110.0, 130.0]}]
    staves = [
        {"staff": {"system_index": 1, "staff_index": 1, "x0": 50.0, "y0": 100.0, "x1": 500.0, "y1": 150.0}},
        {"staff": {"system_index": 2, "staff_index": 1, "x0": 50.0, "y0": 110.0, "x1": 500.0, "y1": 160.0}},
    ]
    _associate_staves(candidates, staves)
    assert candidates[0].get("association_status") == "failed"
    assert candidates[0].get("association_reason") == "ambiguous_staff_match"
    
    # 4. Malformed bbox
    candidates = [{"bbox": [100.0, 120.0]}] # too short
    staves = [{"staff": {"system_index": 1, "staff_index": 1, "x0": 50.0, "y0": 100.0, "x1": 500.0, "y1": 150.0}}]
    _associate_staves(candidates, staves)
    assert candidates[0].get("association_status") == "failed"
    assert candidates[0].get("association_reason") == "malformed_candidate_bbox"

def test_regression_half_and_quarter_notes_staff_association():
    # Verify _associate_staves doesn't break for half/quarter candidates
    staves = [{"staff": {"system_index": 1, "staff_index": 1, "x0": 50.0, "y0": 100.0, "x1": 500.0, "y1": 150.0}}]
    
    # Valid quarter note inside staff bounds
    quarter_cands = [{"bbox": [200.0, 110.0, 210.0, 120.0]}]
    _associate_staves(quarter_cands, staves)
    assert quarter_cands[0].get("association_status") == "success"
    assert quarter_cands[0].get("system_index") == 1
    assert quarter_cands[0].get("staff_index") == 1
    
    # Valid half note inside staff bounds
    half_cands = [{"bbox": [300.0, 130.0, 310.0, 140.0]}]
    _associate_staves(half_cands, staves)
    assert half_cands[0].get("association_status") == "success"
    assert half_cands[0].get("system_index") == 1
    assert half_cands[0].get("staff_index") == 1
