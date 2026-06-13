#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

import fitz

from score2gp.pdf_raster_staff_diagnostics import (
    build_raster_notation_diagnostics,
    summarize_raster_treble_clef_diagnostics,
)
from score2gp.whole_note_recogniser import map_whole_note_candidates_to_read_only_outcomes


def run_diagnostics_on_file(pdf_path: Path, display_label: str = None):
    if not pdf_path.exists():
        return None

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        if display_label:
            print(f"Error opening {display_label}: PDF could not be opened", file=sys.stderr)
        else:
            print(f"Error opening {pdf_path.name}: {e}", file=sys.stderr)
        return None

    total_staff_count = 0
    total_treble_candidates = 0
    total_whole_notes = 0
    total_unknowns = 0
    whole_note_locations = []
    whole_note_pages = []

    from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict

    for i in range(len(doc)):
        page = doc[i]
        diags = build_raster_notation_diagnostics(page, page_index=i + 1, scale=2.0)
        summary = summarize_raster_treble_clef_diagnostics(diags)
        vector_diags = extract_notation_diagnostics_dict(page, i + 1)

        if summary.get("status") == "success":
            total_staff_count += summary.get("staff_count", 0)
            counts = summary.get("label_counts", {})
            total_treble_candidates += counts.get("treble_clef_candidate", 0)
            total_unknowns += counts.get("unknown", 0)

        page_whole_notes = vector_diags.get("whole_note_candidates") or []

        from score2gp.whole_note_recogniser import shape_whole_note_candidate_evidence
        shaped_candidates = shape_whole_note_candidate_evidence(
            page_whole_notes,
            page_index=i + 1,
            start_index=len(whole_note_locations) + 1
        )

        page_count = len(shaped_candidates)
        total_whole_notes += page_count

        if page_count > 0:
            whole_note_pages.append({
                "page_index": i + 1,
                "whole_note_candidate": page_count
            })

        whole_note_locations.extend(shaped_candidates)

    whole_note_candidate_summary = {
        "total_count": len(whole_note_locations),
        "pages_with_candidates": [p["page_index"] for p in whole_note_pages],
        "candidate_ids": [loc["candidate_id"] for loc in whole_note_locations],
        "candidate_count_by_page": {str(p["page_index"]): p["whole_note_candidate"] for p in whole_note_pages}
    }

    return {
        "staff_count": total_staff_count,
        "treble_clef_candidate": total_treble_candidates,
        "whole_note_candidate": total_whole_notes,
        "whole_note_candidate_pages": whole_note_pages,
        "whole_note_candidate_locations": whole_note_locations,
        "whole_note_candidate_summary": whole_note_candidate_summary,
        "unknown": total_unknowns,
        "pages": len(doc),
    }


import json
import hashlib

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()

def classify_case_result(expected_positive: bool, known_false_negative: bool, candidates: int) -> str:
    """Pure helper to classify a single case outcome."""
    if expected_positive:
        if candidates > 0:
            return "true_positive"
        else:
            return "known_false_negative" if known_false_negative else "unexpected_false_negative"
    else:
        if candidates > 0:
            return "false_positive"
        else:
            return "true_negative"


def classify_whole_note_outcome(category: str, case_id: str, candidates: int) -> str:
    """Pure helper to classify a whole-note case outcome."""
    is_positive = "whole_note" in category or "whole_note" in case_id
    is_half_note = "half_note" in category or "half_note" in case_id
    is_negative = category in ["negative_blank", "negative_tab", "negative_noise"] or "negative" in category

    if is_positive:
        return "whole_note_true_positive" if candidates > 0 else "whole_note_false_negative"
    elif is_half_note:
        return "whole_note_false_positive" if candidates > 0 else "whole_note_true_negative"
    elif is_negative:
        return "whole_note_false_positive" if candidates > 0 else "whole_note_true_negative"
    else:
        return "whole_note_not_applicable"

def summarize_whole_note_detection_status(summary: dict) -> tuple[str, list[str]]:
    """Derive readiness status and reason codes from whole-note fixture outcomes."""
    if not summary:
        return "review", ["summary_missing_or_incomplete"]

    pos_eval = summary.get("positive_fixtures_evaluated", 0)
    pos_cand = summary.get("positive_fixtures_with_candidates", 0)
    half_fp = summary.get("half_note_fixtures_with_false_positive_candidates", 0)
    neg_fp = summary.get("negative_noise_fixtures_with_false_positive_candidates", 0)

    reasons = []
    status = "pass"

    if pos_eval == 0:
        reasons.append("positive_fixtures_missing")
        status = "review"
    elif pos_cand < pos_eval:
        reasons.append("positive_candidates_missing")
        status = "review"
    else:
        reasons.append("positive_candidates_complete")

    has_fp = False
    if half_fp > 0:
        reasons.append("half_note_false_positives_present")
        has_fp = True
    if neg_fp > 0:
        reasons.append("negative_noise_false_positives_present")
        has_fp = True
    if has_fp:
        status = "fail"
    else:
        reasons.append("no_false_positive_candidates")

    return status, reasons

