#!/usr/bin/env python3
"""
Diagnostic analysis script for Product Task 170.
Runs the clef_resolved_pitch_coverage report over the authorized public fixture corpus
and writes an aggregate summary markdown report.
"""

import sys
import json
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent / "src"
if src_path.is_dir() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from score2gp.whole_note_recogniser import run_recognition_on_file

def main():
    repo_root = Path(__file__).resolve().parent.parent
    fixtures_dir = repo_root / "tests" / "fixtures" / "pdf"
    
    if not fixtures_dir.exists():
        print(f"Error: Fixtures dir {fixtures_dir} not found.")
        sys.exit(1)

    pdf_files = sorted([f for f in fixtures_dir.glob("*.pdf") if "generated" in f.name])
    
    aggregate = {
        "total_note_candidates_in_scope": 0,
        "note_candidates_with_staff_position_index": 0,
        "note_candidates_on_staves_with_valid_clef": 0,
        "note_candidates_with_clef_resolved_staff_pitch": 0,
        "in_staff_mapped_notes": 0,
        "out_of_staff_mapped_notes": 0,
        "skipped_missing_required_ledger_support": 0,
        "skipped_clef_missing": 0,
        "skipped_clef_ambiguous": 0,
        "skipped_staff_association_malformed": 0,
        "skipped_staff_position_malformed": 0,
        "pitch_out_of_range_or_unsupported": 0,
    }

    files_processed = 0

    print(f"Running clef-resolved pitch coverage analysis on {len(pdf_files)} fixtures...")

    for pdf in pdf_files:
        res = run_recognition_on_file(
            pdf,
            include_x_aligned_clusters=True,
            include_left_margin_candidates=True,
            include_flag_beam_candidates=True,
            assume_treble_clef=False,
            include_ledger_line_candidates=True
        )
        if not res or "clef_resolved_pitch_coverage" not in res:
            continue
        
        files_processed += 1
        cov = res["clef_resolved_pitch_coverage"]
        for k in aggregate:
            if k in cov:
                aggregate[k] += cov[k]
                
        # Derive out-of-range metric if present in samples
        for sample in cov.get("sample_diagnostics", []):
            if sample.get("skip_reason") == "pitch_out_of_range_or_unsupported":
                aggregate["pitch_out_of_range_or_unsupported"] += 1

    report_dir = repo_root / "reports" / "clef_resolved_pitch_coverage"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "2026-06-16-authorised-fixture-summary.md"

    total_candidates = aggregate["total_note_candidates_in_scope"]
    
    missing_clef = aggregate["skipped_clef_missing"]
    missing_ledger = aggregate["skipped_missing_required_ledger_support"]
    
    if missing_clef > missing_ledger and missing_clef > aggregate["skipped_clef_ambiguous"]:
        dominant_blocker = "missing clef evidence"
        recommendation = "Product Task 171 should bridge logical clef candidate evidence to fill in missing clefs."
    elif missing_ledger > missing_clef:
        dominant_blocker = "missing ledger support"
        recommendation = "Product Task 171 should improve ledger line extraction or matching."
    else:
        dominant_blocker = "missing clef evidence"
        recommendation = "Product Task 171 should bridge logical clef candidate evidence to fill in missing clefs."

    md_content = f"""# Clef-Resolved Pitch Coverage Analysis (2026-06-16)

## Corpus
- **Files processed:** {files_processed} public fixtures from `tests/fixtures/pdf/`
- **Safety:** All files are anonymised generated public fixtures. No private PDFs, no copyrighted source names, no raw OCR dumps or sensitive data included.

## Aggregate Findings

| Metric | Count |
|--------|-------|
| Total Note Candidates | {aggregate['total_note_candidates_in_scope']} |
| With Staff Position Index | {aggregate['note_candidates_with_staff_position_index']} |
| On Staves with Valid Clef | {aggregate['note_candidates_on_staves_with_valid_clef']} |
| Mapped to Pitch | {aggregate['note_candidates_with_clef_resolved_staff_pitch']} |
| In-Staff Mapped | {aggregate['in_staff_mapped_notes']} |
| Out-of-Staff Mapped | {aggregate['out_of_staff_mapped_notes']} |

### Skip Reasons
| Reason | Count |
|--------|-------|
| Missing Clef Evidence | {aggregate['skipped_clef_missing']} |
| Missing Required Ledger Support | {aggregate['skipped_missing_required_ledger_support']} |
| Ambiguous Clef Evidence | {aggregate['skipped_clef_ambiguous']} |
| Malformed Staff Association | {aggregate['skipped_staff_association_malformed']} |
| Malformed Staff Position | {aggregate['skipped_staff_position_malformed']} |

## Interpretation
The coverage analysis identifies **{dominant_blocker}** as the dominant blocker preventing note candidates from receiving a `clef_resolved_staff_pitch`.

## Recommendation
Based on empirical evidence, the next smallest safe product task is:
**{recommendation}**
"""

    report_file.write_text(md_content, encoding="utf-8")
    print(f"Report written to {report_file}")

if __name__ == "__main__":
    main()
