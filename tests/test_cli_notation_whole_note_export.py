import json
from pathlib import Path
from unittest.mock import patch
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_bridge import NotationBridgeInputError
from score2gp.ir import ScoreIR

runner = CliRunner()

def test_cli_help_exposes_notation_whole_note_export():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "notation-whole-note-export" in result.stdout

def test_notation_whole_note_export_success(tmp_path):
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.touch()
    out_gp = tmp_path / "out.gp"

    mock_outcomes = [{"symbol_type": "whole_note_candidate", "association_status": "success", "duration": "whole", "clef_resolved_staff_pitch": "B4"}]
    mock_recognition_result = {"read_only_recognition_outcomes": mock_outcomes}

    with patch("score2gp.notation_omr.pipeline.run_recognition_on_file") as mock_recognise:
        mock_recognise.return_value = mock_recognition_result

        result = runner.invoke(app, [
            "notation-whole-note-export",
            "--pdf", str(pdf_path),
            "--out", str(out_gp)
        ])

        assert result.exit_code == 0
        assert mock_recognise.call_count == 1
        assert out_gp.exists()

def test_notation_whole_note_export_fails_on_no_outcomes(tmp_path):
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.touch()
    out_gp = tmp_path / "out.gp"

    mock_recognition_result = {"read_only_recognition_outcomes": []}

    with patch("score2gp.notation_omr.pipeline.run_recognition_on_file") as mock_recognise:
        mock_recognise.return_value = mock_recognition_result

        result = runner.invoke(app, [
            "notation-whole-note-export",
            "--pdf", str(pdf_path),
            "--out", str(out_gp)
        ])

        assert result.exit_code == 1
        assert "NotationBridgeInputError" in result.stderr or "NotationBridgeInputError" in result.stdout
        assert mock_recognise.call_count == 1
        assert not out_gp.exists()

def test_cli_help_exposes_notation_half_note_export():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "notation-half-note-export" in result.stdout

def test_notation_half_note_export_success(tmp_path):
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.touch()
    out_gp = tmp_path / "out_half.gp"

    mock_outcomes = [{"symbol_type": "half_note_candidate", "association_status": "success", "duration": "half", "clef_resolved_staff_pitch": "B4"}]
    mock_recognition_result = {"read_only_recognition_outcomes": mock_outcomes}

    with patch("score2gp.notation_omr.pipeline.run_recognition_on_file") as mock_recognise:
        mock_recognise.return_value = mock_recognition_result

        result = runner.invoke(app, [
            "notation-half-note-export",
            "--pdf", str(pdf_path),
            "--out", str(out_gp)
        ])

        assert result.exit_code == 0
        assert mock_recognise.call_count == 1
        assert out_gp.exists()

def test_notation_half_note_export_fails_on_no_outcomes(tmp_path):
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.touch()
    out_gp = tmp_path / "out_half_fail.gp"

    mock_recognition_result = {"read_only_recognition_outcomes": []}

    with patch("score2gp.notation_omr.pipeline.run_recognition_on_file") as mock_recognise:
        mock_recognise.return_value = mock_recognition_result

        result = runner.invoke(app, [
            "notation-half-note-export",
            "--pdf", str(pdf_path),
            "--out", str(out_gp)
        ])

        assert result.exit_code == 1
        assert "NotationBridgeInputError" in result.stderr or "NotationBridgeInputError" in result.stdout
        assert mock_recognise.call_count == 1
        assert not out_gp.exists()

def test_notation_whole_note_export_rejects_half_note(tmp_path):
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.touch()
    out_gp = tmp_path / "out_whole_fail.gp"

    # Feed half note outcome to whole note CLI
    mock_outcomes = [{"symbol_type": "half_note_candidate", "association_status": "success", "duration": "half", "clef_resolved_staff_pitch": "B4"}]
    mock_recognition_result = {"read_only_recognition_outcomes": mock_outcomes}

    with patch("score2gp.notation_omr.pipeline.run_recognition_on_file") as mock_recognise:
        mock_recognise.return_value = mock_recognition_result

        result = runner.invoke(app, [
            "notation-whole-note-export",
            "--pdf", str(pdf_path),
            "--out", str(out_gp)
        ])

        assert result.exit_code == 1
        assert "Error: Bridge produced non-whole note" in result.stderr or "Error: Bridge produced non-whole note" in result.stdout
        assert not out_gp.exists()

def test_notation_half_note_export_rejects_whole_note(tmp_path):
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.touch()
    out_gp = tmp_path / "out_half_fail2.gp"

    # Feed whole note outcome to half note CLI
    mock_outcomes = [{"symbol_type": "whole_note_candidate", "association_status": "success", "duration": "whole", "clef_resolved_staff_pitch": "B4"}]
    mock_recognition_result = {"read_only_recognition_outcomes": mock_outcomes}

    with patch("score2gp.notation_omr.pipeline.run_recognition_on_file") as mock_recognise:
        mock_recognise.return_value = mock_recognition_result

        result = runner.invoke(app, [
            "notation-half-note-export",
            "--pdf", str(pdf_path),
            "--out", str(out_gp)
        ])

        assert result.exit_code == 1
        assert "Error: Bridge produced non-half note" in result.stderr or "Error: Bridge produced non-half note" in result.stdout
        assert not out_gp.exists()

