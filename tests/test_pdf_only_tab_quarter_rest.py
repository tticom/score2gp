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
    """Replaced (DUR-02): rests come from the notation, never from TAB rest glyphs or padding. The
    TAB-only fixture has no notation staff, so it is refused; a notation bar of two quarter rests and
    a half rest is written as exactly those three rests."""
    import importlib.util
    import json

    import pytest

    from score2gp.build_ir import BuildIrInputRiskError
    from score2gp.notation_omr.note_duration import read_note_durations
    from score2gp.tabraw import TabRaw

    pdf_path = Path("fixtures/public/generated_simple/simple/TabOnlyQuarterNoteRests.pdf")
    payload = extract_tab(pdf_path, out_dir=tmp_path)
    tabraw_path = tmp_path / "tabraw.json"
    tabraw_path.write_text(json.dumps(payload, indent=2))
    with pytest.raises(BuildIrInputRiskError) as err:
        build_ir_from_tabraw_only(tabraw_path, note_durations=read_note_durations(pdf_path, time_signature=(4, 4)))
    assert err.value.category == "pdf_only_tab_no_notation_bars"

    spec = importlib.util.spec_from_file_location("pdf_tab_route_support", Path(__file__).with_name("test_pdf_tab_route_support.py"))
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    synthetic = tmp_path / "synthetic.json"
    TabRaw(candidates=[support.digit("q", 1, 20.0, 1, 3)]).to_json_file(synthetic)
    rests = [support.rest(20.0), support.rest(60.0), support.rest(100.0, "half")]
    score, _ = build_ir_from_tabraw_only(synthetic, note_durations=support.records([[rests, [support.note(20.0, "whole")]]]))
    events = score.bars[0].events
    assert [(e.is_rest, e.notes, e.timing.notated_duration.value, e.timing.onset_ticks) for e in events] == [
        (True, [], "quarter", 0), (True, [], "quarter", 960), (True, [], "half", 1920)]
