#!/usr/bin/env python3
"""
scripts/private_gp_quality_audit.py

Post-serialization quality audit script.
Analyzes the generated GP packages and ScoreIR outputs to classify the quality
and identify the next true correctness blocker.
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

# Add the project source to sys.path to allow imports from score2gp
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from score2gp.gp_package import inspect_gp


def classify_gp_quality(metrics: Dict[str, Any]) -> str:
    """Classify the post-serialization GP output quality into one of the standard categories."""
    gp_written = metrics.get("whether_gp_package_produced", False)
    gpif_note_count = metrics.get("gpif_note_count", 0)
    scoreir_note_count = metrics.get("scoreir_note_count", 0)
    playable_frets = metrics.get("playable_fret_candidate_count", 0)
    matched_frets = metrics.get("matched_fret_candidate_count", 0)
    gpif_measures = metrics.get("gpif_measure_count", 0)
    scoreir_bars = metrics.get("scoreir_bar_count", 0)
    tech_candidates = metrics.get("non_playable_technique_text_candidate_count", 0)
    warnings = metrics.get("warning_code_counts", {})

    # 1. Empty or near-empty
    if not gp_written or gpif_note_count == 0 or scoreir_note_count == 0:
        return "gp_output_empty_or_near_empty"

    # 2. Bar-count consistency check
    if gpif_measures != scoreir_bars:
        return "gp_output_bar_alignment_suspect"

    # 3. Bar alignment suspect from OMR warnings
    has_alignment_warnings = any(
        "shifted" in k or "skipped" in k or "alignment" in k
        for k in warnings.keys()
    )
    if has_alignment_warnings:
        return "gp_output_bar_alignment_suspect"

    # 4. Fret matching suspect
    # High playable frets but very low matched count (e.g. < 40%)
    if playable_frets > 10 and (matched_frets / playable_frets) < 0.40:
        return "gp_output_fret_matching_suspect"

    # 5. Serialized-output coverage checks
    # gpif_note_count vs scoreir_note_count
    if gpif_note_count < scoreir_note_count * 0.70:
        return "gp_output_note_coverage_low"

    # gpif_note_count vs playable_fret_candidate_count where relevant
    if playable_frets > 10 and gpif_note_count < playable_frets * 0.70:
        return "gp_output_note_coverage_low"

    # 6. Note coverage low (re-verify matched frets ratio)
    if playable_frets > 10 and (matched_frets / playable_frets) < 0.70:
        return "gp_output_note_coverage_low"

    # 7. Technique loss expected
    if tech_candidates > 0:
        return "gp_output_technique_loss_expected"

    # 8. Basic pass
    return "gp_output_quality_pass_basic"


def audit_single_input(out_dir: Path, label: str) -> Optional[Dict[str, Any]]:
    """Audit a single processed input directory and return its post-serialization metrics."""
    summary_json_path = out_dir / "summary.json"
    score_ir_path = out_dir / "score.ir.json"
    smoke_gp_path = out_dir / "smoke.gp"
    warnings_json_path = out_dir / "warnings.json"

    if not summary_json_path.exists():
        return None

    # Load summary.json
    try:
        summary_data = json.loads(summary_json_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    # Gather baseline OMR/Pipeline metrics
    extraction = summary_data.get("extraction", {})
    build_ir = summary_data.get("build_ir", {})
    score_ir_summary = summary_data.get("score_ir", {})

    playable_frets = extraction.get("playable_candidates", 0)
    matched_frets = build_ir.get("matched_playable_candidate_count", 0)
    unmatched_frets = playable_frets - matched_frets
    tech_candidates = extraction.get("technique_text_candidates", 0)
    inferred_systems = extraction.get("inferred_system_count", 0)
    detected_bars = extraction.get("inferred_bar_count", 0)

    # Load warnings.json
    warning_counts = {}
    if warnings_json_path.exists():
        try:
            warnings_data = json.loads(warnings_json_path.read_text(encoding="utf-8"))
            # Count warning occurrences by code
            for w in warnings_data:
                code = w.get("code")
                if code:
                    warning_counts[code] = warning_counts.get(code, 0) + 1
        except Exception:
            pass

    # Detect features applied from warning counts
    dedup_applied = ("musicxml_duplicate_staff_tab_dedup_applied" in warning_counts)
    large_spaced_applied = ("pdf_large_tab_staff_spacing_detected" in warning_counts)

    # Parse ScoreIR counts
    scoreir_bar_count = 0
    scoreir_event_count = 0
    scoreir_note_count = 0
    scoreir_written = score_ir_path.exists()

    if scoreir_written:
        try:
            ir_data = json.loads(score_ir_path.read_text(encoding="utf-8"))
            bars = ir_data.get("bars", [])
            scoreir_bar_count = len(bars)
            for bar in bars:
                events = bar.get("events", [])
                scoreir_event_count += len(events)
                for event in events:
                    scoreir_note_count += len(event.get("notes", []))
        except Exception:
            pass

    # Parse GPIF counts from smoke.gp
    gp_written = smoke_gp_path.exists()
    gpif_measure_count = 0
    gpif_beat_count = 0
    gpif_note_count = 0
    gp_non_empty = False

    if gp_written:
        try:
            # Run gp_package inspect helper
            gp_summary = inspect_gp(smoke_gp_path)
            gpif_measure_count = gp_summary.get("bar_count", 0)
            gpif_note_count = gp_summary.get("note_count", 0)
            gp_non_empty = (gpif_note_count > 0)

            # Extract beat count from ZIP without fully parsing
            with zipfile.ZipFile(smoke_gp_path, "r") as zf:
                if "Content/score.gpif" in zf.namelist():
                    xml_content = zf.read("Content/score.gpif")
                    root = ET.fromstring(xml_content)
                    gpif_beat_count = len(root.findall(".//Beat"))
        except Exception:
            pass

    # Match MusicXML measure count to ScoreIR bar count as aligned
    musicxml_measure_count = scoreir_bar_count

    # Determine first failing stage if any
    first_failing_stage = None
    pass_fail = "pass"
    if not scoreir_written:
        pass_fail = "fail"
        first_failing_stage = summary_data.get("suitability", {}).get("recommended_next_action", "build_ir")
    elif not gp_written:
        pass_fail = "fail"
        first_failing_stage = "gp_write"

    # Relative paths for artifacts
    artifact_paths = {
        "score_ir_json": f"{label}/score.ir.json" if scoreir_written else None,
        "gp_package": f"{label}/smoke.gp" if gp_written else None,
        "warnings_json": f"{label}/warnings.json" if warnings_json_path.exists() else None,
    }
    artifact_paths = {k: v for k, v in artifact_paths.items() if v is not None}

    metrics = {
        "input_label": label,
        "pass_fail_status": pass_fail,
        "first_failing_stage": first_failing_stage,
        "inferred_system_count": inferred_systems,
        "detected_bar_count": detected_bars,
        "musicxml_measure_count": musicxml_measure_count,
        "scoreir_bar_count": scoreir_bar_count,
        "scoreir_event_count": scoreir_event_count,
        "scoreir_note_count": scoreir_note_count,
        "gpif_measure_count": gpif_measure_count,
        "gpif_beat_count": gpif_beat_count,
        "gpif_note_count": gpif_note_count,
        "playable_fret_candidate_count": playable_frets,
        "matched_fret_candidate_count": matched_frets,
        "unmatched_fret_candidate_count": unmatched_frets,
        "non_playable_technique_text_candidate_count": tech_candidates,
        "warning_code_counts": warning_counts,
        "whether_duplicate_staff_tab_deduplication_applied": dedup_applied,
        "whether_large_spaced_tab_detection_applied": large_spaced_applied,
        "whether_gp_package_produced": gp_written,
        "whether_gp_package_contains_non_empty_note_content": gp_non_empty,
        "artifact_paths": artifact_paths,
    }

    # Classify quality
    metrics["quality_category"] = classify_gp_quality(metrics)
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Post-serialization GP output quality audit.")
    parser.add_argument("--dir", type=Path, help="Directory containing E2E smoke outputs.")
    parser.add_argument("--out", type=Path, help="Output directory for quality report.")
    args = parser.parse_args()

    smoke_dir = args.dir if args.dir else PROJECT_ROOT / "work" / "private_e2e_smoke_v0_1"
    output_dir = args.out if args.out else PROJECT_ROOT / "work" / "private_gp_quality_audit_v0_1"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not smoke_dir.exists():
        print(f"Error: E2E smoke outputs directory not found at {smoke_dir}", file=sys.stderr)
        sys.exit(1)

    audits = []
    # Scan subdirectories
    subdirs = sorted([d for d in smoke_dir.iterdir() if d.is_dir()])
    for subdir in subdirs:
        label = subdir.name
        audit_res = audit_single_input(subdir, label)
        if audit_res:
            audits.append(audit_res)

    if not audits:
        print("No processed E2E directories found to audit.", file=sys.stderr)
        sys.exit(0)

    # Write master summary JSON
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(audits, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote master quality audit summary JSON to {summary_path}")

    # Generate Markdown Table and Console output
    print("\n=== Post-Serialization GP Output Quality Audit ===")
    print(f"Total Audited Scores: {len(audits)}")
    print(f"{'Input Label':<40} | {'Status':<6} | {'Quality Category':<35} | {'Notes':<6} | {'Matched':<7}")
    print("-" * 105)
    for a in audits:
        print(
            f"{a['input_label']:<40} | "
            f"{a['pass_fail_status']:<6} | "
            f"{a['quality_category']:<35} | "
            f"{a['gpif_note_count']:<6} | "
            f"{a['matched_fret_candidate_count']:<7}"
        )

    # Write Markdown summary report
    md_path = output_dir / "summary.md"
    md_lines = [
        "# Post-Serialization GP Output Quality Audit Report",
        "",
        "This report summarizes the musical plausibility and notes coverage of all generated Guitar Pro packages.",
        "",
        "| Input Label | Status | Quality Category | ScoreIR Notes | GPIF Notes | Matched Frets | Deduplication | Spacing Applied |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for a in audits:
        md_lines.append(
            f"| `{a['input_label']}` "
            f"| `{a['pass_fail_status']}` "
            f"| `{a['quality_category']}` "
            f"| {a['scoreir_note_count']} "
            f"| {a['gpif_note_count']} "
            f"| {a['matched_fret_candidate_count']} "
            f"| {'Yes' if a['whether_duplicate_staff_tab_deduplication_applied'] else 'No'} "
            f"| {'Yes' if a['whether_large_spaced_tab_detection_applied'] else 'No'} |"
        )
    md_lines.append("")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote quality audit summary Markdown to {md_path}\n")


if __name__ == "__main__":
    main()
