#!/usr/bin/env python3

"""

scripts/corpus_harness.py



Commandable corpus harness for the Runtime Provenance Baseline.

Iterates through private corpus inputs, executes the 'score2gp convert' CLI,

and generates an ignored RuntimeProvenanceRecord for each.

"""



import argparse

import hashlib

import json

import shutil

import subprocess

import sys

from pathlib import Path

from typing import Any, Dict, List, Optional



PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT / "src"))



import score2gp

from score2gp.runtime_provenance import RuntimeProvenanceRecord



def get_git_sha() -> str:

    try:

        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()

    except Exception:

        return "unknown"



def is_git_dirty() -> bool:

    try:

        status = subprocess.check_output(["git", "status", "--short"], cwd=PROJECT_ROOT, text=True).strip()

        return bool(status)

    except Exception:

        return True



def get_file_sha256(path: Path) -> Optional[str]:

    if not path.exists():

        return None

    sha256_hash = hashlib.sha256()

    with open(path, "rb") as f:

        for byte_block in iter(lambda: f.read(4096), b""):

            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()



def anonymize_name(path: Path) -> str:

    """Anonymize private input filenames to prevent private data leakage."""

    name = path.name.lower()

    if "derek" in name or "trucks" in name:

        return "private_input_1"

    if "caged" in name or "guitar tab creator" in name:

        return "private_input_2"

    for suffix in ["lesson-3", "lesson-4", "lesson-5", "lesson-6", "lesson-7", "melodic soloing"]:

        if suffix in name:

            safe_suffix = suffix.replace(" ", "_").replace("-", "_")

            return f"private_input_custom_{safe_suffix}"

    return "private_input_custom"



def resolve_score2gp_cmd() -> List[str]:
    """Finds the actual score2gp executable command list."""
    import shutil
    from pathlib import Path

    # Priority 1: Use the existing native WSL CLI entrypoint from the committed environment
    venv_bin = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "score2gp"
    if venv_bin.exists():
        return [str(venv_bin), "convert"]

    # Priority 2: native system executable (WSL/Linux PATH)
    score2gp_bin = shutil.which("score2gp")
    if score2gp_bin:
        return [score2gp_bin, "convert"]

    raise RuntimeError("Native score2gp CLI entrypoint not found. Ensure .venv is initialized.")



def run_pipeline_for_input(

    pdf_path: Path,

    musicxml_path: Optional[Path],

    output_base: Path,

) -> Dict[str, Any]:

    label = anonymize_name(pdf_path)

    out_dir = output_base / label

    out_dir.mkdir(parents=True, exist_ok=True)



    json_report_path = out_dir / "convert-report.json"

    gp_out_path = out_dir / "smoke.gp"



    # Construct command

    cmd = resolve_score2gp_cmd()

    cmd.extend(["--pdf", str(pdf_path)])

    if musicxml_path:

        cmd.extend(["--musicxml", str(musicxml_path)])



    # We pass the work dir and output path

    cmd.extend(["--work-dir", str(out_dir)])

    cmd.extend(["--out", str(gp_out_path)])

    cmd.extend(["--json-report", str(json_report_path)])



    # Run command

    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    exit_status = result.returncode



    # Read json report

    report_data = {}
    if json_report_path.exists():
        try:
            report_data = json.loads(json_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    cli_executable_path = cmd[0]
    if report_data:
        stage = report_data.get("stage", "unknown")
        child_python_executable_path = report_data.get("child_python_executable_path", "unknown")
        python_import_path = report_data.get("python_import_path", "unknown")
        mxl_info = report_data.get("musicxml_sidecar_info")
    else:
        stage = "runtime_probe_failed"
        child_python_executable_path = "unknown"
        python_import_path = "unknown"
        mxl_info = {"provenance": "absent"}

    refusal_code = report_data.get("refusal_code")
    output_written = report_data.get("output_written", False)
    summary_counts = report_data.get("summary_counts", {})

    classification = "pdf-tab-musicxml" if musicxml_path else "pdf-tab-only"

    structural_counts = {
        "bars": summary_counts.get("bar_count", "unknown"),
        "events": summary_counts.get("event_count", "unknown"),
        "source_rests": "unknown",
        "emitted_rests": "unknown",
        "warning_count": summary_counts.get("warning_count", "unknown"),
    }

    provenance = RuntimeProvenanceRecord(
        product_sha=get_git_sha(),
        is_dirty=is_git_dirty(),
        cli_executable_path=cli_executable_path,
        child_python_executable_path=child_python_executable_path,
        python_import_path=python_import_path,
        exact_command=cmd,
        input_classification=classification,
        musicxml_sidecar_info=mxl_info,
        output_report_path=str(json_report_path.resolve()),
        gp_output_path=str(gp_out_path.resolve()),
        exit_status=exit_status,
        output_written=output_written,

        stage=stage,

        refusal_code=refusal_code,

        structural_counts=structural_counts

    )



    provenance_path = out_dir / "provenance_record.json"

    provenance_path.write_text(provenance.model_dump_json(indent=2), encoding="utf-8")



    return {

        "input_label": label,

        "classification": classification,

        "exit_status": exit_status,

        "stage": stage,

        "refusal_code": refusal_code,

        "output_written": output_written,

        "stdout": result.stdout,

        "stderr": result.stderr,

    }



def main():

    parser = argparse.ArgumentParser(description="Commandable corpus harness for Runtime Provenance.")

    parser.add_argument("--pdf", type=Path, help="Path to a single private PDF file.")

    parser.add_argument("--musicxml", type=Path, help="Path to matching MusicXML file (optional).")

    parser.add_argument("--out", type=Path, help="Target output directory (optional).")

    parser.add_argument("--in-dir", type=Path, help="Target input directory (optional).")

    args = parser.parse_args()



    output_base = args.out if args.out else PROJECT_ROOT / "work" / "private_e2e_smoke_v0_1"

    output_base.mkdir(parents=True, exist_ok=True)



    inputs = []

    if args.pdf:

        if not args.pdf.exists():

            print(f"Error: Single PDF input not found: {args.pdf}", file=sys.stderr)

            sys.exit(1)

        inputs.append((args.pdf, args.musicxml))

    else:

        private_dir = args.in_dir if args.in_dir else PROJECT_ROOT.parent / "score2gp-private-fixtures" / "fixtures" / "private"

        if not private_dir.exists():

            print(f"No private fixtures directory found at {private_dir}", file=sys.stderr)

            sys.exit(0)



        pdf_paths = sorted(private_dir.glob("*.pdf"))

        for pdf_path in pdf_paths:

            musicxml_candidates = [

                private_dir / f"{pdf_path.stem}.mxl",

                private_dir / f"{pdf_path.stem}.musicxml",

                private_dir / f"{pdf_path.stem}.xml",

            ]

            matching_musicxml = None

            for candidate in musicxml_candidates:

                if candidate.exists():

                    matching_musicxml = candidate

                    break

            inputs.append((pdf_path, matching_musicxml))



    if not inputs:

        print("No private inputs found to process.", file=sys.stderr)

        sys.exit(0)



    summaries = []

    for pdf_path, mxl_path in inputs:

        print(f"Processing {pdf_path.name}...")

        safe_summary = run_pipeline_for_input(pdf_path, mxl_path, output_base)

        summaries.append(safe_summary)



    master_json_path = output_base / "corpus_harness_summary.json"

    master_json_path.write_text(json.dumps(summaries, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote master JSON report to {master_json_path}")



if __name__ == "__main__":

    main()
