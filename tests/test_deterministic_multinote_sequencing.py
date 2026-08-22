import pytest
from pathlib import Path
from src.score2gp.whole_note_recogniser import run_recognition_on_file
from src.score2gp.notation_bridge import build_ir_from_notation_outcomes

def test_multinote_sequencing_4_quarter_notes():
    pdf_path = Path("fixtures/public/generated_simple/simple/4QuarterNotes.pdf")
    res = run_recognition_on_file(
        pdf_path,
        include_x_aligned_clusters=True,
        include_left_margin_candidates=True,
        include_flag_beam_candidates=True,
        include_ledger_line_candidates=True,
    )
    assert res is not None
    outcomes = res.get("read_only_recognition_outcomes", [])
    valid_outcomes = [o for o in outcomes if o.get("association_status") == "success" and o.get("symbol_type") == "quarter_note_candidate"]
    assert len(valid_outcomes) == 4, f"Expected 4 raw valid quarter candidates, got {len(valid_outcomes)}"
    
    score = build_ir_from_notation_outcomes(outcomes)
    
    events = score.bars[0].events
    assert len(events) == 4
    for i, ev in enumerate(events):
        assert ev.timing.notated_duration.value == "quarter"
        assert ev.timing.duration_ticks == 960
        assert ev.timing.onset_ticks == i * 960

def test_multinote_sequencing_2_eighth_notes():
    pdf_path = Path("fixtures/public/generated_simple/simple/2EighthNotes.pdf")
    res = run_recognition_on_file(
        pdf_path,
        include_x_aligned_clusters=True,
        include_left_margin_candidates=True,
        include_flag_beam_candidates=True,
        include_ledger_line_candidates=True,
    )
    assert res is not None
    outcomes = res.get("read_only_recognition_outcomes", [])
    valid_outcomes = [o for o in outcomes if o.get("association_status") == "success" and o.get("symbol_type") == "eighth_note_candidate"]
    assert len(valid_outcomes) == 2, f"Expected 2 raw valid eighth candidates, got {len(valid_outcomes)}"
    
    score = build_ir_from_notation_outcomes(outcomes)
    
    events = score.bars[0].events
    assert len(events) == 2
    for i, ev in enumerate(events):
        assert ev.timing.notated_duration.value == "eighth"
        assert ev.timing.duration_ticks == 480
        assert ev.timing.onset_ticks == i * 480

def test_multinote_sequencing_4_sixteenth_notes():
    pdf_path = Path("fixtures/public/generated_simple/simple/4SixteenthNotes.pdf")
    res = run_recognition_on_file(
        pdf_path,
        include_x_aligned_clusters=True,
        include_left_margin_candidates=True,
        include_flag_beam_candidates=True,
        include_ledger_line_candidates=True,
    )
    assert res is not None
    outcomes = res.get("read_only_recognition_outcomes", [])
    valid_outcomes = [o for o in outcomes if o.get("association_status") == "success" and o.get("symbol_type") == "sixteenth_note_candidate"]
    assert len(valid_outcomes) == 4, f"Expected 4 raw valid sixteenth candidates, got {len(valid_outcomes)}"
    
    score = build_ir_from_notation_outcomes(outcomes)
    
    events = score.bars[0].events
    assert len(events) == 4
    for i, ev in enumerate(events):
        assert ev.timing.notated_duration.value == "16th"
        assert ev.timing.duration_ticks == 240
        assert ev.timing.onset_ticks == i * 240
