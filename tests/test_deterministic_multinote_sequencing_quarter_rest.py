import pytest
from pathlib import Path
from score2gp.whole_note_recogniser import run_recognition_on_file
from score2gp.notation_bridge import build_ir_from_notation_outcomes
from score2gp.ir import DEFAULT_TICKS_PER_QUARTER

def test_quarter_rest_then_notes_sequencing():
    pdf_path = Path("fixtures/public/generated_simple/simple/QuarterRestThenNotes.pdf")
    res = run_recognition_on_file(
        pdf_path,
        assume_treble_clef=True,
        include_ledger_line_candidates=True,
        include_flag_beam_candidates=True,
        include_left_margin_candidates=True,
        include_x_aligned_clusters=True
    )
    assert res is not None
    outcomes = res.get("read_only_recognition_outcomes", [])
    
    # We expect exactly one quarter rest candidate
    quarter_rests = [o for o in outcomes if o.get("symbol_type") == "quarter_rest_candidate"]
    assert len(quarter_rests) == 1, f"Expected 1 quarter rest candidate, got {len(quarter_rests)}"
    assert quarter_rests[0].get("association_status") == "success"
    
    score = build_ir_from_notation_outcomes(outcomes)
    
    events = score.bars[0].events
    assert len(events) == 3
    
    # event 0: quarter rest
    ev0 = events[0]
    assert ev0.is_rest is True
    assert ev0.notes == []
    assert ev0.timing.duration_ticks == 960
    assert ev0.timing.onset_ticks == 0
    assert ev0.timing.notated_duration.value == "quarter"
    
    # event 1: eighth note
    ev1 = events[1]
    assert ev1.is_rest is False
    assert len(ev1.notes) == 1
    assert ev1.timing.duration_ticks == 480
    assert ev1.timing.onset_ticks == 960
    assert ev1.timing.notated_duration.value == "eighth"
    
    # event 2: half note
    ev2 = events[2]
    assert ev2.is_rest is False
    assert len(ev2.notes) == 1
    assert ev2.timing.duration_ticks == 1920
    assert ev2.timing.onset_ticks == 1440
    assert ev2.timing.notated_duration.value == "half"
