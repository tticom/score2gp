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

    assert data["source"] == str(fixture_path)
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