def test_notation_whole_note_export_fails_on_real_fixture_due_to_multiple_notes(tmp_path):
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    out_gp = tmp_path / "out_real.gp"

    result = runner.invoke(app, [
        "notation-whole-note-export",
        "--pdf", str(pdf_path),
        "--out", str(out_gp),
        "--assume-treble-clef"
    ])

    assert result.exit_code == 1
    assert "Error: Found 2 whole-note candidates but single-note export requires exactly 1" in result.stderr or \
           "Error: Found 2 whole-note candidates but single-note export requires exactly 1" in result.stdout
    assert not out_gp.exists()

def test_notation_whole_note_export_fails_on_real_fixture_without_flag(tmp_path):
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    out_gp = tmp_path / "out_real_fail.gp"

    result = runner.invoke(app, [
        "notation-whole-note-export",
        "--pdf", str(pdf_path),
        "--out", str(out_gp)
    ])

    assert result.exit_code == 1
    assert "Error: Found 2 whole-note candidates but single-note export requires exactly 1" in result.stderr or \
           "Error: Found 2 whole-note candidates but single-note export requires exactly 1" in result.stdout
    assert not out_gp.exists()

def test_notation_whole_note_export_fails_without_pitch_resolution(tmp_path):
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.touch()
    out_gp = tmp_path / "out.gp"

    # Outcome has no clef_resolved_staff_pitch, simulating lack of clef/flag
    mock_outcomes = [{"symbol_type": "whole_note_candidate", "association_status": "success", "duration": "whole"}]
    mock_recognition_result = {"read_only_recognition_outcomes": mock_outcomes}

    with patch("score2gp.notation_omr.pipeline.run_recognition_on_file") as mock_recognise:
        mock_recognise.return_value = mock_recognition_result

        result = runner.invoke(app, [
            "notation-whole-note-export",
            "--pdf", str(pdf_path),
            "--out", str(out_gp)
        ])

        assert result.exit_code == 1
        assert "NotationBridgeInputError" in result.stderr or "NotationBridgeInputError" in result.stdout
        assert mock_recognise.call_count == 1
        assert not out_gp.exists()

def test_coverage_report_under_assume_treble_clef():
    from score2gp.whole_note_recogniser import run_recognition_on_file
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    res = run_recognition_on_file(pdf_path, assume_treble_clef=True)
    report = res["clef_resolved_pitch_coverage"]
    
    assert report["assumed_clef_mode"] is True
    assert report["note_candidates_on_staves_with_assumed_clef"] == 2
    assert report["note_candidates_with_assumed_treble_clef_pitch"] == 2
    assert report["note_candidates_on_staves_with_valid_clef"] == 0
    assert report["note_candidates_with_clef_resolved_staff_pitch"] == 2

def test_coverage_report_without_assume_treble_clef():
    from score2gp.whole_note_recogniser import run_recognition_on_file
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    res = run_recognition_on_file(pdf_path, assume_treble_clef=False)
    report = res["clef_resolved_pitch_coverage"]
    
    assert report["assumed_clef_mode"] is False
    assert report["note_candidates_on_staves_with_assumed_clef"] == 0
    assert report["note_candidates_with_assumed_treble_clef_pitch"] == 0
    assert report["note_candidates_on_staves_with_valid_clef"] == 0
    assert report["note_candidates_with_clef_resolved_staff_pitch"] == 0

def test_notation_whole_note_export_success_real_fixture(tmp_path):
    from score2gp.whole_note_recogniser import run_recognition_on_file
    from score2gp.gp_package import inspect_gp, validate_gp

    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_single_whole_note.pdf")
    out_gp = tmp_path / "out_success.gp"

    # 1. Candidate-count validation through real recognition
    res = run_recognition_on_file(pdf_path, assume_treble_clef=True)
    outcomes = res["read_only_recognition_outcomes"]
    assert len(outcomes) == 1
    assert outcomes[0]["symbol_type"] == "whole_note_candidate"
    assert outcomes[0]["association_status"] == "success"

    # 2. CLI execution without patching
    result = runner.invoke(app, [
        "notation-whole-note-export",
        "--pdf", str(pdf_path),
        "--out", str(out_gp),
        "--assume-treble-clef"
    ])

    assert result.exit_code == 0, f"CLI output: {result.stdout or result.stderr}"
    assert out_gp.exists()

    # 3. GP package validation and inspection
    val_result = validate_gp(out_gp)
    assert not val_result["errors"]

    summary = inspect_gp(out_gp)
    assert len(summary["tracks"]) == 1
    assert summary["note_count"] == 1
