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
    ledger_lines = [o for o in outcomes if o["symbol_type"] == "ledger_line_candidate"]

    # The primitive previously extracted as a beam is now safely promoted to a ledger line
    # and suppressed from the beam candidate pool to prevent double emission.
    assert len(beams) == 0
    assert len(ledger_lines) > 0

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

    for outcome in flags:
        assert outcome["page_index"] == 1
        assert outcome["system_index"] == 1
        assert outcome["staff_index"] == 1

    for outcome in ledger_lines:
        assert outcome["page_index"] == 1
        assert outcome["system_index"] == 1
        assert outcome["staff_index"] == 1


def test_note_candidate_recognition_report_ledger_lines():
    script_path = Path("scripts/note_candidate_recognition_report.py")
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_ledger_lines.pdf")

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

    ledger_lines = [o for o in outcomes if o["symbol_type"] == "ledger_line_candidate"]
    beams = [o for o in outcomes if o["symbol_type"] == "beam_candidate"]

    assert len(ledger_lines) == 2
    assert len(beams) == 0

    for cand in ledger_lines:
        assert cand["page_index"] == 1
        assert cand["system_index"] is not None
        assert cand["staff_index"] is not None
        assert "bbox" in cand
        assert "candidate_id" in cand
        assert "staff_position_index" in cand
        assert "assumed_treble_pitch" not in cand

    positions = [c["staff_position_index"] for c in ledger_lines]
    # One is above the staff, one is below the staff.
    assert any(p < 0 for p in positions)
    assert any(p > 8 for p in positions)

    notes = [o for o in outcomes if o["symbol_type"] == "quarter_note_candidate"]
    assert len(notes) == 2

    above_note = next(n for n in notes if n["staff_position_index"] < 0)
    below_note = next(n for n in notes if n["staff_position_index"] > 8)

    above_ledger = next(l for l in ledger_lines if l["staff_position_index"] < 0)
    below_ledger = next(l for l in ledger_lines if l["staff_position_index"] > 8)

    assert "attached_ledger_line_candidate_ids" in above_note
    assert above_note["attached_ledger_line_candidate_ids"] == [above_ledger["candidate_id"]]

    assert "attached_ledger_line_candidate_ids" in below_note
    assert below_note["attached_ledger_line_candidate_ids"] == [below_ledger["candidate_id"]]

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
def test_ledger_line_duplicate_beam_suppression_cross_page(tmp_path, monkeypatch):
    import fitz
    from score2gp.whole_note_recogniser import run_recognition_on_file
    import score2gp.whole_note_recogniser as wnr

    # Create a dummy 2-page PDF
    pdf_path = tmp_path / "dummy.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    # Mock extract_notation_diagnostics_dict
    def mock_extract(page, page_index):
        if page_index == 1:
            return {
                "staves": [
                    {
                        "staff": {"system_index": 1, "staff_index": 1, "x0": 0.0, "x1": 100.0, "y0": 0.0, "y1": 100.0},
                        "x_aligned_cluster_candidates": [
                            {
                                "system_index": 1, "staff_index": 1,
                                "x0": 10.0, "x1": 20.0,
                                "primitive_count": 2,
                                "primitives": [
                                    {"kind": "horizontal_stroke", "x0": 10.0, "y0": 20.0, "x1": 20.0, "y1": 20.0},
                                    {"kind": "rectangle", "x0": 15.0, "y0": 15.0, "x1": 15.0, "y1": 25.0}
                                ]
                            }
                        ],
                        "flag_beam_candidates": {
                            "flags": [],
                            "beams": [
                                {"bbox": [10.0, 20.0, 20.0, 20.0], "primitive_kind": "non_staff_horizontal", "width": 10.0, "height": 0.0}
                            ]
                        }
                    }
                ]
            }
        else:
            return {
                "staves": [
                    {
                        "staff": {"system_index": 1, "staff_index": 1, "x0": 0.0, "x1": 100.0, "y0": 0.0, "y1": 100.0},
                        "x_aligned_cluster_candidates": [],
                        "flag_beam_candidates": {
                            "flags": [],
                            "beams": [
                                {"bbox": [10.0, 20.0, 20.0, 20.0], "primitive_kind": "non_staff_horizontal", "width": 10.0, "height": 0.0}
                            ]
                        }
                    }
                ]
            }

    import score2gp.pdf_staff_notation_diagnostics as psnd
    monkeypatch.setattr(psnd, "extract_notation_diagnostics_dict", mock_extract)
    monkeypatch.setattr(psnd, "_extract_whole_note_candidates", lambda p: [])
    monkeypatch.setattr(psnd, "_extract_half_note_candidates", lambda p: [])
    monkeypatch.setattr(psnd, "_extract_quarter_note_candidates", lambda p: [])

    res = run_recognition_on_file(
        pdf_path,
        include_flag_beam_candidates=True,
        include_ledger_line_candidates=True
    )

    outcomes = res["read_only_recognition_outcomes"]
    ledger_lines = [o for o in outcomes if o["symbol_type"] == "ledger_line_candidate"]
    beams = [o for o in outcomes if o["symbol_type"] == "beam_candidate"]

    assert len(ledger_lines) == 1
    assert len(beams) == 1
    assert ledger_lines[0]["page_index"] == 1
    assert beams[0]["page_index"] == 2

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
        # ledger line missing bbox
        {"symbol_type": "ledger_line_candidate", "page_index": 1, "system_index": 1, "staff_index": 1},
        # ledger line malformed bbox
        {"symbol_type": "ledger_line_candidate", "bbox": [1, 2], "page_index": 1, "system_index": 1, "staff_index": 1},
        # ledger line missing staff geometry
        {"symbol_type": "ledger_line_candidate", "bbox": [1, 2, 3, 4], "page_index": 9, "system_index": 9, "staff_index": 9},
    ]

    staff_geometries = [
        {"page_index": 1, "system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40, 50]},
        {"page_index": 3, "system_index": 1, "staff_index": 1, "line_y_coords": [10, 20, 30, 40]}, # Only 4 lines
    ]

    map_staff_position_to_read_only_outcomes(outcomes, staff_geometries)

    for cand in outcomes:
        assert "staff_position_index" not in cand

def test_map_ledger_lines_to_note_candidates_edge_cases():
    from score2gp.whole_note_recogniser import map_ledger_lines_to_note_candidates

    outcomes = [
        # Note inside staff (0..8) should not attach ledgers
        {"candidate_id": "q1", "symbol_type": "quarter_note_candidate", "staff_position_index": 4, "bbox": [10, 10, 20, 20], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l1", "symbol_type": "ledger_line_candidate", "staff_position_index": 4, "bbox": [8, 15, 22, 17], "page_index": 1, "system_index": 1, "staff_index": 1},

        # Whole note below staff gets attached lines
        {"candidate_id": "w1", "symbol_type": "whole_note_candidate", "staff_position_index": 10, "bbox": [150, 150, 160, 160], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l11", "symbol_type": "ledger_line_candidate", "staff_position_index": 10, "bbox": [148, 155, 162, 157], "page_index": 1, "system_index": 1, "staff_index": 1},

        # Half note above staff gets attached lines
        {"candidate_id": "h1", "symbol_type": "half_note_candidate", "staff_position_index": -4, "bbox": [170, 170, 180, 180], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l12", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [168, 175, 182, 177], "page_index": 1, "system_index": 1, "staff_index": 1},

        # Unrelated ledger line (different page)
        {"candidate_id": "q2", "symbol_type": "quarter_note_candidate", "staff_position_index": -2, "bbox": [30, 30, 40, 40], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l2", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [28, 35, 42, 37], "page_index": 2, "system_index": 1, "staff_index": 1},

        # Ambiguous/unrelated geometric bounds (no horizontal overlap)
        {"candidate_id": "l3", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [500, 35, 510, 37], "page_index": 1, "system_index": 1, "staff_index": 1},

        # Missing staff index on note
        {"candidate_id": "q3", "symbol_type": "quarter_note_candidate", "staff_position_index": -2, "bbox": [50, 50, 60, 60], "page_index": 1, "system_index": 1},
        {"candidate_id": "l4", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [48, 55, 62, 57], "page_index": 1, "system_index": 1, "staff_index": 1},

        # Missing/malformed geometry on ledger line
        {"candidate_id": "q4", "symbol_type": "quarter_note_candidate", "staff_position_index": -2, "bbox": [70, 70, 80, 80], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l5", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [70, 70], "page_index": 1, "system_index": 1, "staff_index": 1},

        # Missing staff index on ledger line
        {"candidate_id": "q5", "symbol_type": "quarter_note_candidate", "staff_position_index": -2, "bbox": [90, 90, 100, 100], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l6", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [88, 95, 102, 97], "page_index": 1, "system_index": 1},

        # Eighth note with missing quarter_component_id lookup
        {"candidate_id": "e1", "symbol_type": "eighth_note_candidate", "quarter_component_id": "missing_q", "staff_position_index": -2, "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l7", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [8, 15, 22, 17], "page_index": 1, "system_index": 1, "staff_index": 1},

        # Note below staff logically skips above-staff ledgers
        {"candidate_id": "q6", "symbol_type": "quarter_note_candidate", "staff_position_index": 10, "bbox": [110, 110, 120, 120], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l8", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [108, 115, 122, 117], "page_index": 1, "system_index": 1, "staff_index": 1},

        # Duplicate/ambiguous lines should both attach if geometry allows, but unrelated don't.
        {"candidate_id": "q7", "symbol_type": "quarter_note_candidate", "staff_position_index": -4, "bbox": [130, 130, 140, 140], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l9", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [128, 135, 142, 137], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l10", "symbol_type": "ledger_line_candidate", "staff_position_index": -4, "bbox": [128, 130, 142, 132], "page_index": 1, "system_index": 1, "staff_index": 1},

        # Valid eighth note candidate attaching ledger line IDs through a valid quarter_component_id
        {"candidate_id": "e2", "symbol_type": "eighth_note_candidate", "quarter_component_id": "q8", "staff_position_index": -2, "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "q8", "symbol_type": "quarter_note_candidate", "staff_position_index": -2, "bbox": [200, 200, 210, 210], "page_index": 1, "system_index": 1, "staff_index": 1},
        {"candidate_id": "l13", "symbol_type": "ledger_line_candidate", "staff_position_index": -2, "bbox": [198, 205, 212, 207], "page_index": 1, "system_index": 1, "staff_index": 1},
    ]

    map_ledger_lines_to_note_candidates(outcomes)

    for cand in outcomes:
        st_type = cand.get("symbol_type")
        if st_type and "note" in st_type:
            # Only q7, w1, h1, e2, and q8 should have attachments
            if cand.get("candidate_id") == "q7":
                assert cand.get("attached_ledger_line_candidate_ids") == ["l10", "l9"]
            elif cand.get("candidate_id") == "w1":
                assert cand.get("attached_ledger_line_candidate_ids") == ["l11"]
            elif cand.get("candidate_id") == "h1":
                assert cand.get("attached_ledger_line_candidate_ids") == ["l12"]
            elif cand.get("candidate_id") == "e2":
                assert cand.get("attached_ledger_line_candidate_ids") == ["l13"]
            elif cand.get("candidate_id") == "q8":
                assert cand.get("attached_ledger_line_candidate_ids") == ["l13"]
            else:
                assert "attached_ledger_line_candidate_ids" not in cand

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
    assert "assumed_treble_pitch" not in cand1

    cand2 = whole_notes[1]
    assert cand2["staff_position_index"] == 4
    assert "assumed_treble_pitch" not in cand2

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

def test_map_clef_resolved_staff_pitch():
    from score2gp.whole_note_recogniser import map_clef_resolved_staff_pitch

    outcomes = [
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 4}, # 0: B4 inside staff
        {"symbol_type": "quarter_note_candidate", "staff_position_index": -1}, # 1: G5 above staff, 0 ledgers, no attached field
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 9, "attached_ledger_line_candidate_ids": []}, # 2: D4 below staff, 0 ledgers, empty list
        {"symbol_type": "quarter_note_candidate", "staff_position_index": -2, "attached_ledger_line_candidate_ids": ["l1"]}, # 3: A5, 1 ledger
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 10, "attached_ledger_line_candidate_ids": ["l2"]}, # 4: C4, 1 ledger
        {"symbol_type": "quarter_note_candidate", "staff_position_index": -4, "attached_ledger_line_candidate_ids": ["l1", "l2"]}, # 5: C6, 2 ledgers
        {"symbol_type": "quarter_note_candidate", "staff_position_index": -2}, # 6: missing ledger -> fail
        {"symbol_type": "quarter_note_candidate", "staff_position_index": -2, "attached_ledger_line_candidate_ids": ["l1", "l2"]}, # 7: ambiguous (too many) -> fail
        {"symbol_type": "ledger_line_candidate", "staff_position_index": 4}, # 8: ignore non-notes
        {"symbol_type": "quarter_note_candidate", "staff_position_index": None}, # 9: malformed
        {"symbol_type": "quarter_note_candidate", "staff_position_index": -8}, # 10: out of mapped bounds
        {"symbol_type": "quarter_note_candidate", "staff_position_index": -1, "attached_ledger_line_candidate_ids": ["l1"]}, # 11: 0 ledger required but 1 given -> fail
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 9, "attached_ledger_line_candidate_ids": ["l2"]}, # 12: 0 ledger required but 1 given -> fail
        {"symbol_type": "quarter_note_candidate", "staff_position_index": -1, "attached_ledger_line_candidate_ids": "malformed"}, # 13: 0 ledger required but malformed -> fail
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 9, "attached_ledger_line_candidate_ids": "malformed"}, # 14: 0 ledger required but malformed -> fail
        {"symbol_type": "quarter_note_candidate", "staff_position_index": 4, "attached_ledger_line_candidate_ids": ["l1"]}, # 15: inside staff ignores attached ledgers
    ]

    # Test wrong clef
    map_clef_resolved_staff_pitch(outcomes, explicit_clef="bass")
    for cand in outcomes:
        assert "clef_resolved_staff_pitch" not in cand

    # Test no clef
    map_clef_resolved_staff_pitch(outcomes, explicit_clef=None)
    for cand in outcomes:
        assert "clef_resolved_staff_pitch" not in cand

    # Test valid clef
    map_clef_resolved_staff_pitch(outcomes, explicit_clef="treble")

    assert outcomes[0].get("clef_resolved_staff_pitch") == "B4"
    assert outcomes[1].get("clef_resolved_staff_pitch") == "G5"
    assert outcomes[2].get("clef_resolved_staff_pitch") == "D4"
    assert outcomes[3].get("clef_resolved_staff_pitch") == "A5"
    assert outcomes[4].get("clef_resolved_staff_pitch") == "C4"
    assert outcomes[5].get("clef_resolved_staff_pitch") == "C6"
    assert "clef_resolved_staff_pitch" not in outcomes[6]
    assert "clef_resolved_staff_pitch" not in outcomes[7]
    assert "clef_resolved_staff_pitch" not in outcomes[8]
    assert "clef_resolved_staff_pitch" not in outcomes[9]
    assert "clef_resolved_staff_pitch" not in outcomes[10]
    assert "clef_resolved_staff_pitch" not in outcomes[11]
    assert "clef_resolved_staff_pitch" not in outcomes[12]
    assert "clef_resolved_staff_pitch" not in outcomes[13]
    assert "clef_resolved_staff_pitch" not in outcomes[14]
    assert outcomes[15].get("clef_resolved_staff_pitch") == "B4"

def test_map_clef_resolved_staff_pitch_policy():
    from score2gp.whole_note_recogniser import map_clef_resolved_staff_pitch

    outcomes = [
        # Staff 1: exactly 1 valid treble clef
        {"symbol_type": "treble_clef_candidate", "candidate_id": "c1", "source": "diagnostic_candidate_evidence", "page_index": 1, "system_index": 1, "staff_index": 1},
        {"symbol_type": "quarter_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": 4}, # 1: mapped (B4)

        # Staff 2: 0 treble clefs
        {"symbol_type": "quarter_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 2, "staff_position_index": 4}, # 2: not mapped

        # Staff 3: multiple treble clefs
        {"symbol_type": "treble_clef_candidate", "candidate_id": "c2", "source": "raster_diagnostic_candidate_evidence", "page_index": 1, "system_index": 2, "staff_index": 1},
        {"symbol_type": "treble_clef_candidate", "candidate_id": "c3", "source": "raster_diagnostic_candidate_evidence", "page_index": 1, "system_index": 2, "staff_index": 1},
        {"symbol_type": "quarter_note_candidate", "page_index": 1, "system_index": 2, "staff_index": 1, "staff_position_index": 4}, # 5: not mapped

        # Staff 4: malformed clef evidence (missing staff_index)
        {"symbol_type": "treble_clef_candidate", "candidate_id": "c4", "source": "diagnostic_candidate_evidence", "page_index": 2, "system_index": 1},
        {"symbol_type": "quarter_note_candidate", "page_index": 2, "system_index": 1, "staff_index": 1, "staff_position_index": 4}, # 7: not mapped

        # Staff 5: missing candidate_id
        {"symbol_type": "treble_clef_candidate", "source": "diagnostic_candidate_evidence", "page_index": 2, "system_index": 2, "staff_index": 1},
        {"symbol_type": "quarter_note_candidate", "page_index": 2, "system_index": 2, "staff_index": 1, "staff_position_index": 4}, # 9: not mapped

        # Staff 6: empty candidate_id
        {"symbol_type": "treble_clef_candidate", "candidate_id": "", "source": "diagnostic_candidate_evidence", "page_index": 2, "system_index": 3, "staff_index": 1},
        {"symbol_type": "quarter_note_candidate", "page_index": 2, "system_index": 3, "staff_index": 1, "staff_position_index": 4}, # 11: not mapped

        # Staff 7: boolean indexes
        {"symbol_type": "treble_clef_candidate", "candidate_id": "c5", "source": "diagnostic_candidate_evidence", "page_index": True, "system_index": 1, "staff_index": 1},
        {"symbol_type": "quarter_note_candidate", "page_index": True, "system_index": 1, "staff_index": 1, "staff_position_index": 4}, # 13: not mapped

        # Staff 8: missing/invalid source
        {"symbol_type": "treble_clef_candidate", "candidate_id": "c6", "source": "some_other_source", "page_index": 3, "system_index": 1, "staff_index": 1},
        {"symbol_type": "quarter_note_candidate", "page_index": 3, "system_index": 1, "staff_index": 1, "staff_position_index": 4}, # 15: not mapped

        # Staff 1: malformed note staff lookup
        {"symbol_type": "quarter_note_candidate", "page_index": 1, "system_index": True, "staff_index": 1, "staff_position_index": 4}, # 16: not mapped

        # Staff 1: out-of-staff mapped (0 ledgers needed)
        {"symbol_type": "quarter_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": -1}, # 17: mapped (G5)

        # Staff 1: out-of-staff mapped (1 ledger needed)
        {"symbol_type": "quarter_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": -2, "attached_ledger_line_candidate_ids": ["l1"]}, # 18: mapped (A5)

        # Staff 1: out-of-staff missing ledger
        {"symbol_type": "quarter_note_candidate", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": -2}, # 19: not mapped
    ]

    map_clef_resolved_staff_pitch(outcomes)

    assert outcomes[1].get("clef_resolved_staff_pitch") == "B4"
    assert "clef_resolved_staff_pitch" not in outcomes[2]
    assert "clef_resolved_staff_pitch" not in outcomes[5]
    assert "clef_resolved_staff_pitch" not in outcomes[7]
    assert "clef_resolved_staff_pitch" not in outcomes[9]
    assert "clef_resolved_staff_pitch" not in outcomes[11]
    assert "clef_resolved_staff_pitch" not in outcomes[13]
    assert "clef_resolved_staff_pitch" not in outcomes[15]
    assert "clef_resolved_staff_pitch" not in outcomes[16]
    assert outcomes[17].get("clef_resolved_staff_pitch") == "G5"
    assert outcomes[18].get("clef_resolved_staff_pitch") == "A5"
    assert "clef_resolved_staff_pitch" not in outcomes[19]

def test_extract_treble_clef_candidate_evidence_fails_closed():
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    # Provide dummy diagnostic data
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1}}]
    # Should fail closed and return empty since no deterministic evidence exists yet
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1)
    assert cands == []

def test_map_treble_clef_candidates_to_read_only_outcomes():
    from score2gp.whole_note_recogniser import map_treble_clef_candidates_to_read_only_outcomes

    locations = [
        {
            "candidate_id": "treble_001",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [10.0, 20.0, 30.0, 40.0]
        }
    ]

    outcomes = map_treble_clef_candidates_to_read_only_outcomes(locations)
    assert len(outcomes) == 1
    assert outcomes[0]["symbol_type"] == "treble_clef_candidate"
    assert outcomes[0]["candidate_id"] == "treble_001"
    assert outcomes[0]["page_index"] == 1
    assert outcomes[0]["system_index"] == 1
    assert outcomes[0]["staff_index"] == 1
    assert outcomes[0]["bbox"] == [10.0, 20.0, 30.0, 40.0]
    assert outcomes[0]["source"] == "diagnostic_candidate_evidence"


def test_map_treble_clef_candidates_to_read_only_outcomes_fails_closed():
    from score2gp.whole_note_recogniser import map_treble_clef_candidates_to_read_only_outcomes

    locations = [
        # Valid
        {
            "candidate_id": "treble_001",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [10.0, 20.0, 30.0, 40.0]
        },
        # Missing candidate_id
        {
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [10.0, 20.0, 30.0, 40.0]
        },
        # Empty candidate_id
        {
            "candidate_id": "",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [10.0, 20.0, 30.0, 40.0]
        },
        # Missing page_index
        {
            "candidate_id": "treble_002",
            "system_index": 1,
            "staff_index": 1,
            "bbox": [10.0, 20.0, 30.0, 40.0]
        },
        # Malformed non-integer page_index
        {
            "candidate_id": "treble_003",
            "page_index": "1",
            "system_index": 1,
            "staff_index": 1,
            "bbox": [10.0, 20.0, 30.0, 40.0]
        },
        # Missing system_index
        {
            "candidate_id": "treble_004",
            "page_index": 1,
            "staff_index": 1,
            "bbox": [10.0, 20.0, 30.0, 40.0]
        },
        # Missing bbox
        {
            "candidate_id": "treble_005",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1
        },
        # Malformed bbox
        {
            "candidate_id": "treble_006",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": "invalid"
        },
        # Wrong length bbox
        {
            "candidate_id": "treble_007",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [10.0, 20.0, 30.0]
        },
        # Non-numeric bbox
        {
            "candidate_id": "treble_008",
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "bbox": [10.0, "x", 30.0, 40.0]
        },
        # Duplicate candidate_id
        {
            "candidate_id": "treble_001",
            "page_index": 2,
            "system_index": 2,
            "staff_index": 2,
            "bbox": [50.0, 60.0, 70.0, 80.0]
        }
    ]

    outcomes = map_treble_clef_candidates_to_read_only_outcomes(locations)
    assert len(outcomes) == 1
    assert outcomes[0]["candidate_id"] == "treble_001"
    assert outcomes[0]["page_index"] == 1
    assert outcomes[0]["system_index"] == 1
    assert outcomes[0]["staff_index"] == 1
    assert outcomes[0]["bbox"] == [10.0, 20.0, 30.0, 40.0]


def test_clef_resolved_pitch_coverage_report_unit():
    from score2gp.whole_note_recogniser import build_clef_resolved_pitch_coverage_report

    outcomes = [
        # 1. Valid treble clef
        {"symbol_type": "treble_clef_candidate", "candidate_id": "clef_1", "page_index": 1, "system_index": 1, "staff_index": 1, "source": "raster_diagnostic_candidate_evidence"},
        # 2. Ambiguous clefs (two on same staff)
        {"symbol_type": "treble_clef_candidate", "candidate_id": "clef_2", "page_index": 1, "system_index": 1, "staff_index": 2, "source": "diagnostic_candidate_evidence"},
        {"symbol_type": "treble_clef_candidate", "candidate_id": "clef_3", "page_index": 1, "system_index": 1, "staff_index": 2, "source": "raster_diagnostic_candidate_evidence"},

        # In scope valid note with pitch (in staff)
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n1", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": 4, "clef_resolved_staff_pitch": "B4"},
        # In scope valid note with pitch (out of staff)
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n2", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": 10, "clef_resolved_staff_pitch": "G3"},
        # Skipped due to missing ledger line support (no pitch mapped, valid clef)
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n3", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": 10},
        # Skipped due to missing clef (staff 3)
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n4", "page_index": 1, "system_index": 1, "staff_index": 3, "staff_position_index": 4},
        # Skipped due to ambiguous clef (staff 2)
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n5", "page_index": 1, "system_index": 1, "staff_index": 2, "staff_position_index": 4},
        # Skipped due to malformed staff position (missing)
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n6", "page_index": 1, "system_index": 1, "staff_index": 1},
        # Skipped due to malformed staff association (missing system_index)
        {"symbol_type": "eighth_note_candidate", "candidate_id": "n7", "page_index": 1, "staff_index": 1, "staff_position_index": 4},
    ]

    report = build_clef_resolved_pitch_coverage_report(outcomes)

    assert report["total_note_candidates_in_scope"] == 7
    assert report["note_candidates_with_staff_position_index"] == 6 # n6 missing
    assert report["note_candidates_on_staves_with_valid_clef"] == 4 # n1, n2, n3, n6 (n7 has no valid staff to map to clef)
    assert report["note_candidates_with_clef_resolved_staff_pitch"] == 2
    assert report["in_staff_mapped_notes"] == 1
    assert report["out_of_staff_mapped_notes"] == 1
    assert report["skipped_missing_required_ledger_support"] == 1
    assert report["skipped_clef_missing"] == 1
    assert report["skipped_clef_ambiguous"] == 1
    assert report["skipped_staff_association_malformed"] == 1
    assert report["skipped_staff_position_malformed"] == 1

    sample_ids = [d["candidate_id"] for d in report["sample_diagnostics"]]
    assert "n3" in sample_ids
    assert "n4" in sample_ids
    assert "n5" in sample_ids
    assert "n6" in sample_ids
    assert "n7" in sample_ids

