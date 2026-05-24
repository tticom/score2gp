from __future__ import annotations

from pathlib import Path
import pytest

from score2gp.musicxml import parse_musicxml, analyze_musicxml_timing
from score2gp.build_ir import build_ir_from_files, BuildIrInputRiskError

FIXTURES = Path("tests/fixtures/musicxml")
TABRAW = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")


def test_vc_valid_two_voice(tmp_path) -> None:
    # 1. Valid two-voice MusicXML using backup to start voice 2 after voice 1
    imported = parse_musicxml(FIXTURES / "timing_vc_valid_two_voice.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    # Timing is valid, but it has cross-voice overlap which is unsupported polyphony
    assert any(issue.code == "musicxml_valid_multivoice_unsupported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "valid_two_voice.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_valid_two_voice.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_scoreir_polyphony_gate_refused"


def test_vc_valid_chord_stack(tmp_path) -> None:
    # 2. Valid chord stack using <chord/>
    imported = parse_musicxml(FIXTURES / "timing_vc_valid_chord_stack.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    # Legit chord stack classified as valid timeline, not same-voice overlap (no error)
    assert any(issue.code == "musicxml_chord_stack_detected" and issue.severity == "info" for issue in issues)
    assert not any(issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "valid_chord_stack.ir.json"
    score = build_ir_from_files(FIXTURES / "timing_vc_valid_chord_stack.musicxml", TABRAW, out_ir)
    assert score is not None
    assert out_ir.exists()


def test_vc_invalid_same_voice(tmp_path) -> None:
    # 3. Invalid same-voice overlap caused by backup without voice separation
    imported = parse_musicxml(FIXTURES / "timing_vc_invalid_same_voice.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml-voice-overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "invalid_same_voice.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_invalid_same_voice.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_vc_backup_before_start(tmp_path) -> None:
    # 4. Invalid backup before measure start
    imported = parse_musicxml(FIXTURES / "timing_vc_backup_before_start.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_backup_rewinds_before_measure_start" and issue.severity == "warning" for issue in issues)


def test_vc_forward_past_end(tmp_path) -> None:
    # 5. Invalid forward past measure end
    imported = parse_musicxml(FIXTURES / "timing_vc_forward_past_end.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_forward_exceeds_measure_end" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "forward_past_end.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_forward_past_end.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_vc_valid_two_voice_uneven(tmp_path) -> None:
    # 6. Valid voice 1 and voice 2 with different internal durations but both inside measure
    imported = parse_musicxml(FIXTURES / "timing_vc_valid_two_voice_uneven.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_valid_multivoice_unsupported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "valid_two_voice_uneven.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_valid_two_voice_uneven.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_scoreir_polyphony_gate_refused"


def test_vc_rest_overlap(tmp_path) -> None:
    # 7. Rest overlap in same voice
    imported = parse_musicxml(FIXTURES / "timing_vc_rest_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_rest_overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "rest_overlap.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_rest_overlap.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_vc_ambiguous_bf(tmp_path) -> None:
    # 8. Ambiguous backup/forward pattern where event ownership cannot be safely assigned
    imported = parse_musicxml(FIXTURES / "timing_vc_ambiguous_bf.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "ambiguous_bf.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_ambiguous_bf.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_vc_audiveris_unsupported(tmp_path) -> None:
    # 9. Audiveris-like synthetic two-voice backup/forward pattern that is valid MusicXML timing but unsupported by ScoreIR
    imported = parse_musicxml(FIXTURES / "timing_vc_audiveris_unsupported.musicxml")
    issues = analyze_musicxml_timing(imported)
    
    # Valid multivoice timing but unsupported polyphony
    assert any(issue.code == "musicxml_valid_multivoice_unsupported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "audiveris_unsupported.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_audiveris_unsupported.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_scoreir_polyphony_gate_refused"
