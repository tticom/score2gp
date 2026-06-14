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

def test_note_candidate_recognition_report_quarter_note_fixture():
    script_path = Path("scripts/note_candidate_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")

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

    quarter_notes = [o for o in outcomes if o["symbol_type"] == "quarter_note_candidate"]
    assert len(quarter_notes) == 2

def test_note_candidate_recognition_report_x_aligned_cluster_fixture():
    script_path = Path("scripts/note_candidate_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_complex_cluster.pdf")

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

    x_aligned_clusters = [o for o in outcomes if o["symbol_type"] == "x_aligned_cluster_candidate"]
    assert len(x_aligned_clusters) == 5

def test_note_candidate_recognition_report_left_margin_candidate_fixture():
    script_path = Path("scripts/note_candidate_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_complex_cluster.pdf")

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

    left_margin_candidates = [o for o in outcomes if o["symbol_type"] == "left_margin_candidate"]
    assert len(left_margin_candidates) == 1

def test_note_candidate_recognition_report_flag_beam_candidates():
    script_path = Path("scripts/note_candidate_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_complex_cluster.pdf")

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

    flags = [o for o in outcomes if o["symbol_type"] == "flag_candidate"]
    beams = [o for o in outcomes if o["symbol_type"] == "beam_candidate"]

    assert len(beams) > 0
