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

def test_chord_grouping_coordinate_and_context_fallback():
    # Candidates lacking bbox coordinates are not grouped
    outcomes_no_bbox = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
        }
    ]
    score_no_bbox = build_ir_from_notation_outcomes(outcomes_no_bbox)
    assert len(score_no_bbox.bars[0].events) == 2

    # Candidates lacking page_index are not grouped
    outcomes_no_page = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        }
    ]
    score_no_page = build_ir_from_notation_outcomes(outcomes_no_page)
    assert len(score_no_page.bars[0].events) == 2

    # Candidates lacking system_index are not grouped
    outcomes_no_sys = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        }
    ]
    score_no_sys = build_ir_from_notation_outcomes(outcomes_no_sys)
    assert len(score_no_sys.bars[0].events) == 2

    # Candidates lacking staff_index (and system_staff_index) are not grouped
    outcomes_no_staff = [
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "eighth_note_candidate",
            "association_status": "success",
            "duration": "eighth",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        }
    ]
    score_no_staff = build_ir_from_notation_outcomes(outcomes_no_staff)
    assert len(score_no_staff.bars[0].events) == 2


def test_multi_staff_parallel_timing():
    # Two explicit staff/track identities maintain independent timing accumulation.
    # Events from staff A (0) do not advance staff B (1) timing, and vice versa.
    # Parallel starts across staff/track identities remain aligned.
    outcomes = [
        # Staff 0: Quarter note at onset 0, then quarter note at onset 240
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [20.0, 0, 20.0, 0],
        },
        # Staff 1: Quarter note at onset 0, then quarter note at onset 240
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "D4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 1,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "E4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 1,
            "bbox": [20.0, 0, 20.0, 0],
        },
    ]
    score = build_ir_from_notation_outcomes(outcomes)

    assert score is not None
    assert len(score.tracks) == 2
    assert score.tracks[0].id == "trk_0"
    assert score.tracks[0].name == "Guitar"
    assert score.tracks[1].id == "trk_1"
    assert score.tracks[1].name == "Guitar 2"

    bar = score.bars[0]
    # We should have 4 events in total (2 for track 0, 2 for track 1)
    assert len(bar.events) == 4

    # Sort events by track and onset to check them cleanly
    events_trk0 = sorted([e for e in bar.events if e.track_id == "trk_0"], key=lambda e: e.timing.onset_ticks)
    events_trk1 = sorted([e for e in bar.events if e.track_id == "trk_1"], key=lambda e: e.timing.onset_ticks)

    assert len(events_trk0) == 2
    assert len(events_trk1) == 2

    # Assert track 0 independent timing
    assert events_trk0[0].timing.onset_ticks == 0
    assert events_trk0[1].timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER

    # Assert track 1 independent timing starting from 0 and parallel with track 0
    assert events_trk1[0].timing.onset_ticks == 0
    assert events_trk1[1].timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER


def test_coordinate_less_candidates_retain_conservative_sequential_behavior():
    # Coordinate-less/context-less candidates must not gain unsafe parallel behaviour.
    # They should accumulate sequentially on the default track (trk_0).
    outcomes = [
        # Lacks bbox/page/system/staff
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "B4",
        },
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "G4",
        }
    ]
    score = build_ir_from_notation_outcomes(outcomes)
    assert len(score.tracks) == 1
    assert score.tracks[0].id == "trk_0"

    bar = score.bars[0]
    assert len(bar.events) == 2
    assert bar.events[0].track_id == "trk_0"
    assert bar.events[0].timing.onset_ticks == 0
    assert bar.events[1].track_id == "trk_0"
    assert bar.events[1].timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER


def test_positionless_staff_index_candidates_remain_sequential_on_default_track():
    # Positionless candidates carrying a staff index should not split into parallel tracks
    outcomes = [
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "B4",
            "staff_index": 0,
        },
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "G4",
            "staff_index": 1,
        },
    ]
    score = build_ir_from_notation_outcomes(outcomes)
    assert len(score.tracks) == 1
    assert score.tracks[0].id == "trk_0"

    bar = score.bars[0]
    assert len(bar.events) == 2
    assert bar.events[0].track_id == "trk_0"
    assert bar.events[0].timing.onset_ticks == 0
    assert bar.events[1].track_id == "trk_0"
    assert bar.events[1].timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER


def test_sparse_multi_staff_positioned_columns_align_onsets():
    # Sparse multi-staff: staff 0 has events at x=10 and x=20, staff 1's first event is at x=20.
    # Staff 1's event at x=20 must align with staff 0's event at x=20.
    outcomes = [
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "B4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [10.0, 0, 10.0, 0],
        },
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "G4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 0,
            "bbox": [20.0, 0, 20.0, 0],
        },
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "D4",
            "page_index": 0,
            "system_index": 0,
            "staff_index": 1,
            "bbox": [20.0, 0, 20.0, 0],
        },
    ]
    score = build_ir_from_notation_outcomes(outcomes)
    assert len(score.tracks) == 2
    assert score.tracks[0].id == "trk_0"
    assert score.tracks[1].id == "trk_1"

    bar = score.bars[0]
    assert len(bar.events) == 3

    events_trk0 = sorted([e for e in bar.events if e.track_id == "trk_0"], key=lambda e: e.timing.onset_ticks)
    events_trk1 = sorted([e for e in bar.events if e.track_id == "trk_1"], key=lambda e: e.timing.onset_ticks)

    assert len(events_trk0) == 2
    assert len(events_trk1) == 1

    assert events_trk0[0].timing.onset_ticks == 0
    assert events_trk0[1].timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER
    assert events_trk1[0].timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER


