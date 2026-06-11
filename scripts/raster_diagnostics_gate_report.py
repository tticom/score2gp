#!/usr/bin/env python3
import sys
from pathlib import Path

import fitz

from score2gp.pdf_raster_staff_diagnostics import (
    build_raster_notation_diagnostics,
    summarize_raster_treble_clef_diagnostics,
)


def run_diagnostics_on_file(pdf_path: Path):
    if not pdf_path.exists():
        return None

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening {pdf_path}: {e}", file=sys.stderr)
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
        {
            "path": "fixtures/private/raster-treble-clef/treble-staff-paper.pdf",
            "category": "positive_private",
            "expected_positive": True,
        },
        {
            "path": "fixtures/private/raster-treble-clef/FlashCardsValues.pdf",
            "category": "positive_private",
            "expected_positive": True,
        },
    ]

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
                print(f"Skipping missing optional private fixture: {p.name}")
            else:
                print(f"Warning: Expected fixture missing: {p.name}", file=sys.stderr)
            continue

        res = run_diagnostics_on_file(p)
        if not res:
            print(f"Error processing {p.name}", file=sys.stderr)
            continue

        cat = item["category"]
        results[cat]["cases_run"] += 1
        results[cat]["unknowns"] += res["unknown"]

        totals["total_cases_inspected"] += 1
        totals["total_pages"] += res["pages"]
        totals["total_staves"] += res["staff_count"]
        totals["unknowns"] += res["unknown"]

        if item["expected_positive"]:
            # If we expect a positive but get none, it's a false negative (for the document)
            # Alternatively, if we expected staves but got no treble clefs on them, count missing.
            # Here we simplify: if expected positive and 0 treble candidates found overall -> false negative
            if res["treble_clef_candidate"] == 0:
                results[cat]["false_negatives"] += 1
                totals["false_negatives"] += 1
        else:
            if res["treble_clef_candidate"] > 0:
                results[cat]["false_positives"] += res["treble_clef_candidate"]
                totals["false_positives"] += res["treble_clef_candidate"]

        print(f"Processed: {p.name} [{cat}]")
        print(f"  Pages: {res['pages']}")
        print(f"  Staves Detected: {res['staff_count']}")
        print(f"  Treble Candidates: {res['treble_clef_candidate']}")
        print(f"  Unknowns: {res['unknown']}")
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
