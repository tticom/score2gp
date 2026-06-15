import json
import subprocess
import os
import sys
from pathlib import Path

def _get_subprocess_env():
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"
    return env

def test_installed_cli_note_candidate_recognition_report(tmp_path):
    # Test that the new generic installed CLI path works
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert output["source"] == fixture_path.name
    assert output["recognition_mode"] == "read_only_diagnostic_derived"

    outcomes = output["read_only_recognition_outcomes"]
    whole_notes = [o for o in outcomes if o["symbol_type"] == "whole_note_candidate"]
    assert len(whole_notes) == 2

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

    for outcome in whole_notes:
        assert outcome["symbol_type"] == "whole_note_candidate"
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "bbox" in outcome
        assert "page_index" in outcome
        assert outcome.get("system_index") is not None
        assert outcome.get("staff_index") is not None

def test_installed_cli_note_candidate_recognition_with_half_notes(tmp_path):
    # Test that the generic CLI path exposes half notes properly
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_half_note.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert output["source"] == fixture_path.name

    outcomes = output["read_only_recognition_outcomes"]
    half_notes = [o for o in outcomes if o["symbol_type"] == "half_note_candidate"]
    assert len(half_notes) == 2

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

    for outcome in half_notes:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "bbox" in outcome
        assert "page_index" in outcome
        assert outcome.get("system_index") is not None
        assert outcome.get("staff_index") is not None

def test_installed_cli_note_candidate_recognition_with_quarter_notes(tmp_path):
    # Test that the generic CLI path exposes quarter notes properly
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_quarter_note.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert output["source"] == fixture_path.name

    outcomes = output["read_only_recognition_outcomes"]
    quarter_notes = [o for o in outcomes if o["symbol_type"] == "quarter_note_candidate"]
    assert len(quarter_notes) == 2

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

    for outcome in quarter_notes:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "bbox" in outcome
        assert "page_index" in outcome
        assert outcome.get("system_index") is not None
        assert outcome.get("staff_index") is not None

def test_installed_cli_note_candidate_recognition_with_x_aligned_clusters(tmp_path):
    # Test that the generic CLI path exposes x_aligned_cluster_candidates properly
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_complex_cluster.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert output["source"] == fixture_path.name

    outcomes = output["read_only_recognition_outcomes"]
    x_aligned_clusters = [o for o in outcomes if o["symbol_type"] == "x_aligned_cluster_candidate"]

    # We expect 5 clusters based on expected_diagnostics_complex_cluster.json
    assert len(x_aligned_clusters) == 5

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

    for outcome in x_aligned_clusters:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "page_index" in outcome
        assert "system_index" in outcome
        assert "staff_index" in outcome
        assert "x0" in outcome
        assert "x1" in outcome
        assert "primitive_count" in outcome
        assert "primitives" in outcome

def test_installed_cli_note_candidate_recognition_with_left_margin_candidates(tmp_path):
    # Test that the generic CLI path exposes left_margin_candidates properly
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_complex_cluster.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert output["source"] == fixture_path.name

    outcomes = output["read_only_recognition_outcomes"]
    left_margin_candidates = [o for o in outcomes if o["symbol_type"] == "left_margin_candidate"]

    # We expect 1 left margin candidate based on expected_diagnostics_complex_cluster.json
    assert len(left_margin_candidates) == 1

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

    for outcome in left_margin_candidates:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "page_index" in outcome
        assert "system_index" in outcome
        assert "staff_index" in outcome
        assert "x0" in outcome
        assert "y0" in outcome
        assert "x1" in outcome
        assert "y1" in outcome
        assert "kind" in outcome
        assert "font_name" in outcome
        assert "font_size" in outcome

def test_installed_cli_note_candidate_recognition_with_flag_beam_candidates(tmp_path):
    # Test that the generic CLI path exposes flag_candidate and beam_candidate properly
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_complex_cluster.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert output["source"] == fixture_path.name

    outcomes = output["read_only_recognition_outcomes"]
    flags = [o for o in outcomes if o["symbol_type"] == "flag_candidate"]
    beams = [o for o in outcomes if o["symbol_type"] == "beam_candidate"]

    # We expect some beams based on expected_diagnostics_complex_cluster.json
    assert len(beams) > 0

    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]
    assert len(eighth_notes) == 0

    for outcome in flags:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert outcome["page_index"] == 1
        assert outcome["system_index"] == 1
        assert outcome["staff_index"] == 1
        assert "bbox" in outcome
        assert "primitive_kind" in outcome
        assert "width" in outcome
        assert "height" in outcome

    for outcome in beams:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert outcome["page_index"] == 1
        assert outcome["system_index"] == 1
        assert outcome["staff_index"] == 1
        assert "bbox" in outcome
        assert "primitive_kind" in outcome
        assert "width" in outcome
        assert "height" in outcome

def test_installed_cli_note_candidate_recognition_with_eighth_notes(tmp_path):
    # Test that the generic CLI path exposes eighth notes properly
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_eighth_notes.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert output["source"] == fixture_path.name

    outcomes = output["read_only_recognition_outcomes"]
    eighth_notes = [o for o in outcomes if o["symbol_type"] == "eighth_note_candidate"]

    assert len(eighth_notes) >= 3

    for outcome in eighth_notes:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "page_index" in outcome
        assert "system_index" in outcome
        assert "staff_index" in outcome
        assert "quarter_component_id" in outcome
        assert "modifier_component_id" in outcome

def test_installed_cli_note_candidate_recognition_staff_geometry_exposure(tmp_path):
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert "staff_geometry" in output

    staff_geometry = output["staff_geometry"]
    assert isinstance(staff_geometry, list)
    assert len(staff_geometry) > 0

    outcomes = output["read_only_recognition_outcomes"]
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

def test_installed_cli_note_candidate_recognition_assume_treble_clef_default_disabled(tmp_path):
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    outcomes = output["read_only_recognition_outcomes"]
    whole_notes = [o for o in outcomes if o["symbol_type"] == "whole_note_candidate"]
    assert len(whole_notes) == 2
    for cand in outcomes:
        assert "assumed_treble_pitch" not in cand

def test_installed_cli_note_candidate_recognition_assume_treble_clef_enabled(tmp_path):
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")
    cmd = [sys.executable, "-m", "score2gp.cli", "note-candidate-recognition", "--pdf", str(fixture_path), "--json", "--assume-treble-clef"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    outcomes = output["read_only_recognition_outcomes"]
    whole_notes = [o for o in outcomes if o["symbol_type"] == "whole_note_candidate"]
    assert len(whole_notes) == 2

    cand1 = whole_notes[0]
    assert cand1["staff_position_index"] == 2
    assert cand1["assumed_treble_pitch"] == "D5"

    cand2 = whole_notes[1]
    assert cand2["staff_position_index"] == 4
    assert cand2["assumed_treble_pitch"] == "B4"
