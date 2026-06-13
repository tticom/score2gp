import json
import subprocess
import sys
from pathlib import Path

def test_note_candidate_recognition_report_public_fixture():
    script_path = Path("scripts/note_candidate_recognition_report.py")
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

    cand1 = outcomes[0]
    assert cand1["symbol_type"] == "whole_note_candidate"

def test_note_candidate_recognition_report_half_note_fixture():
    script_path = Path("scripts/note_candidate_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_half_note.pdf")

    assert script_path.exists()
    assert fixture_path.exists()

    result = subprocess.run(
        [sys.executable, str(script_path), "--pdf", str(fixture_path), "--json"],
        capture_output=True,
        text=True,
        check=True
    )

    data = json.loads(result.stdout)
    outcomes = data["read_only_recognition_outcomes"]
    
    half_notes = [o for o in outcomes if o["symbol_type"] == "half_note_candidate"]
    assert len(half_notes) == 2
