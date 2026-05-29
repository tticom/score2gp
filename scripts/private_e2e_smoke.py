#!/usr/bin/env python3
"""
scripts/private_e2e_smoke.py

Private-safe end-to-end diagnostic smoke pass script.
Runs a local diagnostic workflow against real private inputs and writes
anonymized, private-safe summaries and artifacts to work/.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add the project source to sys.path to allow imports from score2gp
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from score2gp.private_diagnostics import run_private_diagnostic_smoke
from score2gp.gp_package import write_gp, validate_gp
from score2gp.ir import ScoreIR


def anonymize_name(path: Path) -> str:
    """Anonymize private input filenames to prevent private data leakage."""
    name = path.name.lower()
    if "derek" in name or "trucks" in name:
        return "private_input_1"
    if "caged" in name or "guitar tab creator" in name:
        return "private_input_2"
    # To prevent collisions, append a safe suffix if it matches known patterns
    for suffix in ["lesson-3", "lesson-4", "lesson-5", "lesson-6", "lesson-7", "melodic soloing"]:
        if suffix in name:
            safe_suffix = suffix.replace(" ", "_").replace("-", "_")
            return f"private_input_custom_{safe_suffix}"
    return "private_input_custom"


def run_pipeline_for_input(
    pdf_path: Path,
    musicxml_path: Optional[Path],
    output_base: Path,
    allow_remediation: bool = False,
    allow_skip_unboxed: bool = False,
) -> Dict[str, Any]:
    """Run E2E diagnostic pipeline for a single input and return its private-safe summary."""
    label = anonymize_name(pdf_path)
    out_dir = output_base / label
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1-4. Run PDF inspection, TabRaw extraction, MusicXML import/preflight and alignment
    summary_raw = {}
    try:
        summary_raw = run_private_diagnostic_smoke(
            pdf_path=pdf_path,
            musicxml_path=musicxml_path,
            out_dir=out_dir,
            allow_remediation=allow_remediation,
            allow_skip_unboxed=allow_skip_unboxed,
        )
    except Exception as exc:
        summary_raw = {
            "input": {"pdf_basename": pdf_path.name},
            "musicxml": {
                "exists": musicxml_path.exists() if musicxml_path else False,
                "basename": musicxml_path.name if musicxml_path else None,
            },
            "extraction": {"total_candidates": 0, "playable_candidates": 0, "non_playable_candidates": 0},
            "build_ir": {
                "ran": False,
                "failed": True,
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            "suitability": {
                "recommended_next_action": "diagnose-unhandled-pipeline-exception",
                "recommendation_categories": ["pipeline_exception"],
            },
        }

    # Retrieve page count, text success, and drawings from the inspect_pdf.json
    page_count = 0
    text_extraction_succeeded = False
    drawn_tab_geometry_detected = False

    inspect_json_path = out_dir / "inspect" / "inspect_pdf.json"
    if inspect_json_path.exists():
        try:
            inspect_data = json.loads(inspect_json_path.read_text(encoding="utf-8"))
            page_count = inspect_data.get("page_count", 0)
            pages = inspect_data.get("pages", [])
            text_extraction_succeeded = any(p.get("text_block_count", 0) > 0 for p in pages)
            drawn_tab_geometry_detected = any(p.get("drawing_count", 0) > 0 for p in pages)
        except Exception:
            pass

    # If the above fails orpymupdf is missing, fall back to simple heuristics
    extraction = summary_raw.get("extraction", {})
    if extraction.get("total_candidates", 0) > 0:
        text_extraction_succeeded = True

    # 5. Check if ScoreIR was written
    ir_path = out_dir / "score.ir.json"
    score_ir_written = ir_path.exists()

    # 6. Attempt write-gp only if ScoreIR was actually written safely
    gp_written = False
    gp_valid = False
    gp_path = out_dir / "smoke.gp"
    gp_write_error = None

    if score_ir_written:
        try:
            score = ScoreIR.from_json_file(ir_path)
            warnings = write_gp(score, gp_path)
            gp_written = gp_path.exists()
            if gp_written:
                validation = validate_gp(gp_path)
                gp_valid = not validation.get("errors")
        except Exception as exc:
            gp_write_error = f"{type(exc).__name__}: {str(exc)}"

    # Determine failure category
    primary_failure = None
    secondary_codes = []

    build_ir_info = summary_raw.get("build_ir", {})
    if build_ir_info.get("failed"):
        primary_failure = build_ir_info.get("error_category") or build_ir_info.get("error_type")
        message = build_ir_info.get("message")
        if message:
            secondary_codes.append(message)
    elif summary_raw.get("blocking_reason"):
        primary_failure = "missing_musicxml"
        secondary_codes.append(summary_raw["blocking_reason"])
    elif gp_write_error:
        primary_failure = "gp_write_failed"
        secondary_codes.append(gp_write_error)
    elif score_ir_written and not gp_valid:
        primary_failure = "gp_validation_failed"

    # Gather warning codes as secondary reason codes
    for warning_code in extraction.get("grouping_warning_codes", []):
        secondary_codes.append(warning_code)

    # Get local artifact paths relative to output base
    artifacts = {}
    for filename in [
        "extracted.tabraw.json",
        "score.ir.json",
        "diagnostics.json",
        "build_error.json",
        "warnings.json",
        "musicxml-unrecoverable-timing-report.json",
        "musicxml-unrecoverable-timing-report.html",
        "pdf-edge-boundary-report.json",
        "pdf-edge-boundary-report.html",
        "grouping-diagnostics.html",
    ]:
        file_path = out_dir / filename
        if file_path.exists():
            # For filenames with multiple dots or dashes, let's keep the name simple as the key
            key = filename.replace(".", "_").replace("-", "_")
            artifacts[key] = f"{label}/{filename}"
    if gp_path.exists():
        artifacts["gp_package"] = f"{label}/smoke.gp"

    # Define classification
    classification = "pdf-tab-musicxml" if musicxml_path else "pdf-tab-only"

    # Align statuses
    timing_status = "not_attempted"
    alignment_status = "not_attempted"
    scoreir_gate_status = "not_attempted"

    if classification == "pdf-tab-musicxml":
        if build_ir_info.get("ran"):
            timing_status = "passed"
            alignment_status = "passed"
            scoreir_gate_status = "passed"
        elif build_ir_info.get("failed"):
            timing_status = "failed"
            alignment_status = "failed"
            scoreir_gate_status = "refused"

    # Build the final private-safe summary for this input
    return {
        "input_label": label,
        "input_type_classification": classification,
        "page_count": page_count,
        "whether_text_extraction_succeeded": text_extraction_succeeded,
        "whether_ascii_tab_detected": extraction.get("playable_candidates", 0) > 0,
        "whether_drawn_tab_geometry_detected": drawn_tab_geometry_detected,
        "candidate_counts": {
            "total_candidates": extraction.get("total_candidates", 0),
            "playable_candidates": extraction.get("playable_candidates", 0),
            "non_playable_candidates": extraction.get("non_playable_candidates", 0),
        },
        "grouping_status": extraction.get("grouping_status", "unknown"),
        "timing_status": timing_status,
        "musicxml_timing_risk_status": "low_risk" if classification == "pdf-tab-musicxml" and timing_status == "passed" else "high_risk" if timing_status == "failed" else "none",
        "alignment_status": alignment_status,
        "scoreir_gate_status": scoreir_gate_status,
        "whether_scoreir_written": score_ir_written,
        "whether_gp_written": gp_written,
        "primary_failure_refusal_reason": primary_failure,
        "secondary_reason_codes": sorted(list(set(secondary_codes))),
        "artifact_paths": artifacts,
        "next_diagnostic_recommendation": summary_raw.get("suitability", {}).get("recommended_next_action", "unknown"),
    }


def main():
    args = parse_args()
    
    # Base output path
    output_base = args.out if args.out else PROJECT_ROOT / "work" / "private_e2e_smoke_v0_1"
    output_base.mkdir(parents=True, exist_ok=True)

    inputs = []
    if args.pdf:
        # Single input mode
        if not args.pdf.exists():
            print(f"Error: Single PDF input not found: {args.pdf}", file=sys.stderr)
            sys.exit(1)
        inputs.append((args.pdf, args.musicxml))
    else:
        # Directory scan mode
        private_dir = PROJECT_ROOT / "fixtures" / "private"
        if not private_dir.exists():
            print(f"No private fixtures directory found at {private_dir}", file=sys.stderr)
            sys.exit(0)
            
        pdf_paths = sorted(private_dir.glob("*.pdf"))
        for pdf_path in pdf_paths:
            # Check for matching MusicXML
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

    # Process all inputs
    summaries = []
    for pdf_path, mxl_path in inputs:
        print(f"Processing {pdf_path.name}...")
        safe_summary = run_pipeline_for_input(
            pdf_path,
            mxl_path,
            output_base,
            allow_remediation=True,
            allow_skip_unboxed=True,
        )
        summaries.append(safe_summary)

    # Write master summary JSON
    master_json_path = output_base / "private_e2e_summary.json"
    master_json_path.write_text(json.dumps(summaries, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote master JSON report to {master_json_path}")

    # Write master summary Markdown
    master_md_path = output_base / "private_e2e_summary.md"
    markdown_content = generate_markdown_summary(summaries)
    master_md_path.write_text(markdown_content, encoding="utf-8")
    print(f"Wrote master Markdown report to {master_md_path}")


def generate_markdown_summary(summaries: List[Dict[str, Any]]) -> str:
    """Generate a clean private-safe Markdown summary from results."""
    lines = [
        "# Private E2E Diagnostic Smoke Summary",
        "",
        "This report is private-safe and contains only anonymized labels, counts, statuses, and recommendation codes.",
        "",
        "| Label | Type | Pages | Extract | ASCII Tab | Drawn Tab | Playable | ScoreIR | GP | Failure Reason | Next Recommendation |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for s in summaries:
        lines.append(
            f"| `{s['input_label']}` "
            f"| `{s['input_type_classification']}` "
            f"| {s['page_count']} "
            f"| {'Yes' if s['whether_text_extraction_succeeded'] else 'No'} "
            f"| {'Yes' if s['whether_ascii_tab_detected'] else 'No'} "
            f"| {'Yes' if s['whether_drawn_tab_geometry_detected'] else 'No'} "
            f"| {s['candidate_counts']['playable_candidates']} "
            f"| {'Yes' if s['whether_scoreir_written'] else 'No'} "
            f"| {'Yes' if s['whether_gp_written'] else 'No'} "
            f"| `{s['primary_failure_refusal_reason'] or 'none'}` "
            f"| `{s['next_diagnostic_recommendation']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Private-safe E2E diagnostic smoke runner.")
    parser.add_argument("--pdf", type=Path, help="Path to a single private PDF file.")
    parser.add_argument("--musicxml", type=Path, help="Path to matching MusicXML file (optional).")
    parser.add_argument("--out", type=Path, help="Target output directory (optional).")
    return parser.parse_args()


if __name__ == "__main__":
    main()
