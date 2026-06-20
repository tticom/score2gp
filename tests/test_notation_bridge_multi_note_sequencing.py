import pytest
from score2gp.notation_bridge import build_ir_from_notation_outcomes, NotationBridgeInputError
from score2gp.ir import DEFAULT_TICKS_PER_QUARTER

def test_build_ir_multi_note_sequencing():
    outcomes = [
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "B4",
            "bbox": [10, 0, 20, 10],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        },
        {
            "symbol_type": "quarter_note_candidate",
            "association_status": "success",
            "duration": "quarter",
            "clef_resolved_staff_pitch": "C5",
            "bbox": [30, 0, 40, 10],
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
        }
    ]
    
    score = build_ir_from_notation_outcomes(outcomes)
    bar = score.bars[0]
    
    assert len(bar.events) == 2
    
    evt1 = bar.events[0]
    assert evt1.timing.onset_ticks == 0
    assert evt1.timing.duration_ticks == DEFAULT_TICKS_PER_QUARTER
    
    evt2 = bar.events[1]
    assert evt2.timing.onset_ticks == DEFAULT_TICKS_PER_QUARTER
    assert evt2.timing.duration_ticks == DEFAULT_TICKS_PER_QUARTER
