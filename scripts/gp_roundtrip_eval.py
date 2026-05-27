#!/usr/bin/env python3
"""
scripts/gp_roundtrip_eval.py

Private-safe GP-originated PDF round-trip evaluation script.
Runs the conversion pipeline, extracts notes from both recovered ScoreIR
and original native GP oracle files, performs semantic comparison,
and reports private-safe matching statistics.
"""

import argparse
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from score2gp.private_diagnostics import run_private_diagnostic_smoke
from score2gp.gp_package import write_gp, validate_gp
from score2gp.ir import ScoreIR


def extract_native_gp_notes(gp_path: Path) -> List[Dict[str, Any]]:
    """Parse notes from either native flat GP7 or score2gp nested GP package."""
    if not gp_path.exists():
        return []

    try:
        with zipfile.ZipFile(gp_path, 'r') as zf:
            xml_content = zf.read('Content/score.gpif')
        root = ET.fromstring(xml_content)

        # If it's a score2gp nested package (no global 'Notes' element), convert via extract_score_ir_from_gp
        if root.find('Notes') is None:
            from score2gp.gp_package import extract_score_ir_from_gp, ScoreBooklet
            score_booklet_or_ir = extract_score_ir_from_gp(gp_path)
            if isinstance(score_booklet_or_ir, ScoreBooklet):
                score = score_booklet_or_ir.scores[0]
            else:
                score = score_booklet_or_ir
            return extract_recovered_notes(score)

        # Otherwise, parse native GP7 flat XML structure:
        # 1. Parse Notes map
        notes_map = {}
        notes_node = root.find('Notes')
        if notes_node is not None:
            for note_node in notes_node.findall('Note'):
                nid = note_node.get('id')
                string = None
                fret = None
                props = note_node.find('Properties')
                if props is not None:
                    for prop in props.findall('Property'):
                        name = prop.get('name')
                        if name == 'String':
                            # Native GP7 is 0-indexed where 0 = low E (string 6) and 5 = high E (string 1)
                            # We map to 1-indexed (1 = high E, 6 = low E)
                            val = int(prop.find('String').text or 0)
                            string = 6 - val
                        elif name == 'Fret':
                            fret = int(prop.find('Fret').text or 0)
                notes_map[nid] = {'string': string, 'fret': fret}

        # 2. Parse Beats map
        beats_map = {}
        beats_node = root.find('Beats')
        if beats_node is not None:
            for beat_node in beats_node.findall('Beat'):
                bid = beat_node.get('id')
                notes_text = beat_node.find('Notes')
                nids = notes_text.text.split() if (notes_text is not None and notes_text.text) else []
                beats_map[bid] = nids

        # 3. Parse Voices map
        voices_map = {}
        voices_node = root.find('Voices')
        if voices_node is not None:
            for voice_node in voices_node.findall('Voice'):
                vid = voice_node.get('id')
                beats_text = voice_node.find('Beats')
                bids = beats_text.text.split() if (beats_text is not None and beats_text.text) else []
                voices_map[vid] = bids

        # 4. Traverse MasterBars and map Track 0 Bar IDs to their 1-indexed MasterBar index
        bar_to_mb = {}
        mb_node = root.find('MasterBars')
        if mb_node is not None:
            for mb_idx, mb in enumerate(mb_node.findall('MasterBar')):
                bars_text = mb.find('Bars')
                if bars_text is not None and bars_text.text:
                    bar_ids = [int(x) for x in bars_text.text.split()]
                    if bar_ids:
                        bar_to_mb[bar_ids[0]] = mb_idx + 1

        notes = []
        bars_node = root.find('Bars')
        if bars_node is not None:
            bars = bars_node.findall('Bar')
            for bar_id, mb_index in bar_to_mb.items():
                if bar_id < len(bars):
                    bar_node = bars[bar_id]
                    voices_text = bar_node.find('Voices')
                    vids = voices_text.text.split() if (voices_text is not None and voices_text.text) else []
                    if vids:
                        guitar_vid = vids[0]
                        if guitar_vid != '-1':
                            bids = voices_map.get(guitar_vid, [])
                            for bid in bids:
                                nids = beats_map.get(bid, [])
                                for nid in nids:
                                    note_info = notes_map.get(nid, {})
                                    notes.append({
                                        'bar_index': mb_index,
                                        'string': note_info.get('string'),
                                        'fret': note_info.get('fret'),
                                    })
        return notes
    except Exception as e:
        print(f"Warning: Failed to extract native GP notes: {e}", file=sys.stderr)
        return []