def generate_report(json_mode: bool = False, test_manifest: str = None):
    manifest = []
    manifest_cases = {}
    found_case_ids = set()

    if test_manifest:
        try:
            with open(test_manifest, "r") as f:
                data = json.load(f)
                for entry in data:
                    path_str = entry.get("path", "")
                    p = Path(path_str)

                    if ".." in path_str or p.is_absolute():
                        print("Warning: Rejecting unsafe test manifest path", file=sys.stderr)
                        continue

                    try:
                        res_parts = p.resolve().parts
                        is_private = False
                        for i in range(len(res_parts) - 1):
                            if res_parts[i] == "fixtures" and res_parts[i+1] == "private":
                                is_private = True
                                break
                        if is_private:
                            print("Warning: Rejecting unsafe test manifest path", file=sys.stderr)
                            continue
                    except Exception:
                        pass

                    manifest.append({
                        "path": path_str,
                        "category": entry.get("category", "test_category"),
                        "expected_positive": entry.get("expected_positive", False),
                        "known_false_negative": entry.get("known_false_negative", False),
                        "is_missing": False,
                        "case_id": entry.get("case_id", Path(path_str).name),
                        "expected_whole_note_candidate_count": entry.get("expected_whole_note_candidate_count")
                    })
        except Exception:
            print("Error loading test manifest: Invalid or missing manifest", file=sys.stderr)
            sys.exit(1)
    else:
        manifest = [
            {
                "path": "tests/fixtures/pdf/generated_standard_staff_negative_blank.pdf",
                "category": "negative_blank",
                "expected_positive": False,
                "known_false_negative": False,
                "is_missing": False,
                "expected_whole_note_candidate_count": 0,
            },
            {
                "path": "tests/fixtures/pdf/generated_standard_staff_negative_tab.pdf",
                "category": "negative_tab",
                "expected_positive": False,
                "known_false_negative": False,
                "is_missing": False,
                "expected_whole_note_candidate_count": 0,
            },
            {
                "path": "tests/fixtures/pdf/generated_standard_staff_negative_noise.pdf",
                "category": "negative_noise",
                "expected_positive": False,
                "known_false_negative": False,
                "is_missing": False,
                "expected_whole_note_candidate_count": 0,
            },
            {
                "path": "tests/fixtures/pdf/generated_standard_staff_whole_note.pdf",
                "category": "positive_whole_note",
                "expected_positive": False,
                "known_false_negative": False,
                "is_missing": False,
                "expected_whole_note_candidate_count": 2,
            },
            {
                "path": "tests/fixtures/pdf/generated_standard_staff_half_note.pdf",
                "category": "half_note",
                "expected_positive": False,
                "known_false_negative": False,
                "is_missing": False,
                "expected_whole_note_candidate_count": 0,
            },
        ]

        # Load expected cases from manifest
        manifest_path = Path("tests/fixtures/raster_diagnostics_false_negative_manifest.json")
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    data = json.load(f)
                    for entry in data.get("false_negative_cases", []):
                        case_id = entry.get("case_id")
                        file_sha256 = entry.get("file_sha256")
                        is_expected_positive = entry.get("expected_positive", True)
                        is_known_fn = entry.get("safe_category") == "currently_verified_false_negative"
                        if case_id and file_sha256:
                            manifest_cases[file_sha256] = {
                                "case_id": case_id,
                                "expected_positive": is_expected_positive,
                                "known_false_negative": is_known_fn
                            }
            except Exception as e:
                print(f"Warning: Could not load manifest: {e}", file=sys.stderr)

        private_dir = Path("fixtures/private/raster-treble-clef")
        if private_dir.exists():
            for p in private_dir.glob("*.pdf"):
                h = compute_sha256(p)
                if h in manifest_cases:
                    mc = manifest_cases[h]
                    manifest.append({
                        "path": str(p),
                        "category": "positive_private",
                        "expected_positive": mc["expected_positive"],
                        "known_false_negative": mc["known_false_negative"],
                        "case_id": mc["case_id"],
                        "is_missing": False
                    })
                    found_case_ids.add(mc["case_id"])

        # Add dummy entries for missing private fixtures so they are reported as skipped
        for file_sha256, mc in manifest_cases.items():
            if mc["case_id"] not in found_case_ids:
                manifest.append({
                    "path": f"missing_private_fixture_{mc['case_id']}.pdf",
                    "category": "positive_private",
                    "expected_positive": mc["expected_positive"],
                    "known_false_negative": mc["known_false_negative"],
                    "case_id": mc["case_id"],
                    "is_missing": True
                })

    results = {
        "negative_blank": {"cases_run": 0, "false_positives": 0, "unknowns": 0},
        "negative_tab": {"cases_run": 0, "false_positives": 0, "unknowns": 0},
        "negative_noise": {"cases_run": 0, "false_positives": 0, "unknowns": 0},
        "positive_whole_note": {"cases_run": 0, "false_positives": 0, "false_negatives": 0, "unknowns": 0},
        "half_note": {"cases_run": 0, "false_positives": 0, "false_negatives": 0, "unknowns": 0},
        "positive_private": {"cases_run": 0, "false_negatives": 0, "unknowns": 0},
    }

    totals = {
        "true_positives": 0,
        "false_positives": 0,
        "known_false_negatives": 0,
        "unexpected_false_negatives": 0,
        "unknowns": 0,
        "skipped_optional_private_fixtures": 0,
        "negative_fixture_outcomes": 0,
        "total_staves": 0,
        "total_pages": 0,
        "total_cases_inspected": 0,
    }

    wn_summary = {
        "positive_fixtures_evaluated": 0,
        "positive_fixtures_with_candidates": 0,
        "positive_fixtures_without_candidates": 0,
        "half_note_fixtures_evaluated": 0,
        "half_note_fixtures_with_false_positive_candidates": 0,
        "negative_noise_fixtures_evaluated": 0,
        "negative_noise_fixtures_with_false_positive_candidates": 0,
        "cases": []
    }

    wn_count_mismatches = 0
    wn_count_cases_evaluated = 0
    wn_count_reasons = []

    if not json_mode:
        print("Raster Diagnostics Gate Report")
        print("=" * 60)

    json_cases = []

    for item in manifest:
        is_missing = item.get("is_missing", False)
        p = Path(item["path"])
        if is_missing or not p.exists():
            if item["category"] == "positive_private":
                display = item.get("case_id", "anonymised_private_fixture")
                if not json_mode:
                    print(f"Skipping missing optional private fixture: {display}")
                totals["skipped_optional_private_fixtures"] += 1
            else:
                print(f"Warning: Expected fixture missing: {p.name}", file=sys.stderr)
            continue

        display_name = item.get("case_id", "anonymised_private_fixture") if item["category"] == "positive_private" else p.name
        res = run_diagnostics_on_file(p, display_label=display_name)
        if not res:
            print(f"Error processing {display_name}", file=sys.stderr)
            continue

        cat = item["category"]
        results.setdefault(cat, {"cases_run": 0, "false_positives": 0, "false_negatives": 0, "unknowns": 0})
        results[cat]["cases_run"] += 1
        results[cat]["unknowns"] += res["unknown"]

        totals["total_cases_inspected"] += 1
        totals["total_pages"] += res["pages"]
        totals["total_staves"] += res["staff_count"]
        totals["unknowns"] += res["unknown"]

        outcome = classify_case_result(item["expected_positive"], item["known_false_negative"], res["treble_clef_candidate"])

        if outcome == "known_false_negative":
            totals["known_false_negatives"] += 1
            results[cat]["false_negatives"] += 1
        elif outcome == "unexpected_false_negative":
            totals["unexpected_false_negatives"] += 1
            results[cat]["false_negatives"] += 1
        elif outcome == "false_positive":
            totals["false_positives"] += res["treble_clef_candidate"]
            results[cat]["false_positives"] += res["treble_clef_candidate"]
        elif outcome == "true_negative":
            totals["negative_fixture_outcomes"] += 1
        if outcome == "true_positive":
            totals["true_positives"] += 1

        wn_candidates = res.get("whole_note_candidate_summary", {}).get("total_count", 0)
        wn_outcome = classify_whole_note_outcome(cat, item.get("case_id", display_name), wn_candidates)

        wn_summary["cases"].append({
            "case_id": item.get("case_id", display_name),
            "category": cat,
            "whole_note_candidate": res.get("whole_note_candidate", 0),
            "whole_note_candidate_summary_total_count": wn_candidates,
            "whole_note_outcome": wn_outcome
        })

        if wn_outcome in ["whole_note_true_positive", "whole_note_false_negative"]:
            wn_summary["positive_fixtures_evaluated"] += 1
            if wn_candidates > 0:
                wn_summary["positive_fixtures_with_candidates"] += 1
            else:
                wn_summary["positive_fixtures_without_candidates"] += 1
        elif wn_outcome in ["whole_note_true_negative", "whole_note_false_positive"]:
            is_half = "half_note" in cat or "half_note" in item.get("case_id", display_name)
            if is_half:
                wn_summary["half_note_fixtures_evaluated"] += 1
                if wn_candidates > 0:
                    wn_summary["half_note_fixtures_with_false_positive_candidates"] += 1
            else:
                wn_summary["negative_noise_fixtures_evaluated"] += 1
                if wn_candidates > 0:
                    wn_summary["negative_noise_fixtures_with_false_positive_candidates"] += 1

        expected_wn_count = item.get("expected_whole_note_candidate_count")
        wn_count_matches = None
        if expected_wn_count is not None:
            wn_count_matches = (expected_wn_count == wn_candidates)
            wn_count_cases_evaluated += 1
            if not wn_count_matches:
                wn_count_mismatches += 1
                if expected_wn_count == 0 and wn_candidates > 0:
                    wn_count_reasons.append(f"unexpected_candidates_in_{cat}")
                elif expected_wn_count > 0 and wn_candidates < expected_wn_count:
                    wn_count_reasons.append(f"missing_candidates_in_{cat}")
                elif expected_wn_count > 0 and wn_candidates > expected_wn_count:
                    wn_count_reasons.append(f"too_many_candidates_in_{cat}")

        json_case = {
            "case_id": item.get("case_id", display_name),
            "category": cat,
            "outcome": outcome,
            "pages": res['pages'],
            "staff_count": res['staff_count'],
            "treble_clef_candidate": res['treble_clef_candidate'],
            "whole_note_candidate": res.get("whole_note_candidate", 0),
            "whole_note_candidate_pages": res.get("whole_note_candidate_pages", []),
            "whole_note_candidate_locations": res.get("whole_note_candidate_locations", []),
            "whole_note_candidate_summary": res.get("whole_note_candidate_summary", {}),
            "unknown": res['unknown']
        }

        if expected_wn_count is not None:
            json_case["expected_whole_note_candidate_count"] = expected_wn_count
            json_case["actual_whole_note_candidate_count"] = wn_candidates
            json_case["whole_note_candidate_count_matches_expected"] = wn_count_matches

        is_authorized_whole_note = Path(item["path"]).name == "generated_standard_staff_whole_note.pdf" or cat == "positive_whole_note"
        if is_authorized_whole_note:
            json_case["read_only_recognition_outcomes"] = map_whole_note_candidates_to_read_only_outcomes(res.get("whole_note_candidate_locations", []))

        json_cases.append(json_case)

        if not json_mode:
            print(f"Processed: {display_name} [{cat}]")
            print(f"  Pages: {res['pages']}")
            print(f"  Staves Detected: {res['staff_count']}")
            print(f"  Treble Candidates: {res['treble_clef_candidate']}")
            print(f"  Whole Note Candidates: {res.get('whole_note_candidate', 0)}")

            pages = res.get('whole_note_candidate_pages', [])
            if pages:
                for p_info in pages:
                    print(f"    - Page {p_info['page_index']}: {p_info['whole_note_candidate']} candidate(s)")

            locations = res.get('whole_note_candidate_locations', [])
            if locations:
                for loc in locations:
                    cid = loc.get('candidate_id', 'unknown_id')
                    print(f"    - [{cid}] Page {loc['page_index']}: bbox={loc['bbox']}")

            if is_authorized_whole_note:
                outcomes = map_whole_note_candidates_to_read_only_outcomes(locations)
                if outcomes:
                    print(f"  Read-only Recognition Outcomes: {len(outcomes)}")
                    for out in outcomes:
                        print(f"    - [{out['candidate_id']}] {out['symbol_type']}")

            print(f"  Unknowns: {res['unknown']}")

            if outcome == "known_false_negative":
                case_id = item.get("case_id", display_name)
                print(f"  -> MATCHED KNOWN FALSE NEGATIVE MANIFEST ENTRY: {case_id}")
            elif outcome == "unexpected_false_negative":
                case_id = item.get("case_id", display_name)
                print(f"  -> UNEXPECTED FALSE NEGATIVE: {case_id}")

            print("-" * 60)

    treble_gate_status = "PASS" if totals["false_positives"] == 0 and totals["unexpected_false_negatives"] == 0 else "REVIEW"

    wn_status, wn_reasons = summarize_whole_note_detection_status(wn_summary)

    if wn_status == "fail":
        wn_gate_status = "FAIL"
    elif wn_status == "review":
        wn_gate_status = "REVIEW"
    else:
        wn_gate_status = "PASS"

    wn_count_gate_status = "PASS"
    wn_count_gate_reasons_dedup = list(dict.fromkeys(wn_count_reasons)) # preserve order, dedup
    if wn_count_mismatches > 0:
        wn_count_gate_status = "FAIL"
        if not wn_count_gate_reasons_dedup:
            wn_count_gate_reasons_dedup.append("count_mismatch")
    else:
        wn_count_gate_reasons_dedup = ["counts_match"]

    if treble_gate_status == "PASS" and wn_gate_status == "PASS" and wn_count_gate_status == "PASS":
        gate_status = "PASS"
    elif wn_gate_status == "FAIL" or wn_count_gate_status == "FAIL":
        gate_status = "FAIL"
    else:
        gate_status = "REVIEW"

    if json_mode:
        json_output = {
            "schema_version": 1,
            "gate_status": gate_status,
            "whole_note_detection_gate_status": wn_gate_status,
            "whole_note_candidate_count_gate_status": wn_count_gate_status,
            "whole_note_candidate_count_gate_reasons": wn_count_gate_reasons_dedup,
            "whole_note_candidate_count_mismatches": wn_count_mismatches,
            "whole_note_candidate_count_cases_evaluated": wn_count_cases_evaluated,
            "totals": totals,
            "categories": results,
            "whole_note_detection_status": wn_status,
            "whole_note_detection_status_reasons": wn_reasons,
            "whole_note_fixture_outcome_summary": wn_summary,
            "cases": json_cases
        }
        print(json.dumps(json_output, indent=2))
    else:
        print("\nWhole-note fixture outcome summary")
        print("-" * 34)
        print(f"Whole-note detection status: {wn_status}")
        print(f"Whole-note detection status reasons: {', '.join(wn_reasons)}")
        print(f"Positive whole-note fixtures evaluated: {wn_summary['positive_fixtures_evaluated']}")
        print(f"Positive fixtures with candidates: {wn_summary['positive_fixtures_with_candidates']}")
        print(f"Positive fixtures without candidates: {wn_summary['positive_fixtures_without_candidates']}")
        print(f"Half-note fixtures evaluated: {wn_summary['half_note_fixtures_evaluated']}")
        print(f"Half-note fixtures with false-positive whole-note candidates: {wn_summary['half_note_fixtures_with_false_positive_candidates']}")
        print(f"Negative/noise fixtures evaluated: {wn_summary['negative_noise_fixtures_evaluated']}")
        print(f"Negative/noise fixtures with false-positive whole-note candidates: {wn_summary['negative_noise_fixtures_with_false_positive_candidates']}")

        print("\nAggregate Report")
        print("=" * 60)
        for cat, data in results.items():
            if data["cases_run"] > 0:
                print(f"Category: {cat}")
                print(f"  Cases Run: {data['cases_run']}")
                if "false_positives" in data:
                    print(f"  False Positives: {data['false_positives']}")
                if "false_negatives" in data:
                    print(f"  False Negatives: {data['false_negatives']}")
                print(f"  Unknowns: {data['unknowns']}")
                print("-" * 30)

        print("\nGrand Totals:")
        print(f"  Total Cases Inspected      : {totals['total_cases_inspected']}")
        print(f"  Total Pages Inspected      : {totals['total_pages']}")
        print(f"  Total Staves Detected      : {totals['total_staves']}")
        print(f"  True Positives             : {totals['true_positives']}")
        print(f"  Total False Positives      : {totals['false_positives']}")
        print(f"  Known False Negatives      : {totals['known_false_negatives']}")
        print(f"  Unexpected False Negatives : {totals['unexpected_false_negatives']}")
        print(f"  Total Unknowns             : {totals['unknowns']}")
        print(f"  Skipped Private Fixtures   : {totals['skipped_optional_private_fixtures']}")
        print(f"  Negative Fixture Outcomes  : {totals['negative_fixture_outcomes']}")
        print(f"\nGate Status: {gate_status}")

    return gate_status, totals


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Raster Diagnostics Gate Report")
    parser.add_argument("--json", action="store_true", help="Emit ONLY valid JSON to stdout")
    parser.add_argument("--check", action="store_true", help="Exit 0 if PASS, 1 if REVIEW")
    parser.add_argument("--test-manifest", type=str, help="Path to override manifest for safe testing seam")
    args = parser.parse_args()

    gate_status, totals = generate_report(json_mode=args.json, test_manifest=args.test_manifest)

    if args.check:
        if gate_status == "PASS":
            sys.exit(0)
        else:
            sys.exit(1)
