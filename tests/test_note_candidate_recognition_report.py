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
    whole_notes = [o for o in outcomes if o["symbol_type"] == "whole_note_candidate"]
    assert len(whole_notes) == 2

    cand1 = whole_notes[0]
    assert cand1["symbol_type"] == "whole_note_candidate"
    assert cand1["system_index"] is not None
    assert cand1["staff_index"] is not None

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
    for cand in half_notes:
        assert cand["system_index"] is not None
        assert cand["staff_index"] is not None

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
    for cand in quarter_notes:
        assert cand["system_index"] is not None
        assert cand["staff_index"] is not None

def test_note_candidate_recognition_report_eighth_note_fixture():
    script_path = Path("scripts/note_candidate_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_eighth_notes.pdf")

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
    assert len(quarter_notes) >= 3

    flags = [o for o in outcomes if o["symbol_type"] == "flag_candidate"]
    assert len(flags) > 0

    beams = [o for o in outcomes if o["symbol_type"] == "beam_candidate"]
    assert len(beams) > 0

    for cand in quarter_notes + flags + beams:
        assert cand["page_index"] is not None
        assert cand["system_index"] is not None
        assert cand["staff_index"] is not None
        assert cand["bbox"] is not None

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

    for outcome in flags:
        assert outcome["page_index"] == 1
        assert outcome["system_index"] == 1
        assert outcome["staff_index"] == 1

    for outcome in beams:
        assert outcome["page_index"] == 1
        assert outcome["system_index"] == 1
        assert outcome["staff_index"] == 1


def test_associate_staves_horizontal_boundary():
    from score2gp.whole_note_recogniser import _associate_staves

    staves = [{
        "staff": {
            "x0": 50.0,
            "x1": 550.0,
            "y0": 200.0,
            "y1": 240.0,
            "system_index": 0,
            "staff_index": 0
        }
    }]

    cand_inside = {"bbox": [100.0, 210.0, 115.0, 220.0]}
    cand_outside_left = {"bbox": [10.0, 210.0, 25.0, 220.0]}
    cand_outside_right = {"bbox": [600.0, 210.0, 615.0, 220.0]}

    candidates = [cand_inside, cand_outside_left, cand_outside_right]

    _associate_staves(candidates, staves)

    assert cand_inside.get("system_index") == 0
    assert cand_inside.get("staff_index") == 0

    assert cand_outside_left.get("system_index") is None
    assert cand_outside_left.get("staff_index") is None
    assert cand_outside_right.get("system_index") is None
    assert cand_outside_right.get("staff_index") is None
