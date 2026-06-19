import pytest
from score2gp.notation_bridge import build_ir_from_notation_outcomes, NotationBridgeInputError
from score2gp.ir import DEFAULT_TICKS_PER_QUARTER

def test_build_ir_from_whole_note_outcome_yields_valid_scoreir():
    outcomes = [
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "success",
            "duration": "whole",
            "clef_resolved_staff_pitch": "B4",
        }
    ]
    
    score = build_ir_from_notation_outcomes(outcomes)
    
    # Assert valid ScoreIR object and single elements
    assert score is not None
    assert len(score.tracks) == 1
    assert len(score.bars) == 1
    
    bar = score.bars[0]
    assert bar.time_signature.numerator == 4
    assert bar.time_signature.denominator == 4
    assert len(bar.events) == 1
    
    event = bar.events[0]
    assert event.timing.duration_ticks == 4 * DEFAULT_TICKS_PER_QUARTER
    assert event.timing.notated_duration is not None
    assert event.timing.notated_duration.value == "whole"
    
    assert len(event.notes) == 1
    note = event.notes[0]
    
    # Policy A validation for written B4
    assert note.pitch == 59
    assert note.string == 2
    assert note.fret == 0

def test_notation_bridge_skips_missing_pitch_from_tab_like_outcome():
    outcomes = [
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "success",
            "duration": "whole",
            "clef_resolved_staff_pitch": None,
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_notation_bridge_rejects_failed_association():
    outcomes = [
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "failed",
            "duration": "whole",
            "clef_resolved_staff_pitch": "B4",
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_notation_bridge_rejects_rests_and_unsupported_symbols():
    outcomes = [
        {
            "symbol_type": "whole_note_rest_candidate",
            "association_status": "success",
            "duration": "whole",
            "clef_resolved_staff_pitch": "B4",
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_notation_bridge_rejects_unsupported_duration():
    outcomes = [
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "success",
            "duration": "half",
            "clef_resolved_staff_pitch": "B4",
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_notation_bridge_rejects_multiple_valid_outcomes():
    outcomes = [
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "success",
            "duration": "whole",
            "clef_resolved_staff_pitch": "B4",
        },
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "success",
            "duration": "whole",
            "clef_resolved_staff_pitch": "G4",
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="multiple_valid_notation_outcomes_unsupported"):
        build_ir_from_notation_outcomes(outcomes)

def test_notation_bridge_preserves_scoreir_semantic_validation():
    outcomes = [
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "success",
            "duration": "whole",
            "clef_resolved_staff_pitch": "B4",
        }
    ]
    score = build_ir_from_notation_outcomes(outcomes)
    # The ScoreIR root model_validator semantic_contract_is_valid will run automatically if we use model_validate,
    # but score.semantic_errors() provides explicit proof.
    assert score.semantic_errors() == []

