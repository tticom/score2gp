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

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

    cand1 = whole_notes[0]
    assert cand1["symbol_type"] == "whole_note_candidate"
    assert cand1["system_index"] is not None
    assert cand1["staff_index"] is not None
    assert "staff_position_index" in cand1
    assert isinstance(cand1["staff_position_index"], int)
    assert cand1["staff_position_index"] == 2
    assert "assumed_treble_pitch" not in cand1

    cand2 = whole_notes[1]
    assert "staff_position_index" in cand2
    assert cand2["staff_position_index"] == 4
    assert "assumed_treble_pitch" not in cand2

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

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0
    for cand in half_notes:
        assert cand["system_index"] is not None
        assert cand["staff_index"] is not None
        assert "staff_position_index" in cand
        assert isinstance(cand["staff_position_index"], int)
        assert cand["staff_position_index"] == 4

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

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0
    for cand in quarter_notes:
        assert cand["system_index"] is not None
        assert cand["staff_index"] is not None
        assert "staff_position_index" in cand
        assert isinstance(cand["staff_position_index"], int)
        assert cand["staff_position_index"] == 4

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

    explicit_flag_found = False
    for f in flags:
        bbox = f["bbox"]
        # Intended explicit wide-curve flag is at x=115..125, y=185..210.
        # Allow +/- 5 margin for pdf bounds extraction rounding.
        # Y must be < 210 to avoid accepting lower notehead quadrants which sit at y=210..220.
        if (110.0 <= bbox[0] and bbox[2] <= 130.0 and
            180.0 <= bbox[1] and bbox[3] <= 215.0 and
            (bbox[3] - bbox[1]) >= 15.0): # must have height similar to the full stem/flag (25)
            explicit_flag_found = True
            break
    assert explicit_flag_found, "Intended explicit flag bbox not found"

    beams = [o for o in outcomes if o["symbol_type"] == "beam_candidate"]
    assert len(beams) > 0

    for cand in quarter_notes + flags + beams:
        assert cand["page_index"] is not None
        assert cand["system_index"] is not None
        assert cand["staff_index"] is not None
        assert cand["bbox"] is not None

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) >= 3

    flagged = [e for e in eighth_notes if e["modifier_type"] == "flag_candidate"]
    beamed = [e for e in eighth_notes if e["modifier_type"] == "beam_candidate"]

    assert len(flagged) >= 1
    assert len(beamed) >= 2

    for cand in eighth_notes:
        assert cand["page_index"] == 1
        assert cand["system_index"] is not None
        assert cand["staff_index"] is not None
        assert cand["quarter_component_id"] is not None
        assert cand["modifier_component_id"] is not None
        assert "staff_position_index" in cand
        assert isinstance(cand["staff_position_index"], int)
        assert cand["staff_position_index"] == 4

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

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

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

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

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

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

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

def test_compose_eighth_note_candidates_positive_boundaries():
    from score2gp.whole_note_recogniser import compose_eighth_note_candidates

    # Matching staff, page, system, and touching bbox
    q1 = {
        "candidate_id": "q1",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [100.0, 185.0, 115.0, 220.0],
        "source": "test"
    }
    f1 = {
        "candidate_id": "f1",
        "symbol_type": "flag_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [115.0, 185.0, 125.0, 210.0]
    }

    # Beam touches multiple quarters
    q2 = {
        "candidate_id": "q2",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [200.0, 185.0, 215.0, 220.0],
        "source": "test"
    }
    q3 = {
        "candidate_id": "q3",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [250.0, 185.0, 265.0, 220.0],
        "source": "test"
    }
    b1 = {
        "candidate_id": "b1",
        "symbol_type": "beam_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [215.0, 185.0, 265.0, 190.0]
    }

    outcomes = [q1, q2, q3, f1, b1]
    eighths = compose_eighth_note_candidates(outcomes)

    assert len(eighths) == 3

    flagged = [e for e in eighths if e["modifier_type"] == "flag_candidate"]
    assert len(flagged) == 1
    assert flagged[0]["quarter_component_id"] == "q1"
    assert flagged[0]["modifier_component_id"] == "f1"

    beamed = [e for e in eighths if e["modifier_type"] == "beam_candidate"]
    assert len(beamed) == 2
    assert beamed[0]["quarter_component_id"] == "q2"
    assert beamed[1]["quarter_component_id"] == "q3"

