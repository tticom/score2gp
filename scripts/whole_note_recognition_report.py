#!/usr/bin/env python3
"""
Product-facing report surface for read-only whole-note recognition outcomes.
Consumes diagnostic candidate evidence and formats it into deterministic JSON.
"""
import sys
import argparse
import json
from pathlib import Path

import fitz  # type: ignore

from score2gp.pdf_staff_notation_diagnostics import _extract_whole_note_candidates
from score2gp.whole_note_recogniser import map_whole_note_candidates_to_read_only_outcomes

def run_recognition_on_file(pdf_path: Path):
    if not pdf_path.exists():
        print(f"Error: File {pdf_path} not found", file=sys.stderr)
        return None

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening {pdf_path.name}: {e}", file=sys.stderr)
        return None

    whole_note_locations = []

    for i in range(len(doc)):
        page = doc[i]
        page_index = i + 1
        candidates_objs = _extract_whole_note_candidates(page)
        
        # Sort geometrically: top, left, bottom, right
        candidates_objs.sort(key=lambda c: (c.bbox[1], c.bbox[0], c.bbox[3], c.bbox[2]))

        for cand in candidates_objs:
            candidate_id = f"whole_note_candidate_{len(whole_note_locations) + 1:03d}"
            whole_note_locations.append({
                "candidate_id": candidate_id,
                "page_index": page_index,
                "bbox": cand.bbox
            })

    outcomes = map_whole_note_candidates_to_read_only_outcomes(whole_note_locations)

    return {
        "source": pdf_path.name,
        "recognition_mode": "read_only_diagnostic_derived",
        "read_only_recognition_outcomes": outcomes
    }

def main():
    parser = argparse.ArgumentParser(description="Read-Only Whole-Note Recognition Report")
    parser.add_argument("--pdf", type=str, default="tests/fixtures/pdf/generated_standard_staff_whole_note.pdf", help="Path to the PDF fixture")
    parser.add_argument("--json", action="store_true", help="Output machine-checkable JSON")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    res = run_recognition_on_file(pdf_path)
    if not res:
        sys.exit(1)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        # Default behaviour if JSON is not explicitly requested, though prompt says "Keep JSON output simple and deterministic"
        print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
