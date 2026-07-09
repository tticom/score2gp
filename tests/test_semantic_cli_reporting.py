import json
import subprocess
import sys
import os
from pathlib import Path

def _get_subprocess_env():
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"
    return env

def test_note_candidate_recognition_cli_exposes_semantic_candidates():
    # We use dense_margin which has a clef
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_dense_margin.pdf")
    assert pdf_path.exists()

    cmd = [
        sys.executable, "-m", "score2gp.cli", "note-candidate-recognition",
        "--pdf", str(pdf_path),
        "--json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())
    output = json.loads(result.stdout)

    assert "semantic_candidates" in output, "semantic_candidates key is missing from note-candidate-recognition CLI output"
    semantic_cands = output["semantic_candidates"]
    assert len(semantic_cands) >= 1

    staff_cand = semantic_cands[0]
    assert "page_index" in staff_cand
    assert "system_index" in staff_cand
    assert "staff_index" in staff_cand
    assert "logical_clef" in staff_cand
    assert "quarter_rests" in staff_cand

    clef = staff_cand["logical_clef"]
    assert clef["status"] == "logical_clef_candidate"
    assert clef["clef_kind"] == "unknown"  # dense_margin has ambiguous left margin clef

def test_inspect_pdf_cli_exposes_semantic_candidates(tmp_path):
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_dense_margin.pdf")
    out_json = tmp_path / "inspect_pdf.json"

    cmd = [
        sys.executable, "-m", "score2gp.cli", "inspect-pdf",
        str(pdf_path),
        "--out", str(tmp_path)
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())

    assert out_json.exists()
    output = json.loads(out_json.read_text(encoding="utf-8"))

    assert "pages" in output
    assert len(output["pages"]) > 0

    page_info = output["pages"][0]
    assert "semantic_candidates" in page_info, "semantic_candidates missing from inspect-pdf page_info"
    semantic_cands = page_info["semantic_candidates"]
    assert len(semantic_cands) >= 1

    staff_cand = semantic_cands[0]
    assert "logical_clef" in staff_cand
    assert "quarter_rests" in staff_cand

def test_reporting_script_exposes_semantic_candidates():
    script_path = Path("scripts/note_candidate_recognition_report.py")
    pdf_path = Path("tests/fixtures/pdf/generated_standard_staff_dense_margin.pdf")
    assert script_path.exists()

    cmd = [
        sys.executable, str(script_path),
        "--pdf", str(pdf_path),
        "--json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())
    output = json.loads(result.stdout)

    assert "semantic_candidates" in output

def test_legacy_scoreir_and_playable_output_unchanged(tmp_path):
    # Verify convert runs successfully and produces the expected GP package
    pdf_path = Path("tests/fixtures/pdf/generated_tiny_tab.pdf")
    musicxml_path = Path("tests/fixtures/musicxml/generated_tiny_tab.musicxml")
    out_gp = tmp_path / "output.gp"
    workdir = tmp_path / "workdir"
    json_report = tmp_path / "report.json"

    cmd = [
        sys.executable, "-m", "score2gp.cli", "convert",
        "--pdf", str(pdf_path),
        "--musicxml", str(musicxml_path),
        "--out", str(out_gp),
        "--work-dir", str(workdir),
        "--json-report", str(json_report)
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())
    assert out_gp.exists()
    assert json_report.exists()

    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert report["status"] == "success"

    # Also verify that no semantic candidate fields leaked into the generated GP summary
    summary_str = json.dumps(report).lower()
    for forbidden in ["quarter_rest_candidate", "logical_clef_candidate"]:
        assert forbidden not in summary_str

def test_semantic_candidates_fail_closed_on_standard_fixtures():
    # List of public standard staff fixtures that contain noise, blank staves,
    # wide curves, or complex clusters (overlapping primitives).
    fixtures = [
        "complex_cluster",
        "sparse",
        "wide_curves",
        "negative_tab",
        "negative_blank",
        "negative_noise"
    ]

    for f in fixtures:
        pdf_path = Path(f"tests/fixtures/pdf/generated_standard_staff_{f}.pdf")
        assert pdf_path.exists()

        cmd = [
            sys.executable, "-m", "score2gp.cli", "note-candidate-recognition",
            "--pdf", str(pdf_path),
            "--json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())
        output = json.loads(result.stdout)

        assert "semantic_candidates" in output
        for staff in output["semantic_candidates"]:
            # Confirm that no quarter rests are extracted (fail-closed on these staves)
            assert len(staff["quarter_rests"]) == 0, f"Expected 0 quarter rests for {f}, found {len(staff['quarter_rests'])}"

            # Confirm that no treble clef was resolved (either unknown or no_candidate)
            clef = staff["logical_clef"]
            assert clef["clef_kind"] in [None, "unknown"], f"Expected clef_kind to be None/unknown for {f}, found {clef['clef_kind']}"

def test_semantic_candidates_fail_closed_on_whole_half_rests():
    # Verify simple public fixtures with whole/half rests do not produce quarter rests
    fixtures = [
        "WholeNoteRest.pdf",
        "HalfNotes.pdf"
    ]

    for f in fixtures:
        pdf_path = Path(f"fixtures/public/generated_simple/simple/{f}")
        assert pdf_path.exists()

        cmd = [
            sys.executable, "-m", "score2gp.cli", "note-candidate-recognition",
            "--pdf", str(pdf_path),
            "--json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=_get_subprocess_env())
        output = json.loads(result.stdout)

        assert "semantic_candidates" in output
        for staff in output["semantic_candidates"]:
            assert len(staff["quarter_rests"]) == 0, f"Expected 0 quarter rests for {f}, found {len(staff['quarter_rests'])}"
            if f == "WholeNoteRest.pdf":
                assert len(staff.get("whole_rests", [])) == 1, f"Expected 1 whole rest for {f}, found {len(staff.get('whole_rests', []))}"
                assert len(staff.get("half_rests", [])) == 0, f"Expected 0 half rests for {f}, found {len(staff.get('half_rests', []))}"
            elif f == "HalfNotes.pdf":
                assert len(staff.get("whole_rests", [])) == 0, f"Expected 0 whole rests for {f}, found {len(staff.get('whole_rests', []))}"
                assert len(staff.get("half_rests", [])) == 0, f"Expected 0 half rests for {f}, found {len(staff.get('half_rests', []))}"
