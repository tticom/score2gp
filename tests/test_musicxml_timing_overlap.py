from __future__ import annotations

from pathlib import Path
import pytest

from score2gp.musicxml import parse_musicxml, analyze_musicxml_timing
from score2gp.build_ir import build_ir_from_files, BuildIrInputRiskError

FIXTURES = Path("tests/fixtures/musicxml")
TABRAW = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")


def test_overfull_measure_blocks_output_and_reports_overfull(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_overfull_measure.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml-overfull-bar" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "overfull.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_overfull_measure.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_underfull_measure_reports_warning_without_blocking_output(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_underfull_measure.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml-underfull-bar" and issue.severity == "warning" for issue in issues)

    out_ir = tmp_path / "underfull.ir.json"
    # Underfull measure alone does not contain fatal timing errors (only warnings), so it can succeed
    score = build_ir_from_files(FIXTURES / "timing_underfull_measure.musicxml", TABRAW, out_ir)
    assert score is not None
    assert out_ir.exists()


def test_same_voice_overlap_blocks_output_and_reports_voice_overlap(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_same_voice_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml-voice-overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "same_voice_overlap.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_same_voice_overlap.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_multivoice_overlap_refuses_clearly(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_multivoice_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_polyphony_not_supported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "multivoice_overlap.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_multivoice_overlap.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_legitimate_chord_stack_classified_distinctly(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_legit_chord_stack.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_chord_stack_detected" and issue.severity == "info" for issue in issues)
    assert not any(issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "legit_chord_stack.ir.json"
    score = build_ir_from_files(FIXTURES / "timing_legit_chord_stack.musicxml", TABRAW, out_ir)
    assert score is not None
    assert out_ir.exists()


def test_backup_forward_ambiguity_blocks_output(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_ambiguous_backup_forward.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_backup_forward_risk" and issue.severity == "warning" for issue in issues)
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "ambiguous_backup_forward.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_ambiguous_backup_forward.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_rest_overlap_blocks_output(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_rest_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_rest_overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "rest_overlap.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_rest_overlap.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_missing_zero_duration_blocks_output(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_missing_zero_duration.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_duration_zero" and issue.severity == "warning" for issue in issues)
    assert any(issue.code == "musicxml_duration_missing" and issue.severity == "warning" for issue in issues)

    out_ir = tmp_path / "missing_zero_duration.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_missing_zero_duration.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_divisions_change_mid_measure_blocks_output(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_divisions_changed_mid_measure.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_divisions_changed_mid_measure" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "divisions_changed_mid_measure.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_divisions_changed_mid_measure.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_unsupported_tuplet_timing_blocks_output(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_unsupported_tuplet.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_tuplet_unsupported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "unsupported_tuplet.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_unsupported_tuplet.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_musicxml_timing_diagnostics_html_written_on_failure(tmp_path) -> None:
    out_ir = tmp_path / "failed_score.ir.json"
    diagnostics_out_path = tmp_path / "diagnostics.json"

    with pytest.raises(BuildIrInputRiskError):
        build_ir_from_files(
            FIXTURES / "timing_overfull_measure.musicxml",
            TABRAW,
            out_path=out_ir,
            diagnostics_out_path=diagnostics_out_path,
        )

    assert diagnostics_out_path.exists()
    html_path = tmp_path / "musicxml-timing-diagnostics.html"
    assert html_path.exists()

    html_content = html_path.read_text(encoding="utf-8")
    assert "MusicXML Timing & Overlap Diagnostics" in html_content
    assert "musicxml-overfull-bar" in html_content
    assert "Timing Risk" in html_content