def extract_recovered_notes(score: ScoreIR) -> List[Dict[str, Any]]:
    """Extract notes sequence from a ScoreIR object."""
    notes = []
    for bar in sorted(score.bars, key=lambda b: b.index):
        for event in sorted(bar.events, key=lambda e: (e.timing.onset_ticks, e.id)):
            if event.is_rest:
                continue
            for note in event.notes:
                notes.append({
                    'bar_index': bar.index,
                    'string': note.string,
                    'fret': note.fret,
                })
    return notes


def run_roundtrip_eval(
    pdf_path: Path,
    musicxml_path: Optional[Path],
    oracle_gp_path: Optional[Path],
    output_dir: Path
) -> Dict[str, Any]:
    """Execute E2E diagnostic and run semantic comparison against oracle."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run pipeline smoke pass
    summary_raw = run_private_diagnostic_smoke(
        pdf_path=pdf_path,
        musicxml_path=musicxml_path,
        out_dir=output_dir,
        allow_remediation=True,
        allow_skip_unboxed=True,
    )

    ir_path = output_dir / "score.ir.json"
    gp_path = output_dir / "smoke.gp"

    score_ir_written = ir_path.exists()
    gp_written = False

    # Write GP if ScoreIR is present
    if score_ir_written:
        try:
            score = ScoreIR.from_json_file(ir_path)
            write_gp(score, gp_path)
            gp_written = gp_path.exists()
        except Exception:
            pass

    # 2. Extract extraction geometry metrics
    extraction = summary_raw.get("extraction", {})
    total_candidates = extraction.get("total_candidates", 0)
    playable_candidates = extraction.get("playable_candidates", 0)
    candidates_with_system = extraction.get("candidates_with_system", 0)
    candidates_with_bar = extraction.get("candidates_with_bar", 0)
    candidates_with_string = extraction.get("candidates_with_string", 0)

    # 3. Read warning codes/blocking safety gate
    refusal_reasons = summary_raw.get("build_ir", {}).get("error_category") or summary_raw.get("blocking_reason")
    secondary_codes = summary_raw.get("build_ir", {}).get("message") or extraction.get("grouping_warning_codes", [])
    if isinstance(secondary_codes, str):
        secondary_codes = [secondary_codes]

    # 4. Semantic Comparison against Oracle GP
    comparison = {
        "oracle_available": False,
        "oracle_notes_count": 0,
        "recovered_notes_count": 0,
        "string_matches": 0,
        "fret_matches": 0,
        "full_matches": 0,
        "string_match_rate": 0.0,
        "fret_match_rate": 0.0,
    }

    if oracle_gp_path and oracle_gp_path.exists() and score_ir_written:
        comparison["oracle_available"] = True

        # Load scores
        recovered_score = ScoreIR.from_json_file(ir_path)
        oracle_notes = extract_native_gp_notes(oracle_gp_path)
        recovered_notes = extract_recovered_notes(recovered_score)

        # Filter oracle notes to only cover the measures we processed
        max_bar = len(recovered_score.bars)
        oracle_notes_filtered = [n for n in oracle_notes if n["bar_index"] <= max_bar]

        comparison["oracle_notes_count"] = len(oracle_notes_filtered)
        comparison["recovered_notes_count"] = len(recovered_notes)

        # Pairwise compare within each bar
        total_matched = 0
        total_string_matched = 0

        for b in range(1, max_bar + 1):
            b_oracle = [n for n in oracle_notes_filtered if n["bar_index"] == b]
            b_recovered = [n for n in recovered_notes if n["bar_index"] == b]

            for o_note, r_note in zip(b_oracle, b_recovered):
                if o_note["string"] == r_note["string"]:
                    total_string_matched += 1
                    if o_note["fret"] == r_note["fret"]:
                        total_matched += 1

        comparison["string_matches"] = total_string_matched
        comparison["fret_matches"] = total_matched
        comparison["full_matches"] = total_matched

        if len(oracle_notes_filtered) > 0:
            comparison["string_match_rate"] = total_string_matched / len(oracle_notes_filtered)
            comparison["fret_match_rate"] = total_matched / len(oracle_notes_filtered)

    # 5. Evaluate Quality Gate & Verdicts
    per_bar_quality = summary_raw.get("build_ir", {}).get("per_bar_quality_counts", {})
    poor_bars = per_bar_quality.get("poor", 0)
    unknown_bars = per_bar_quality.get("unknown", 0)

    semantic_comparison_ran = comparison.get("oracle_available", False)
    semantic_roundtrip_passed = False
    semantic_roundtrip_status = "not_run"
    failure_category = None
    primary_failure_reason = None
    recommended_next_action = None

    if not score_ir_written:
        semantic_roundtrip_status = "diagnostic_only"
        failure_category = "strict_grouping_refused"
        primary_failure_reason = "ScoreIR file was not generated."
        recommended_next_action = "resolve-pipeline-exception-or-missing-input"
    elif not gp_written:
        semantic_roundtrip_status = "diagnostic_only"
        failure_category = "generated_output_semantically_invalid"
        primary_failure_reason = "GP package file compilation failed."
        recommended_next_action = "fix-gp-writer-validation-errors"
    elif not semantic_comparison_ran:
        semantic_roundtrip_status = "not_run"
        failure_category = "oracle_unavailable"
        primary_failure_reason = "Oracle GP file is not available for comparison."
        recommended_next_action = "provide-oracle-gp-package"
    else:
        # We did run comparison!
        oracle_count = comparison["oracle_notes_count"]
        recovered_count = comparison["recovered_notes_count"]
        string_rate = comparison["string_match_rate"]
        fret_rate = comparison["fret_match_rate"]

        note_count_diff_ratio = abs(recovered_count - oracle_count) / max(1, oracle_count)

        if poor_bars > 0 or unknown_bars > 0:
            semantic_roundtrip_status = "failed_alignment_quality"
            failure_category = "failed_alignment_quality"
            primary_failure_reason = f"Poor/unknown bar quality detected (poor={poor_bars}, unknown={unknown_bars})."
            recommended_next_action = "inspect-poor-or-unknown-bars-before-conversion"
        elif note_count_diff_ratio > 0.02:
            semantic_roundtrip_status = "failed_note_count_mismatch"
            failure_category = "failed_note_count_mismatch"
            primary_failure_reason = f"Recovered note count {recovered_count} differs from oracle count {oracle_count} by {note_count_diff_ratio:.1%}."
            recommended_next_action = "align-unboxed-system-barlines"
        elif string_rate < 0.90 or fret_rate < 0.90:
            semantic_roundtrip_status = "failed_string_fret_mismatch"
            failure_category = "failed_string_fret_mismatch"
            primary_failure_reason = f"Low string/fret match rates (string={string_rate:.1%}, fret={fret_rate:.1%})."
            recommended_next_action = "tune-string-mapping-heuristics"
        else:
            semantic_roundtrip_passed = True
            semantic_roundtrip_status = "passed"
            recommended_next_action = "none"

    diagnostic_only = not semantic_roundtrip_passed

    # 6. Diagnose the Main Semantic Failure (Phase 3)
    diagnose_failure = {
        "string_concentration_on_string_1": False,
        "fret_matching_rate_is_zero": False,
        "measure_count_mismatches_present": False,
        "unboxed_systems_present": False,
    }

    if score_ir_written:
        # Check string concentration
        try:
            recovered_score = ScoreIR.from_json_file(ir_path)
            recovered_notes = extract_recovered_notes(recovered_score)
            if recovered_notes:
                string_1_notes = sum(1 for n in recovered_notes if n["string"] == 1)
                if string_1_notes / len(recovered_notes) > 0.70:
                    diagnose_failure["string_concentration_on_string_1"] = True
        except Exception:
            pass

        # Check fret matching rate is 0
        if semantic_comparison_ran:
            if comparison["fret_match_rate"] == 0.0 and comparison["oracle_notes_count"] > 0:
                diagnose_failure["fret_matching_rate_is_zero"] = True

        # Check measure count mismatches
        build_ir_info = summary_raw.get("build_ir", {})
        if build_ir_info.get("bars_with_count_mismatches"):
            diagnose_failure["measure_count_mismatches_present"] = True

        # Check unboxed systems
        for w_code in summary_raw.get("extraction", {}).get("warning_counts", {}):
            if "unboxed" in w_code or "missing_pdf_barlines" in w_code or "not_constructible" in w_code:
                diagnose_failure["unboxed_systems_present"] = True

    # 7. Build final report
    report = {
        "input_label": "private_input_1" if "derek" in pdf_path.name.lower() else "private_input_custom",
        "whether_scoreir_written": score_ir_written,
        "whether_gp_written": gp_written,
        "whether_semantic_comparison_ran": semantic_comparison_ran,
        "semantic_roundtrip_status": semantic_roundtrip_status,
        "semantic_roundtrip_passed": semantic_roundtrip_passed,
        "diagnostic_only": diagnostic_only,
        "failure_category": failure_category,
        "primary_failure_reason": primary_failure_reason,
        "recommended_next_action": recommended_next_action,
        "candidate_counts": {
            "total_candidates": total_candidates,
            "playable_candidates": playable_candidates,
            "candidates_with_system": candidates_with_system,
            "candidates_with_bar": candidates_with_bar,
            "candidates_with_string": candidates_with_string,
        },
        "refusal_reason_codes": {
            "primary": refusal_reasons,
            "secondary": sorted(list(set(secondary_codes))),
        },
        "timing_mapping_status": summary_raw.get("build_ir", {}).get("ran", False),
        "semantic_comparison": comparison,
        "semantic_diagnostics": diagnose_failure,
        "private_safe_output_dir": str(output_dir.relative_to(PROJECT_ROOT)) if output_dir.is_relative_to(PROJECT_ROOT) else str(output_dir),
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="E2E GP Round-trip evaluation tool.")
    parser.add_argument("--pdf", type=Path, required=True, help="Path to private PDF exported from GP.")
    parser.add_argument("--musicxml", type=Path, help="Path to matching MusicXML (optional).")
    parser.add_argument("--gp", type=Path, help="Path to original GP oracle (optional).")
    parser.add_argument("--out", type=Path, help="Target output directory (optional).")

    args = parser.parse_args()

    pdf_path = args.pdf
    musicxml_path = args.musicxml
    gp_path = args.gp

    output_dir = args.out if args.out else PROJECT_ROOT / "work" / "roundtrip_eval"

    print(f"Running GP round-trip evaluation for {pdf_path.name}...")
    report = run_roundtrip_eval(pdf_path, musicxml_path, gp_path, output_dir)

    # Print clean private-safe report
    print("\n=======================================================")
    print("      PRIVATE-SAFE GP ROUND-TRIP EVALUATION REPORT      ")
    print("=======================================================")
    print(json.dumps(report, indent=2))
    print("=======================================================")

    # Save the report
    report_json_path = output_dir / "roundtrip_report.json"
    report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote evaluation report to {report_json_path}")


if __name__ == "__main__":
    main()
