from __future__ import annotations

from pathlib import Path
import pytest

from score2gp.musicxml import parse_musicxml, analyze_musicxml_timing
from score2gp.build_ir import build_ir_from_files, BuildIrInputRiskError

FIXTURES = Path("tests/fixtures/musicxml")
TABRAW = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")


def test_same_voice_overfull_reports_precise_overfull() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_same_voice_overfull.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any("musicxml_same_voice_measure_overfull" in issue.secondary_reasons for issue in issues)
    assert any(issue.overfull_divisions == 1.0 for issue in issues)


def test_accumulated_small_overflow_reports_accumulated_overflow() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_same_voice_accumulated_overflow.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any("musicxml_accumulated_duration_overflow" in issue.secondary_reasons for issue in issues)


def test_same_voice_overlap_reports_overlap_reason() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_same_voice_event_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any("musicxml_same_voice_event_overlap" in issue.secondary_reasons for issue in issues)


def test_rest_note_overlap_reports_rest_note_overlap() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_same_voice_rest_note_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any("musicxml_same_voice_rest_note_overlap" in issue.secondary_reasons for issue in issues)


def test_backup_no_voice_switch_overlap_reports_same_voice_overlap() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_backup_no_voice_switch_overlap.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any("musicxml_same_voice_event_overlap" in issue.secondary_reasons for issue in issues)


def test_event_extends_past_measure_reports_event_extends_past_measure() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_event_extends_past_measure.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any("musicxml_event_extends_past_measure" in issue.secondary_reasons for issue in issues)


def test_compound_meter_overfull_reports_compound_overfull() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_compound_meter_overfull.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any("musicxml_same_voice_measure_overfull" in issue.secondary_reasons for issue in issues)


def test_invalid_duration_grid_reports_calibration_required() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_invalid_duration_grid.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any("musicxml_invalid_duration_grid" in issue.secondary_reasons for issue in issues)
    assert any("musicxml_timing_calibration_required" in issue.secondary_reasons for issue in issues)


def test_many_invalid_events_reports_overlap_count() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_many_invalid_events.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert any(issue.overlap_count is not None and issue.overlap_count > 1 for issue in issues)


def test_valid_counterparts_pass() -> None:
    imported = parse_musicxml(FIXTURES / "timing_vc_valid_counterparts.musicxml")
    issues = analyze_musicxml_timing(imported)
    assert not any(issue.severity == "error" for issue in issues)


@pytest.mark.parametrize("fixture_name", [
    "timing_vc_same_voice_overfull.musicxml",
    "timing_vc_same_voice_accumulated_overflow.musicxml",
    "timing_vc_same_voice_event_overlap.musicxml",
    "timing_vc_same_voice_rest_note_overlap.musicxml",
    "timing_vc_backup_no_voice_switch_overlap.musicxml",
    "timing_vc_event_extends_past_measure.musicxml",
    "timing_vc_compound_meter_overfull.musicxml",
    "timing_vc_invalid_duration_grid.musicxml",
    "timing_vc_many_invalid_events.musicxml",
])
def test_invalid_timing_blocks_alignment(tmp_path, fixture_name) -> None:
    out_ir = tmp_path / "blocked.ir.json"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / fixture_name, TABRAW, out_ir)
    assert raised.value.category == "musicxml_timing_risk"


def test_no_private_fixtures_are_used() -> None:
    # Ensure no file in tests/fixtures/musicxml/ contains any private music info
    for path in FIXTURES.glob("*.musicxml"):
        content = path.read_text(encoding="utf-8")
        assert "private" not in content.lower()
        # Verify titles or other sensitive fields are boring/generic
        assert "beethoven" not in content.lower()
        assert "bach" not in content.lower()
        assert "metallica" not in content.lower()


def test_calibration_scenarios(tmp_path) -> None:
    out_ir = tmp_path / "blocked.ir.json"

    # Scenario 1: Drift candidate
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_drift_candidate.musicxml", TABRAW, out_ir)
    payload = raised.value.to_diagnostics_payload()
    assert payload["calibration_possible"] is True
    assert payload["calibration_candidate_reason"] == "musicxml_timing_calibration_candidate"
    assert not payload["calibration_blocking_reasons"]
    assert payload["overfull_bar_count"] == 1
    assert payload["underfull_bar_count"] == 0
    assert payload["automatic_repair_attempted"] is False
    assert "remediation_hint" in payload

    # Scenario 2: Large overfull
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_large_overfull.musicxml", TABRAW, out_ir)
    payload = raised.value.to_diagnostics_payload()
    assert payload["calibration_possible"] is False
    assert "musicxml_overfull_too_large_for_calibration" in payload["calibration_blocking_reasons"]
    assert payload["overfull_bar_count"] == 1

    # Scenario 3: Same-voice overlap
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_overlap_blocks.musicxml", TABRAW, out_ir)
    payload = raised.value.to_diagnostics_payload()
    assert payload["calibration_possible"] is False
    assert "musicxml_overlap_blocks_calibration" in payload["calibration_blocking_reasons"]
    assert payload["overlap_count"] >= 1

    # Scenario 4: Tie continuity risk
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_tie_continuity_blocks.musicxml", TABRAW, out_ir)
    payload = raised.value.to_diagnostics_payload()
    assert payload["calibration_possible"] is False
    assert "musicxml_tie_continuity_blocks_calibration" in payload["calibration_blocking_reasons"]
    assert payload["tie_continuity_risk_count"] >= 1

    # Scenario 5: Many timing risks
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_many_risks_blocks.musicxml", TABRAW, out_ir)
    payload = raised.value.to_diagnostics_payload()
    assert payload["calibration_possible"] is False
    assert "musicxml_many_risks_block_calibration" in payload["calibration_blocking_reasons"]
    assert payload["many_risk_summary_count"] >= 1

    # Scenario 6: Mixed underfull/overfull
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_mixed_blocks.musicxml", TABRAW, out_ir)
    payload = raised.value.to_diagnostics_payload()
    assert payload["calibration_possible"] is False
    assert "musicxml_mixed_underfull_overfull_blocks_calibration" in payload["calibration_blocking_reasons"]
    assert payload["overfull_bar_count"] == 1
    assert payload["underfull_bar_count"] == 1

    # Scenario 7: Invalid duration grid
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_invalid_grid_blocks.musicxml", TABRAW, out_ir)
    payload = raised.value.to_diagnostics_payload()
    assert payload["calibration_possible"] is False
    assert "musicxml_invalid_grid_blocks_calibration" in payload["calibration_blocking_reasons"]
    assert payload["invalid_grid_count"] >= 1

    # Scenario 8: Multiple affected events but ordered
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_multi_affected_ordered.musicxml", TABRAW, out_ir)
    payload = raised.value.to_diagnostics_payload()
    assert payload["calibration_possible"] is True
    assert payload["affected_event_count"] >= 1

    # Scenario 9: Unrecoverable synthetic summary approximating the private smoke blocker shape
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(FIXTURES / "timing_vc_unrecoverable_summary.musicxml", TABRAW, out_ir)
    payload = raised.value.to_diagnostics_payload()
    assert payload["calibration_possible"] is False
    assert "musicxml_overfull_too_large_for_calibration" in payload["calibration_blocking_reasons"]
    assert "musicxml_overlap_blocks_calibration" in payload["calibration_blocking_reasons"]
    assert payload["affected_event_count"] >= 2
    assert payload["overfull_bar_count"] == 1

    # Scenario 10: Valid counterpart passes
    build_ir_from_files(FIXTURES / "timing_vc_valid_counterpart.musicxml", TABRAW, out_ir)
    assert out_ir.exists()
