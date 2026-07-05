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

    with patch("score2gp.whole_note_recogniser.run_recognition_on_file") as mock_recognise:
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

    with patch("score2gp.whole_note_recogniser.run_recognition_on_file") as mock_recognise:
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

    with patch("score2gp.whole_note_recogniser.run_recognition_on_file") as mock_recognise:
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

    with patch("score2gp.whole_note_recogniser.run_recognition_on_file") as mock_recognise:
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

    with patch("score2gp.whole_note_recogniser.run_recognition_on_file") as mock_recognise:
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

    with patch("score2gp.whole_note_recogniser.run_recognition_on_file") as mock_recognise:
        mock_recognise.return_value = mock_recognition_result

        result = runner.invoke(app, [
            "notation-half-note-export",
            "--pdf", str(pdf_path),
            "--out", str(out_gp)
        ])

        assert result.exit_code == 1
        assert "Error: Bridge produced non-half note" in result.stderr or "Error: Bridge produced non-half note" in result.stdout
        assert not out_gp.exists()

def test_notation_whole_note_export_with_assume_treble_clef_real_fixture(tmp_path):
    from score2gp.gp_package import inspect_gp
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    out_gp = tmp_path / "out_real.gp"

    result = runner.invoke(app, [
        "notation-whole-note-export",
        "--pdf", str(pdf_path),
        "--out", str(out_gp),
        "--assume-treble-clef"
    ])

    assert result.exit_code == 0
    assert out_gp.exists()

    summary = inspect_gp(out_gp)
    assert not summary["package"]["errors"]
    assert summary["note_count"] > 0

def test_notation_whole_note_export_fails_on_real_fixture_without_flag(tmp_path):
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    out_gp = tmp_path / "out_real_fail.gp"

    result = runner.invoke(app, [
        "notation-whole-note-export",
        "--pdf", str(pdf_path),
        "--out", str(out_gp)
    ])

    assert result.exit_code == 1
    assert "NotationBridgeInputError" in result.stdout or "NotationBridgeInputError" in result.stderr
    assert not out_gp.exists()

