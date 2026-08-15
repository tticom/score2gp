
import pytest
from pathlib import Path

def _get_dynamic_private_pdf():
    pdfs = list(Path("fixtures/private").glob("*.pdf"))
    if not pdfs:
        pytest.skip("No private fixtures found")
    return pdfs[0]

def _get_dynamic_private_musicxml():
    xmls = list(Path("fixtures/private").glob("*.musicxml"))
    if not xmls:
        # Fallback to pdf just so Path doesn't fail, test will likely skip or fail gracefully
        return _get_dynamic_private_pdf()
    return xmls[0]

from pathlib import Path
from score2gp.pdf import extract_tab
from score2gp.build_ir import build_ir_from_tabraw_only

def test_pdf_only_tab_quarter_rest_detection(tmp_path):
    pdf_path = _get_dynamic_private_pdf()
    
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
    pdf_path = _get_dynamic_private_pdf()
    
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
    pdf_path = _get_dynamic_private_pdf()
    
    # 1. Extraction
    payload = extract_tab(pdf_path, out_dir=tmp_path)
    
    # 2. Build IR
    import json
    tabraw_path = tmp_path / "tabraw.json"
    tabraw_path.write_text(json.dumps(payload, indent=2))
    
    score, diagnostics = build_ir_from_tabraw_only(tabraw_path, editable_draft=False)
    
    # Verify events
    events = score.bars[0].events
    # The fixture has two quarter rests (plus 1 decomposed half rest filling the measure to 3840 ticks)
    assert len(events) == 3

    rest_events = [ev for ev in events if ev.is_rest]
    assert len(rest_events) == 3
    
    for rest_ev in rest_events:
        assert rest_ev.is_rest is True
        assert rest_ev.notes == [] # Ensure notes are cleanly stripped

    # The first two rests are the explicit candidate quarter rests
    for rest_ev in rest_events[:2]:
        assert rest_ev.timing.duration_ticks == 960 # Must have quarter rest duration
        assert rest_ev.timing.notated_duration.value == "quarter"

    # The third rest is the decomposed half rest filling the remainder measure capacity
    assert rest_events[2].timing.duration_ticks == 1920
    assert rest_events[2].timing.notated_duration.value == "half"