def test_compose_eighth_note_candidates_negative_boundaries():
    from score2gp.whole_note_recogniser import compose_eighth_note_candidates

    # Different staff
    q1 = {
        "candidate_id": "q1",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [100.0, 185.0, 115.0, 220.0]
    }
    f1 = {
        "candidate_id": "f1",
        "symbol_type": "flag_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 2, # Different staff
        "bbox": [115.0, 185.0, 125.0, 210.0]
    }

    # Different page
    q2 = {
        "candidate_id": "q2",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [200.0, 185.0, 215.0, 220.0]
    }
    b1 = {
        "candidate_id": "b1",
        "symbol_type": "beam_candidate",
        "page_index": 2, # Different page
        "system_index": 1,
        "staff_index": 1,
        "bbox": [215.0, 185.0, 265.0, 190.0]
    }

    # Missing bbox logic (too loose relationship)
    q3 = {
        "candidate_id": "q3",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [300.0, 185.0, 315.0, 220.0]
    }
    f2 = {
        "candidate_id": "f2",
        "symbol_type": "flag_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [400.0, 185.0, 410.0, 210.0] # Too far!
    }

    # Notehead quadrant (strictly overlaps quarter notehead)
    q4 = {
        "candidate_id": "q4",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [500.0, 210.0, 515.0, 220.0]
    }
    f3 = {
        "candidate_id": "f3",
        "symbol_type": "flag_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [500.0, 210.0, 507.5, 215.0] # quadrant inside notehead
    }

    # Malformed bbox
    q5 = {
        "candidate_id": "q5",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [600.0, 185.0] # short bbox
    }
    f4 = {
        "candidate_id": "f4",
        "symbol_type": "flag_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [615.0, 185.0, 625.0, 210.0]
    }
    q6 = {
        "candidate_id": "q6",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [700.0, 185.0, 715.0, 220.0]
    }
    f5 = {
        "candidate_id": "f5",
        "symbol_type": "flag_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": "invalid" # wrong type
    }
    q7 = {
        "candidate_id": "q7",
        "symbol_type": "quarter_note_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [815.0, 185.0, 800.0, 220.0] # invalid coordinates x0 > x1
    }
    f6 = {
        "candidate_id": "f6",
        "symbol_type": "flag_candidate",
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "bbox": [815.0, 185.0, 825.0, 210.0]
    }

    outcomes = [q1, f1, q2, b1, q3, f2, q4, f3, q5, f4, q6, f5, q7, f6]
    eighths = compose_eighth_note_candidates(outcomes)

    assert len(eighths) == 0

def test_note_candidate_recognition_report_staff_geometry_exposure():
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
    assert "staff_geometry" in data

    staff_geometry = data["staff_geometry"]
    assert isinstance(staff_geometry, list)
    assert len(staff_geometry) > 0

    outcomes = data["read_only_recognition_outcomes"]
    assert len(outcomes) > 0
    note_candidate = outcomes[0]

    join_success = False

    for geom in staff_geometry:
        assert "page_index" in geom
        assert "system_index" in geom
        assert "staff_index" in geom
        assert "bbox" in geom
        assert "line_y_coords" in geom

        assert len(geom["bbox"]) == 4
        assert len(geom["line_y_coords"]) == 5
        for y in geom["line_y_coords"]:
            assert isinstance(y, (int, float))

        if (geom["page_index"] == note_candidate["page_index"] and
            geom["system_index"] == note_candidate["system_index"] and
            geom["staff_index"] == note_candidate["staff_index"]):
            join_success = True

    assert join_success, "Could not join note candidate to staff geometry by page, system, and staff index."

