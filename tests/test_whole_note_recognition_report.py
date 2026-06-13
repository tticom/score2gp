import json
import subprocess
import sys
from pathlib import Path

def test_whole_note_recognition_report_public_fixture():
    script_path = Path("scripts/whole_note_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")

    assert script_path.exists()
    assert fixture_path.exists()

    result = subprocess.run(
        [sys.executable, str(script_path), "--pdf", str(fixture_path), "--json"],
        capture_output=True,
        text=True,
        check=True
    )

    data = json.loads(result.stdout)

    assert data["source"] == fixture_path.name
    assert data["recognition_mode"] == "read_only_diagnostic_derived"
    outcomes = data["read_only_recognition_outcomes"]
    assert len(outcomes) == 2

    # Verify candidate shape
    cand1 = outcomes[0]
    assert cand1["symbol_type"] == "whole_note_candidate"
    assert cand1["candidate_id"] == "whole_note_candidate_001"
    assert "bbox" in cand1
    assert cand1["page_index"] == 1
    assert cand1["source"] == "diagnostic_candidate_evidence"

    cand2 = outcomes[1]
    assert cand2["symbol_type"] == "whole_note_candidate"
    assert cand2["candidate_id"] == "whole_note_candidate_002"
    assert "bbox" in cand2
    assert cand2["page_index"] == 1
    assert cand2["source"] == "diagnostic_candidate_evidence"

def test_whole_note_recognition_report_nested_path_sanitisation(tmp_path):
    import shutil
    script_path = Path("scripts/whole_note_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")

    # Create a nested path in tmp_path
    nested_dir = tmp_path / "deeply" / "nested" / "private_lookalike"
    nested_dir.mkdir(parents=True)
    temp_pdf = nested_dir / "my_secret_score.pdf"
    shutil.copy(fixture_path, temp_pdf)

    result = subprocess.run(
        [sys.executable, str(script_path), "--pdf", str(temp_pdf), "--json"],
        capture_output=True,
        text=True,
        check=True
    )

    data = json.loads(result.stdout)

    assert data["source"] == "my_secret_score.pdf"
    assert "nested" not in data["source"]
    assert "private_lookalike" not in data["source"]
    assert str(tmp_path) not in data["source"]
