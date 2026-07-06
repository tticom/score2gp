import pytest
from typer.testing import CliRunner
from unittest.mock import patch
from src.score2gp.cli import app

runner = CliRunner()

def test_single_note_export_rejects_multi_note_pdf(tmp_path):
    ir_out = tmp_path / "out.ir.json"
    gp_out = tmp_path / "out.gp"
    
    mock_outcomes = {
        "read_only_recognition_outcomes": [
            {
                "symbol_type": "quarter_note_candidate",
                "association_status": "success",
                "duration": "quarter",
                "clef_resolved_staff_pitch": "B4",
                "bbox": [10.0, 0, 10.0, 0]
            },
            {
                "symbol_type": "quarter_note_candidate",
                "association_status": "success",
                "duration": "quarter",
                "clef_resolved_staff_pitch": "G4",
                "bbox": [20.0, 0, 20.0, 0]
            }
        ]
    }
    
    with patch("src.score2gp.whole_note_recogniser.run_recognition_on_file", return_value=mock_outcomes):
        result = runner.invoke(app, [
            "notation-quarter-note-export",
            "--pdf", "fixtures/public/generated_simple/simple/4QuarterNotes.pdf",
            "--out", str(gp_out),
            "--ir-out", str(ir_out)
        ])
        
    assert result.exit_code == 1
    assert "single-note export requires exactly 1" in result.output
