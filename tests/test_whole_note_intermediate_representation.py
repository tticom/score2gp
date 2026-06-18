import pytest
from pathlib import Path
from score2gp.whole_note_recogniser import run_recognition_on_file, map_whole_note_candidates_to_intermediate_notes

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdf"
WHOLE_NOTE_PDF = FIXTURES_DIR / "generated_standard_staff_whole_note.pdf"

def test_map_whole_note_fixture_to_intermediate_representation():
    assert WHOLE_NOTE_PDF.exists()
    
    result = run_recognition_on_file(WHOLE_NOTE_PDF)
    outcomes = result.get("read_only_recognition_outcomes", [])
    
    # Verify prior state is unchanged
    whole_note_cands = [o for o in outcomes if o.get("symbol_type") == "whole_note_candidate"]
    assert len(whole_note_cands) == 2
    for cand in whole_note_cands:
        assert cand.get("association_status") == "success"
        assert "assumed_treble_pitch" not in cand
        assert "clef_resolved_staff_pitch" not in cand
        
    # Map to intermediate notes
    intermediate_notes = map_whole_note_candidates_to_intermediate_notes(outcomes)
    
    assert len(intermediate_notes) == 2
    
    # Sort them by staff position index (2 and 4 expected from PR #296)
    intermediate_notes.sort(key=lambda n: n.get("staff_position_index", 0))
    
    note1 = intermediate_notes[0]
    assert note1.get("symbol_type") == "whole_note"
    assert note1.get("note_kind") == "whole_note"
    assert note1.get("duration_kind") == "whole"
    assert note1.get("source_candidate_id") == "whole_note_candidate_001"
    assert note1.get("page_index") == 1
    assert note1.get("system_index") == 1
    assert note1.get("staff_index") == 1
    assert note1.get("staff_position_index") == 2
    assert isinstance(note1.get("bbox"), list)
    assert len(note1.get("bbox")) == 4
    assert note1.get("mapping_status") == "success"
    assert "assumed_treble_pitch" not in note1
    assert "clef_resolved_staff_pitch" not in note1
    
    note2 = intermediate_notes[1]
    assert note2.get("source_candidate_id") == "whole_note_candidate_002"
    assert note2.get("staff_position_index") == 4
    assert note2.get("mapping_status") == "success"
    
def test_map_whole_note_failure_modes():
    # 1. Missing association_status
    outcomes = [{
        "symbol_type": "whole_note_candidate",
        "candidate_id": "cand_1",
        "bbox": [0.0, 0.0, 10.0, 10.0]
    }]
    notes = map_whole_note_candidates_to_intermediate_notes(outcomes)
    assert notes[0]["mapping_status"] == "failed"
    assert "invalid_association_status" in notes[0]["mapping_reason"]
    assert notes[0]["symbol_type"] == "whole_note_mapping_failure"
    assert "note_kind" not in notes[0]

    # 2. Failed association_status
    outcomes = [{
        "symbol_type": "whole_note_candidate",
        "candidate_id": "cand_1",
        "bbox": [0.0, 0.0, 10.0, 10.0],
        "association_status": "failed",
        "association_reason": "ambiguous"
    }]
    notes = map_whole_note_candidates_to_intermediate_notes(outcomes)
    assert notes[0]["mapping_status"] == "failed"
    assert notes[0]["symbol_type"] == "whole_note_mapping_failure"

    # 3. Missing staff_position_index
    outcomes = [{
        "symbol_type": "whole_note_candidate",
        "candidate_id": "cand_1",
        "bbox": [0.0, 0.0, 10.0, 10.0],
        "association_status": "success",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1
    }]
    notes = map_whole_note_candidates_to_intermediate_notes(outcomes)
    assert notes[0]["mapping_status"] == "failed"
    assert notes[0]["mapping_reason"] == "missing_or_invalid_staff_position_index"
    assert notes[0]["symbol_type"] == "whole_note_mapping_failure"

    # 4. Missing page/system/staff
    outcomes = [{
        "symbol_type": "whole_note_candidate",
        "candidate_id": "cand_1",
        "bbox": [0.0, 0.0, 10.0, 10.0],
        "association_status": "success",
        "staff_position_index": 2
    }]
    notes = map_whole_note_candidates_to_intermediate_notes(outcomes)
    assert notes[0]["mapping_status"] == "failed"
    assert notes[0]["mapping_reason"] == "missing_staff_indices"
    assert notes[0]["symbol_type"] == "whole_note_mapping_failure"

    # 5. Malformed bbox
    outcomes = [{
        "symbol_type": "whole_note_candidate",
        "candidate_id": "cand_1",
        "bbox": [0.0, 0.0], # too short
        "association_status": "success",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "staff_position_index": 2
    }]
    notes = map_whole_note_candidates_to_intermediate_notes(outcomes)
    assert notes[0]["mapping_status"] == "failed"
    assert notes[0]["mapping_reason"] == "missing_or_malformed_bbox"
    assert notes[0]["symbol_type"] == "whole_note_mapping_failure"
