import json
import subprocess
import sys
import os
import shutil
from pathlib import Path

def _get_subprocess_env():
    env = os.environ.copy()
    src_path = str(Path.cwd() / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"
    return env

def test_candidate_gate_isolation(tmp_path):
    # Public fixtures
    pdf_path = Path("tests/fixtures/pdf/generated_tiny_tab.pdf")
    musicxml_path = Path("tests/fixtures/musicxml/generated_tiny_tab.musicxml")
    assert pdf_path.exists()
    assert musicxml_path.exists()

    # Output paths
    out_gp = tmp_path / "output.gp"
    workdir = tmp_path / "workdir"
    json_report = tmp_path / "report.json"

    # Command to run full PDF-to-GP conversion
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

    # Load conversion report and check for any leakage of diagnostic candidate keywords
    report = json.loads(json_report.read_text(encoding="utf-8"))

    # We clean the report representation to exclude path strings (which may contain the user's workspace path)
    # to focus strictly on structural keys/values.
    # Let's check report structure or keys/values directly instead of raw string search, or remove path fields.
    if "diagnostics_paths" in report:
        del report["diagnostics_paths"]
    if "output_path" in report:
        del report["output_path"]
    if "work_dir" in report:
        del report["work_dir"]

    report_str = json.dumps(report).lower()
    for forbidden in ["quarter_rest_candidate", "logical_clef_candidate", "semantic_candidates", "whole_rest_candidate", "half_rest_candidate"]:
        assert forbidden not in report_str, f"Forbidden keyword '{forbidden}' leaked into JSON conversion report"

    # Load intermediate ScoreIR file if written to the work-dir
    scoreir_json = workdir / "scoreir.json"
    if scoreir_json.exists():
        scoreir_data = json.loads(scoreir_json.read_text(encoding="utf-8"))
        scoreir_str = json.dumps(scoreir_data).lower()
        for forbidden in ["quarter_rest_candidate", "logical_clef_candidate", "semantic_candidates", "logical_clef", "quarter_rests", "whole_rests", "half_rests", "whole_rest_candidate", "half_rest_candidate"]:
            assert forbidden not in scoreir_str, f"Forbidden keyword '{forbidden}' leaked into intermediate ScoreIR JSON"

    # Verify that the generated GP package has no traces of semantic candidate metadata.
    # GP7 package is a zip container containing gpif.xml or similar files.
    # Let's extract and search inside the XML/text files for forbidden semantic terms.
    extract_dir = tmp_path / "extracted_gp"
    shutil.unpack_archive(str(out_gp), str(extract_dir), "zip")

    for p in extract_dir.rglob("*"):
        if p.is_file() and p.suffix in [".xml", ".json", ".txt"]:
            content = p.read_text(encoding="utf-8", errors="ignore").lower()
            for forbidden in ["quarter_rest_candidate", "logical_clef_candidate", "semantic_candidates", "whole_rest_candidate", "half_rest_candidate"]:
                assert forbidden not in content, f"Forbidden keyword '{forbidden}' leaked into GP package file: {p.name}"

def test_scoreir_identical_regardless_of_diagnostics(tmp_path):
    # Proves that the presence/evaluation of semantic candidates does not alter
    # ScoreIR output, by comparing a baseline build with a diagnostic-loaded run.
    from score2gp.build_ir import build_ir_from_files
    from score2gp.ir import validate_score_ir_file

    musicxml_path = Path("tests/fixtures/musicxml/tiny_single_bar.musicxml")
    tabraw_path = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")
    assert musicxml_path.exists()
    assert tabraw_path.exists()

    # Load and build baseline ScoreIR
    baseline_ir_path = tmp_path / "baseline.ir.json"
    score_baseline = build_ir_from_files(musicxml_path, tabraw_path, baseline_ir_path)

    # Validate baseline
    val_baseline, errors_baseline = validate_score_ir_file(baseline_ir_path)
    assert errors_baseline == []

    # Verify baseline contents are pristine
    baseline_str = baseline_ir_path.read_text(encoding="utf-8").lower()
    for forbidden in ["quarter_rest_candidate", "logical_clef_candidate", "semantic_candidates", "whole_rest_candidate", "half_rest_candidate"]:
        assert forbidden not in baseline_str
