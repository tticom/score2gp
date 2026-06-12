#!/usr/bin/env python3
"""
Whole-note candidate diagnostic report script.
Extracts whole-note candidates from vector paths using geometric properties
(aspect ratio and curve counts) without performing semantic ScoreIR emission
or full note/rhythm inference.
"""
import sys
import argparse
import json
from pathlib import Path

import fitz  # type: ignore

def build_whole_note_diagnostics(page: fitz.Page, page_index: int) -> dict:
    from score2gp.pdf_staff_notation_diagnostics import _extract_whole_note_candidates
    candidates_objs = _extract_whole_note_candidates(page)
    candidates = []
    for c in candidates_objs:
        candidates.append({
            "kind": "whole_note_candidate",
            "bbox": c.bbox,
            "width": c.width,
            "height": c.height,
            "aspect_ratio": c.aspect_ratio
        })

    return {
        "kind": "whole_note_diagnostics",
        "page_index": page_index,
        "whole_note_candidate_count": len(candidates),
        "candidates": candidates
    }

def run_diagnostics_on_file(pdf_path: Path):
    if not pdf_path.exists():
        return None

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening {pdf_path.name}: {e}", file=sys.stderr)
        return None

    total_candidates = 0
    all_pages = []

    for i in range(len(doc)):
        page = doc[i]
        diags = build_whole_note_diagnostics(page, page_index=i + 1)
        total_candidates += diags["whole_note_candidate_count"]
        all_pages.append(diags)

    return {
        "status": "success",
        "total_whole_note_candidates": total_candidates,
        "pages": all_pages
    }

def main():
    parser = argparse.ArgumentParser(description="Whole Note Candidate Diagnostics Report")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF fixture")
    args = parser.parse_args()

    res = run_diagnostics_on_file(Path(args.pdf_path))
    if not res:
        sys.exit(1)

    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
