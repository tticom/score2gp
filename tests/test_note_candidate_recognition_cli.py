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
    assert len(outcomes) == 2

    for outcome in outcomes:
        assert outcome["symbol_type"] == "whole_note_candidate"
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "bbox" in outcome
        assert "page_index" in outcome

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

    for outcome in half_notes:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "bbox" in outcome
        assert "page_index" in outcome

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

    for outcome in quarter_notes:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "bbox" in outcome
        assert "page_index" in outcome

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
