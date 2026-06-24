import pytest
from pathlib import Path
from score2gp.pdf import extract_tab
from score2gp.build_ir import build_ir_from_tabraw_only

def test_pdf_only_tab_quarter_rest_detection(tmp_path):
    pdf_path = Path("fixtures/public/generated_simple/simple/TabOnlyQuarterNoteRests.pdf")
    
    # Run the PDF tab extraction
    payload = extract_tab(pdf_path, out_dir=tmp_path)
    raw_candidates = payload["candidates"]
    
    # Should detect the quarter_rest candidates
    rests = [c for c in raw_candidates if c.get("raw_text") == "quarter_rest"]
    assert len(rests) == 2, "Expected 2 quarter_rest candidates in TabOnlyQuarterNoteRests.pdf"
    
    for rest in rests:
        props = rest.get("raw", rest)
        assert props.get("symbol_type") == "quarter_rest_candidate"
        assert rest.get("local_bar_index", props.get("local_bar_index")) is not None

def test_pdf_only_tab_three_bars_rests_unsupported_shapes_ignored(tmp_path):
    pdf_path = Path("fixtures/public/generated_simple/simple/TabOnlyThreeBarsOfRests.pdf")
    
    # Run the PDF tab extraction
    payload = extract_tab(pdf_path, out_dir=tmp_path)
    raw_candidates = payload["candidates"]
    
    # Should detect ONLY the quarter_rest candidates, ignoring whole, half, eighth, sixteenth
    rests = [c for c in raw_candidates if c.get("raw_text") == "quarter_rest"]
    assert len(rests) == 4, "Expected exactly 4 quarter_rest candidates from the middle bar"
    
    # Ensure they are safely grouped
    for rest in rests:
        props = rest.get("raw", rest)
        assert rest.get("local_bar_index", props.get("local_bar_index")) == 1 # The middle bar (0-indexed) has the quarter rests

def test_pdf_only_tab_build_ir_creates_valid_rest_events(tmp_path):
    pdf_path = Path("fixtures/public/generated_simple/simple/TabOnlyQuarterNoteRests.pdf")
    
    # 1. Extraction
    payload = extract_tab(pdf_path, out_dir=tmp_path)
    
    # 2. Build IR
    import json
    tabraw_path = tmp_path / "tabraw.json"
    tabraw_path.write_text(json.dumps(payload, indent=2))
    
    score, diagnostics = build_ir_from_tabraw_only(tabraw_path, editable_draft=False)
    
    # Verify events
    events = score.bars[0].events
    # The fixture has two quarter rests
    assert len(events) == 2
    
    rest_events = [ev for ev in events if ev.is_rest]
    assert len(rest_events) == 2
    
    for rest_ev in rest_events:
        assert rest_ev.is_rest is True
        assert rest_ev.notes == [] # Ensure notes are cleanly stripped
        assert rest_ev.timing.duration_ticks == 960 # Must have quarter rest duration
        assert rest_ev.timing.notated_duration.value == "quarter"