def test_map_staff_position_to_read_only_outcomes_malformed_inputs():
    from score2gp.whole_note_recogniser import map_staff_position_to_read_only_outcomes
    outcomes = [
        # missing bbox
        {"symbol_type": "whole_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1},
        # malformed bbox (not 4 elements)
        {"symbol_type": "quarter_note_candidate", "bbox": [1, 2, 3], "page_index": 1, "system_index": 1, "staff_index": 1},
        # string bbox
        {"symbol_type": "half_note_candidate", "bbox": "invalid", "page_index": 1, "system_index": 1, "staff_index": 1},
        # reversed bbox x
        {"symbol_type": "whole_note_candidate", "bbox": [10, 20, 5, 30], "page_index": 1, "system_index": 1, "staff_index": 1},
        # reversed bbox y
        {"symbol_type": "whole_note_candidate", "bbox": [5, 30, 10, 20], "page_index": 1, "system_index": 1, "staff_index": 1},
        # bbox is an integer
        {"symbol_type": "whole_note_candidate", "bbox": 123, "page_index": 1, "system_index": 1, "staff_index": 1},
        # bbox is None
        {"symbol_type": "whole_note_candidate", "bbox": None, "page_index": 1, "system_index": 1, "staff_index": 1},
        # no matching staff geometry
        {"symbol_type": "whole_note_candidate", "bbox": [1, 2, 3, 4], "page_index": 2, "system_index": 1, "staff_index": 1},
        # eighth note missing quarter id
        {"symbol_type": "eighth_note_candidate", "bbox": [1, 2, 3, 4], "page_index": 1, "system_index": 1, "staff_index": 1},
        # eighth note missing quarter candidate
        {"symbol_type": "eighth_note_candidate", "quarter_component_id": "q1", "bbox": [1, 2, 3, 4], "page_index": 1, "system_index": 1, "staff_index": 1},
        # whole note malformed line_y_coords
        {"symbol_type": "whole_note_candidate", "bbox": [1, 2, 3, 4], "page_index": 3, "system_index": 1, "staff_index": 1},
    ]

    staff_geometries = [
        {"page_index": 1, "system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40, 50]},
        {"page_index": 3, "system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40]}, # Only 4 lines
    ]

    map_staff_position_to_read_only_outcomes(outcomes, staff_geometries)

    for cand in outcomes:
        assert "staff_position_index" not in cand

def test_assume_treble_clef_enabled_public_fixture():
    script_path = Path("scripts/note_candidate_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")

    assert script_path.exists()
    assert fixture_path.exists()

    result = subprocess.run(
        [sys.executable, str(script_path), "--pdf", str(fixture_path), "--json", "--assume-treble-clef"],
        capture_output=True,
        text=True,
        check=True
    )

    data = json.loads(result.stdout)
    outcomes = data["read_only_recognition_outcomes"]
    whole_notes = [o for o in outcomes if o["symbol_type"] == "whole_note_candidate"]
    assert len(whole_notes) == 2

    cand1 = whole_notes[0]
    assert cand1["staff_position_index"] == 2
    assert cand1["assumed_treble_pitch"] == "D5"

    cand2 = whole_notes[1]
    assert cand2["staff_position_index"] == 4
    assert cand2["assumed_treble_pitch"] == "B4"

def test_assume_treble_clef_out_of_bounds():
    from score2gp.whole_note_recogniser import map_assumed_treble_pitch_to_read_only_outcomes

    outcomes = [
        {"staff_position_index": -1},
        {"staff_position_index": 9},
        {"staff_position_index": -3},
        {"staff_position_index": 13},
    ]

    map_assumed_treble_pitch_to_read_only_outcomes(outcomes)

    for cand in outcomes:
        assert "assumed_treble_pitch" not in cand

def test_assume_treble_clef_malformed_and_missing():
    from score2gp.whole_note_recogniser import map_assumed_treble_pitch_to_read_only_outcomes

    outcomes = [
        {},
        {"staff_position_index": None},
        {"staff_position_index": "4"},
        {"staff_position_index": 4.0},
        {"staff_position_index": []},
        {"staff_position_index": {}},
    ]

    map_assumed_treble_pitch_to_read_only_outcomes(outcomes)

    for cand in outcomes:
        assert "assumed_treble_pitch" not in cand

def test_assume_treble_clef_exact_mapping():
    from score2gp.whole_note_recogniser import map_assumed_treble_pitch_to_read_only_outcomes

    outcomes = [
        {"staff_position_index": 0},
        {"staff_position_index": 1},
        {"staff_position_index": 2},
        {"staff_position_index": 3},
        {"staff_position_index": 4},
        {"staff_position_index": 5},
        {"staff_position_index": 6},
        {"staff_position_index": 7},
        {"staff_position_index": 8},
    ]

    map_assumed_treble_pitch_to_read_only_outcomes(outcomes)

    expected = ["F5", "E5", "D5", "C5", "B4", "A4", "G4", "F4", "E4"]
    for i, cand in enumerate(outcomes):
        assert cand["assumed_treble_pitch"] == expected[i]