def test_clef_resolved_pitch_coverage_report_malformed_outcomes():
    from score2gp.whole_note_recogniser import build_clef_resolved_pitch_coverage_report

    # Test non-list inputs
    assert build_clef_resolved_pitch_coverage_report(None)["total_note_candidates_in_scope"] == 0
    assert build_clef_resolved_pitch_coverage_report("invalid")["total_note_candidates_in_scope"] == 0
    assert build_clef_resolved_pitch_coverage_report({})["total_note_candidates_in_scope"] == 0

    # Test empty list
    assert build_clef_resolved_pitch_coverage_report([])["total_note_candidates_in_scope"] == 0

    # Test list with non-dict elements and missing attributes
    outcomes = [
        "not_a_dict",
        None,
        123,
        {"symbol_type": "treble_clef_candidate", "candidate_id": "clef_1", "page_index": 1, "system_index": 1, "staff_index": 1, "source": "diagnostic_candidate_evidence"},
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n1", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": 4, "clef_resolved_staff_pitch": "B4"}
    ]

    report = build_clef_resolved_pitch_coverage_report(outcomes)
    assert report["total_note_candidates_in_scope"] == 1
    assert report["note_candidates_with_clef_resolved_staff_pitch"] == 1


def test_clef_resolved_pitch_coverage_report_out_of_range_positions():
    from score2gp.whole_note_recogniser import build_clef_resolved_pitch_coverage_report

    outcomes = [
        {"symbol_type": "treble_clef_candidate", "candidate_id": "clef_1", "page_index": 1, "system_index": 1, "staff_index": 1, "source": "diagnostic_candidate_evidence"},

        # Out of range position: -8
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n_out_1", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": -8},
        # Out of range position: 16
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n_out_2", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": 16},
        # Extreme position
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n_out_3", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": 100},
        
        # Valid missing ledger line support: -7
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n_ledger_1", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": -7},
        # Valid missing ledger line support: 15
        {"symbol_type": "quarter_note_candidate", "candidate_id": "n_ledger_2", "page_index": 1, "system_index": 1, "staff_index": 1, "staff_position_index": 15},
    ]

    report = build_clef_resolved_pitch_coverage_report(outcomes)

    assert report["total_note_candidates_in_scope"] == 5
    assert report["note_candidates_with_staff_position_index"] == 5
    assert report["note_candidates_on_staves_with_valid_clef"] == 5
    assert report["note_candidates_with_clef_resolved_staff_pitch"] == 0
    assert report["skipped_missing_required_ledger_support"] == 2 # Only -7 and 15

    # Check reasons in sample diagnostics
    sample_reasons = {d["candidate_id"]: d["skip_reason"] for d in report["sample_diagnostics"]}
    assert sample_reasons["n_out_1"] == "pitch_out_of_range_or_unsupported"
    assert sample_reasons["n_out_2"] == "pitch_out_of_range_or_unsupported"
    assert sample_reasons["n_out_3"] == "pitch_out_of_range_or_unsupported"
    assert sample_reasons["n_ledger_1"] == "missing_required_ledger_support"
    assert sample_reasons["n_ledger_2"] == "missing_required_ledger_support"
