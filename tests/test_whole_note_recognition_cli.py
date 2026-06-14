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

def test_installed_cli_whole_note_recognition_report(tmp_path):
    # Test that the installed CLI path works directly
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "whole-note-recognition", "--pdf", str(fixture_path), "--json"]
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

def test_installed_cli_whole_note_recognition_nested_path_sanitisation(tmp_path):
    import shutil
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_whole_note.pdf")

    # Create a nested path in tmp_path
    nested_dir = tmp_path / "deeply" / "nested" / "private_lookalike"
    nested_dir.mkdir(parents=True)
    custom_pdf_path = nested_dir / "custom_test_file.pdf"
    shutil.copy(fixture_path, custom_pdf_path)

    cmd = [sys.executable, "-m", "score2gp.cli", "whole-note-recognition", "--pdf", str(custom_pdf_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)

    assert output["source"] == "custom_test_file.pdf"
    assert "tmp_path" not in output["source"]
    assert "private_lookalike" not in output["source"]
    assert "deeply" not in output["source"]

def test_installed_cli_recognition_report_with_half_notes(tmp_path):
    # Test that the installed CLI path works and exposes half notes
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_half_note.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "whole-note-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert output["source"] == fixture_path.name

    outcomes = output["read_only_recognition_outcomes"]
    # The half note fixture may only have half notes or both, but we know it has half notes
    half_notes = [o for o in outcomes if o["symbol_type"] == "half_note_candidate"]
    assert len(half_notes) == 2

    for outcome in half_notes:
        assert outcome["source"] == "diagnostic_candidate_evidence"
        assert "candidate_id" in outcome
        assert "bbox" in outcome
        assert "page_index" in outcome

def test_installed_cli_whole_note_recognition_no_x_aligned_clusters(tmp_path):
    # Test that the legacy CLI path DOES NOT expose x_aligned_cluster_candidates
    fixture_path = Path("tests/fixtures/pdf/generated_standard_staff_complex_cluster.pdf")

    cmd = [sys.executable, "-m", "score2gp.cli", "whole-note-recognition", "--pdf", str(fixture_path), "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    output = json.loads(result.stdout)
    assert output["source"] == fixture_path.name

    outcomes = output["read_only_recognition_outcomes"]
    x_aligned_clusters = [o for o in outcomes if o["symbol_type"] == "x_aligned_cluster_candidate"]
    assert len(x_aligned_clusters) == 0

    left_margin_candidates = [o for o in outcomes if o["symbol_type"] == "left_margin_candidate"]
    assert len(left_margin_candidates) == 0
