#!/usr/bin/env python3
import sys
from pathlib import Path

import fitz

from score2gp.pdf_raster_staff_diagnostics import (
    build_raster_notation_diagnostics,
    summarize_raster_treble_clef_diagnostics,
)


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
    total_unknowns = 0

    for i in range(len(doc)):
        page = doc[i]
        diags = build_raster_notation_diagnostics(page, page_index=i + 1, scale=2.0)
        summary = summarize_raster_treble_clef_diagnostics(diags)

        if summary.get("status") == "success":
            total_staff_count += summary.get("staff_count", 0)
            counts = summary.get("label_counts", {})
            total_treble_candidates += counts.get("treble_clef_candidate", 0)
            total_unknowns += counts.get("unknown", 0)

    return {
        "staff_count": total_staff_count,
        "treble_clef_candidate": total_treble_candidates,
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

def generate_report():
    manifest = [
        {
            "path": "tests/fixtures/pdf/generated_standard_staff_negative_blank.pdf",
            "category": "negative_blank",
            "expected_positive": False,
        },
        {
            "path": "tests/fixtures/pdf/generated_standard_staff_negative_tab.pdf",
            "category": "negative_tab",
            "expected_positive": False,
        },
        {
            "path": "tests/fixtures/pdf/generated_standard_staff_negative_noise.pdf",
            "category": "negative_noise",
            "expected_positive": False,
        },
    ]

    # Load false negative manifest first
    fn_manifest_path = Path("tests/fixtures/raster_diagnostics_false_negative_manifest.json")
    expected_fns = {}  # sha256 -> case_id
    if fn_manifest_path.exists():
        try:
            with open(fn_manifest_path, "r") as f:
                data = json.load(f)
                for entry in data.get("false_negative_cases", []):
                    case_id = entry.get("case_id")
                    file_sha256 = entry.get("file_sha256")
                    if case_id and file_sha256:
                        expected_fns[file_sha256] = case_id
        except Exception as e:
            print(f"Warning: Could not load false negative manifest: {e}", file=sys.stderr)

    found_case_ids = set()
    private_dir = Path("fixtures/private/raster-treble-clef")
    if private_dir.exists():
        for p in private_dir.glob("*.pdf"):
            h = compute_sha256(p)
            if h in expected_fns:
                case_id = expected_fns[h]
                manifest.append({
                    "path": str(p),
                    "category": "positive_private",
                    "expected_positive": True,
                    "case_id": case_id
                })
                found_case_ids.add(case_id)

    # Add dummy entries for missing private fixtures so they are reported as skipped
    for file_sha256, case_id in expected_fns.items():
        if case_id not in found_case_ids:
            manifest.append({
                "path": f"missing_private_fixture_{case_id}.pdf",
                "category": "positive_private",
                "expected_positive": True,
                "case_id": case_id
            })

    results = {
        "negative_blank": {"cases_run": 0, "false_positives": 0, "unknowns": 0},
        "negative_tab": {"cases_run": 0, "false_positives": 0, "unknowns": 0},
        "negative_noise": {"cases_run": 0, "false_positives": 0, "unknowns": 0},
        "positive_private": {"cases_run": 0, "false_negatives": 0, "unknowns": 0},
    }

    totals = {
        "false_positives": 0,
        "false_negatives": 0,
        "unknowns": 0,
        "total_staves": 0,
        "total_pages": 0,
        "total_cases_inspected": 0,
    }

    print("Raster Diagnostics Gate Report")
    print("=" * 60)

    for item in manifest:
        p = Path(item["path"])
        if not p.exists():
            if item["category"] == "positive_private":
                display = item.get("case_id", "anonymised_private_fixture")
                print(f"Skipping missing optional private fixture: {display}")
            else:
                print(f"Warning: Expected fixture missing: {p.name}", file=sys.stderr)
            continue

        display_name = item.get("case_id", "anonymised_private_fixture") if item["category"] == "positive_private" else p.name
        res = run_diagnostics_on_file(p, display_label=display_name)
        if not res:
            print(f"Error processing {display_name}", file=sys.stderr)
            continue

        cat = item["category"]
        results[cat]["cases_run"] += 1
        results[cat]["unknowns"] += res["unknown"]

        totals["total_cases_inspected"] += 1
        totals["total_pages"] += res["pages"]
        totals["total_staves"] += res["staff_count"]
        totals["unknowns"] += res["unknown"]

        is_fn = False
        if item["expected_positive"]:
            if res["treble_clef_candidate"] == 0:
                is_fn = True
                results[cat]["false_negatives"] += 1
                totals["false_negatives"] += 1
        else:
            if res["treble_clef_candidate"] > 0:
                results[cat]["false_positives"] += res["treble_clef_candidate"]
                totals["false_positives"] += res["treble_clef_candidate"]

        print(f"Processed: {display_name} [{cat}]")
        print(f"  Pages: {res['pages']}")
        print(f"  Staves Detected: {res['staff_count']}")
        print(f"  Treble Candidates: {res['treble_clef_candidate']}")
        print(f"  Unknowns: {res['unknown']}")

        if is_fn:
            case_id = item.get("case_id", display_name)
            if case_id in found_case_ids:
                print(f"  -> MATCHED KNOWN FALSE NEGATIVE MANIFEST ENTRY: {case_id}")
            else:
                print(f"  -> UNEXPECTED FALSE NEGATIVE: {case_id}")

        print("-" * 60)

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
    print(f"  Total Cases Inspected : {totals['total_cases_inspected']}")
    print(f"  Total Pages Inspected : {totals['total_pages']}")
    print(f"  Total Staves Detected : {totals['total_staves']}")
    print(f"  Total False Positives : {totals['false_positives']}")
    print(f"  Total False Negatives : {totals['false_negatives']}")
    print(f"  Total Unknowns        : {totals['unknowns']}")

    return totals


if __name__ == "__main__":
    generate_report()
