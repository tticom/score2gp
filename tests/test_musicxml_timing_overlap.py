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


def test_valid_12_8_compound_preflight() -> None:
    imported = parse_musicxml(FIXTURES / "timing_12_8_valid.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "valid_compound_meter" and issue.severity == "info" for issue in issues)
    assert not any(issue.severity == "error" for issue in issues)


def test_12_8_underfull_preflight() -> None:
    imported = parse_musicxml(FIXTURES / "timing_12_8_underfull.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_compound_meter_underfull" and issue.severity == "warning" for issue in issues)


def test_12_8_overfull_preflight() -> None:
    imported = parse_musicxml(FIXTURES / "timing_12_8_overfull.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_compound_meter_overfull" and issue.severity == "error" for issue in issues)


def test_backup_rewind_before_measure_start_detected() -> None:
    imported = parse_musicxml(FIXTURES / "timing_backup_rewinds_before_start.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_backup_rewinds_before_measure_start" and issue.severity == "warning" for issue in issues)


def test_forward_beyond_measure_end_detected() -> None:
    imported = parse_musicxml(FIXTURES / "timing_forward_exceeds_end.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_forward_exceeds_measure_end" and issue.severity == "error" for issue in issues)


def test_backup_forward_ambiguity_blocks_alignment(tmp_path) -> None:
    out_ir = tmp_path / "ambig.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_12_8_ambiguous_backup_forward.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_multivoice_unsupported_refuses_clearly(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_multivoice_unsupported.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_multivoice_timing_not_supported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "multivoice.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_multivoice_unsupported.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_scoreir_polyphony_gate_refused"


def test_same_voice_cursor_overlap_refuses_clearly(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_same_voice_cursor_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_voice_cursor_overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "same_voice.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_same_voice_cursor_overlap.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_chord_stack_classified_distinctly_from_unsafe_overlap(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_chord_stack_classified.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_chord_stack_detected" and issue.severity == "info" for issue in issues)
    assert any(issue.code == "musicxml_chord_stack_supported_or_blocked" and issue.severity == "info" for issue in issues)
    assert not any(issue.severity == "error" for issue in issues)


def test_audiveris_like_synthetic_timing_pattern() -> None:
    imported = parse_musicxml(FIXTURES / "timing_audiveris_like_pattern.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_unbalanced_backup_forward" and issue.severity == "error" for issue in issues)
    assert any(issue.code == "musicxml_alignment_not_attempted_due_to_timing_risk" and issue.severity == "error" for issue in issues)


def test_v03_repeated_backup_forward(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_repeated_backup_forward.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_repeated_backup_forward_risk" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "repeated.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_v03_repeated_backup_forward.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_v03_voice_cursor_reset(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_voice_cursor_reset.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_same_voice_tick_overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "reset.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_v03_voice_cursor_reset.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_v03_multivoice_staggered(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_multivoice_staggered.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_cross_voice_timing_unsupported" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "staggered.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_v03_multivoice_staggered.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_v03_backup_measure_start_forward(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_backup_measure_start_forward.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_same_voice_tick_overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "measure_start.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_v03_backup_measure_start_forward.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_v03_rest_note_cursor_overlap(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_rest_note_cursor_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_rest_overlap" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "rest_cursor.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_v03_rest_note_cursor_overlap.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_v03_chord_marker_backup_forward(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_chord_marker_backup_forward.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_chord_stack_not_timing_overlap" and issue.severity == "info" for issue in issues)
    assert not any(issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "chord_backup.ir.json"
    score = build_ir_from_files(FIXTURES / "timing_v03_chord_marker_backup_forward.musicxml", TABRAW, out_ir)
    assert score is not None
    assert out_ir.exists()


def test_v03_audiveris_heavy_rewinds(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_audiveris_heavy_rewinds.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "audiveris.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_v03_audiveris_heavy_rewinds.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_v03_high_count_timing_risk(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_high_count_timing_risk.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_many_timing_risks" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "high_count.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_v03_high_count_timing_risk.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_v03_valid_counterpart(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_valid_counterpart.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert not any(issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "valid.ir.json"
    score = build_ir_from_files(FIXTURES / "timing_v03_valid_counterpart.musicxml", TABRAW, out_ir)
    assert score is not None
    assert out_ir.exists()


def test_v03_alignment_not_attempted(tmp_path) -> None:
    imported = parse_musicxml(FIXTURES / "timing_v03_alignment_not_attempted.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.code == "musicxml_alignment_not_attempted_due_to_timing_risk" and issue.severity == "error" for issue in issues)

    out_ir = tmp_path / "alignment_not_attempted.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_v03_alignment_not_attempted.musicxml", TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_unrecoverable_timing_report_generation(tmp_path) -> None:
    import json
    out_ir = tmp_path / "failed_score.ir.json"
    diagnostics_out_path = tmp_path / "diagnostics.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(
            FIXTURES / "timing_overfull_measure.musicxml",
            TABRAW,
            out_path=out_ir,
            diagnostics_out_path=diagnostics_out_path,
        )

    # Check payload has reference
    payload = raised.value.to_diagnostics_payload()
    assert payload.get("unrecoverable_timing_report_json") == "musicxml-unrecoverable-timing-report.json"
    assert payload.get("unrecoverable_timing_report_html") == "musicxml-unrecoverable-timing-report.html"

    # Check that sidecars were written
    json_report_path = tmp_path / "musicxml-unrecoverable-timing-report.json"
    html_report_path = tmp_path / "musicxml-unrecoverable-timing-report.html"
    assert json_report_path.exists()
    assert html_report_path.exists()

    # Load JSON report
    report = json.loads(json_report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "musicxml-unrecoverable-timing-report.v0.1"
    assert report["timing_status"] == "failed"
    assert report["timing_gate_status"] == "refused"
    assert report["calibration_possible"] is False
    assert report["automatic_repair_attempted"] is False
    assert report["overfull_measure_count"] > 0
    assert report["remediation_hint"] is not None

    # Verify no private note details, pitches, lyrics are in JSON keys or values
    private_keys_or_substrings = ["pitch", "alter", "step", "octave", "lyric", "chord_symbol", "note_name"]
    for key, val in report.items():
        for p in private_keys_or_substrings:
            assert p not in str(key)
            if isinstance(val, str):
                assert p not in val

    # Verify HTML contents
    html_content = html_report_path.read_text(encoding="utf-8")
    assert "MusicXML timing is unrecoverable" in html_content
    assert "remediation-card" in html_content
    assert "calibration_possible" in html_content
    assert "remediation guidance" in html_content.lower()
    assert "table" in html_content.lower()

