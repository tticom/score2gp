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
            "duration": "double_whole",
            "clef_resolved_staff_pitch": "B4",
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="no_valid_notation_outcomes_found"):
        build_ir_from_notation_outcomes(outcomes)

def test_notation_bridge_rejects_cumulative_duration_exceeding_bar():
    outcomes = [
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "success",
            "duration": "whole",
            "clef_resolved_staff_pitch": "B4",
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "success",
            "duration": "whole",
            "clef_resolved_staff_pitch": "G4",
            "bbox": [20.0, 0, 20.0, 0],
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="cumulative_duration_exceeds_one_4_4_bar"):
        build_ir_from_notation_outcomes(outcomes)

def test_notation_bridge_rejects_mixed_duration_exceeding_bar():
    outcomes = [
        {
            "symbol_type": "whole_note_candidate",
            "association_status": "success",
            "duration": "whole",
            "clef_resolved_staff_pitch": "B4",
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "half_note_candidate",
            "association_status": "success",
            "duration": "half",
            "clef_resolved_staff_pitch": "G4",
            "bbox": [20.0, 0, 20.0, 0],
        }
    ]
    with pytest.raises(NotationBridgeInputError, match="cumulative_duration_exceeds_one_4_4_bar"):
        build_ir_from_notation_outcomes(outcomes)

def test_build_ir_from_half_note_outcome_yields_valid_scoreir():
    outcomes = [
        {
            "symbol_type": "half_note_candidate",
            "association_status": "success",
            "duration": "half",
            "clef_resolved_staff_pitch": "B4",
        }
    ]
    
    score = build_ir_from_notation_outcomes(outcomes)
    
    assert score is not None
    assert len(score.tracks) == 1
    assert len(score.bars) == 1
    
    bar = score.bars[0]
    assert len(bar.events) == 1
    
    event = bar.events[0]
    assert event.timing.duration_ticks == 2 * DEFAULT_TICKS_PER_QUARTER
    assert event.timing.notated_duration is not None
    assert event.timing.notated_duration.value == "half"
    
    assert len(event.notes) == 1
    note = event.notes[0]
    
    assert note.pitch == 59
    assert note.string == 2
    assert note.fret == 0
    assert score.semantic_errors() == []

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

def test_chord_grouping_same_context_and_duration_mapping():
    outcomes_eighth = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.5, 0, 10.5, 0],
        }
    ]
    score_eighth = build_ir_from_notation_outcomes(outcomes_eighth)
    assert score_eighth is not None
    bar = score_eighth.bars[0]
    assert len(bar.events) == 1
    event = bar.events[0]
    assert len(event.notes) == 2
    assert event.timing.onset_ticks == 0
    assert event.timing.duration_ticks == DEFAULT_TICKS_PER_QUARTER // 2
    assert event.timing.notated_duration.value == "eighth"

    outcomes_sixteenth = [
        {
            "symbol_type": "sixteenth_note_candidate",
            "association_status": "success",
            "duration": "sixteenth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "sixteenth_note_candidate",
            "association_status": "success",
            "duration": "sixteenth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [11.0, 0, 11.0, 0],
        }
    ]
    score_sixteenth = build_ir_from_notation_outcomes(outcomes_sixteenth)
    assert len(score_sixteenth.bars[0].events) == 1
    event = score_sixteenth.bars[0].events[0]
    assert len(event.notes) == 2
    assert event.timing.onset_ticks == 0
    assert event.timing.duration_ticks == DEFAULT_TICKS_PER_QUARTER // 4
    assert event.timing.notated_duration.value == "16th"

def test_chord_grouping_negative_contexts():
    outcomes_diff_page = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 1,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        }
    ]
    score_diff_page = build_ir_from_notation_outcomes(outcomes_diff_page)
    assert len(score_diff_page.bars[0].events) == 2
    events = score_diff_page.bars[0].events
    assert events[0].timing.onset_ticks == 0
    assert events[1].timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER // 2

    outcomes_diff_sys = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 1,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        }
    ]
    score_diff_sys = build_ir_from_notation_outcomes(outcomes_diff_sys)
    assert len(score_diff_sys.bars[0].events) == 2

    outcomes_diff_staff = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 1,
            "bbox": [10.0, 0, 10.0, 0],
        }
    ]
    score_diff_staff = build_ir_from_notation_outcomes(outcomes_diff_staff)
    assert len(score_diff_staff.bars[0].events) == 2

    outcomes_diff_x = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [11.1, 0, 11.1, 0],
        }
    ]
    score_diff_x = build_ir_from_notation_outcomes(outcomes_diff_x)
    assert len(score_diff_x.bars[0].events) == 2

    outcomes_seq = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [50.0, 0, 50.0, 0],
        }
    ]
    score_seq = build_ir_from_notation_outcomes(outcomes_seq)
    assert len(score_seq.bars[0].events) == 2


