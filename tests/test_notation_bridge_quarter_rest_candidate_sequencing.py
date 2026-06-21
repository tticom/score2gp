import pytest
from score2gp.notation_bridge import build_ir_from_notation_outcomes, NotationBridgeInputError
from score2gp.ir import DEFAULT_TICKS_PER_QUARTER

def test_quarter_rest_candidate_sequencing():
    outcomes = [
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "B4",
            "bbox": [10.0, 50.0, 20.0, 80.0],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "candidate_id": "c1"
        },
        {
            "symbol_type": "quarter_rest_candidate",
            "association_status": "success",
            "duration": "quarter",
            "bbox": [30.0, 50.0, 40.0, 80.0],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "candidate_id": "c2"
        },
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "G4",
            "bbox": [50.0, 50.0, 60.0, 80.0],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "candidate_id": "c3"
        }
    ]

    score = build_ir_from_notation_outcomes(outcomes)
    events = score.bars[0].events

    assert len(events) == 3
    
    # First event: quarter note
    assert events[0].is_rest is False
    assert len(events[0].notes) == 1
    assert events[0].timing.duration_ticks == DEFAULT_TICKS_PER_QUARTER
    assert events[0].timing.onset_ticks == 0

    # Second event: quarter rest
    assert events[1].is_rest is True
    assert events[1].notes == []
    assert events[1].timing.duration_ticks == DEFAULT_TICKS_PER_QUARTER
    assert events[1].timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER

    # Third event: quarter note, shifted by rest
    assert events[2].is_rest is False
    assert len(events[2].notes) == 1
    assert events[2].timing.duration_ticks == DEFAULT_TICKS_PER_QUARTER
    assert events[2].timing.onset_ticks == 2 * DEFAULT_TICKS_PER_QUARTER

def test_quarter_rest_candidate_missing_association_status_rejected():
    outcomes = [
        {
            "symbol_type": "quarter_rest_candidate",
            "duration": "quarter",
            "bbox": [30.0, 50.0, 40.0, 80.0],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "candidate_id": "c1"
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_playable_notation_outcomes_found|no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_malformed_rest_candidate_duration_rejected():
    outcomes = [
        {
            "symbol_type": "quarter_rest_candidate",
            "association_status": "success",
            "duration": "half", # wrong duration
            "bbox": [30.0, 50.0, 40.0, 80.0],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "candidate_id": "c1"
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_playable_notation_outcomes_found|no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_malformed_rest_candidate_bbox_missing_rejected():
    outcomes = [
        {
            "symbol_type": "quarter_rest_candidate",
            "association_status": "success",
            "duration": "quarter",
            # missing bbox
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "candidate_id": "c1"
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_playable_notation_outcomes_found|no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_malformed_rest_candidate_bbox_short_rejected():
    outcomes = [
        {
            "symbol_type": "quarter_rest_candidate",
            "association_status": "success",
            "duration": "quarter",
            "bbox": [30.0, 50.0], # too short
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "candidate_id": "c1"
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_playable_notation_outcomes_found|no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_malformed_rest_candidate_bbox_non_numeric_rejected():
    outcomes = [
        {
            "symbol_type": "quarter_rest_candidate",
            "association_status": "success",
            "duration": "quarter",
            "bbox": [30.0, 50.0, 40.0, "eighty"], # non-numeric
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "candidate_id": "c1"
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_playable_notation_outcomes_found|no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_quarter_rest_candidate_bridge_fallback_system_staff_index():
    outcomes = [
        {
            "symbol_type": "quarter_rest_candidate",
            "association_status": "success",
            "duration": "quarter",
            "bbox": [30.0, 50.0, 40.0, 80.0],
            "page_index": 1,
            "system_index": 1,
            "system_staff_index": 2,
            "candidate_id": "c1"
        },
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "G4",
            "bbox": [50.0, 50.0, 60.0, 80.0],
            "page_index": 1,
            "system_index": 1,
            "system_staff_index": 2,
            "candidate_id": "c2"
        }
    ]
    
    score = build_ir_from_notation_outcomes(outcomes)
    events = score.bars[0].events
    
    assert len(events) == 2
    
    # First event: quarter rest (has system_staff_index but no staff_index)
    assert events[0].is_rest is True
    assert events[0].notes == []
    assert events[0].timing.duration_ticks == DEFAULT_TICKS_PER_QUARTER
    assert events[0].timing.onset_ticks == 0
    
    # Second event: quarter note, shifted by rest
    assert events[1].is_rest is False
    assert len(events[1].notes) == 1
    assert events[1].timing.duration_ticks == DEFAULT_TICKS_PER_QUARTER
    assert events[1].timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER
