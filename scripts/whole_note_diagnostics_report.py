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
    candidates = []
    drawings = page.get_drawings()

    # Pre-collect vertical lines to detect stems
    vertical_lines = []
    for draw in drawings:
        for item in draw.get("items", []):
            if item[0] == 'l':
                p0, p1 = item[1], item[2]
                dx = abs(p0.x - p1.x)
                dy = abs(p0.y - p1.y)
                if dy >= 5.0 and dx <= 2.0:
                    vertical_lines.append({
                        "x0": min(p0.x, p1.x),
                        "y0": min(p0.y, p1.y),
                        "x1": max(p0.x, p1.x),
                        "y1": max(p0.y, p1.y)
                    })

    for draw in drawings:
        rect = draw.get("rect")
        if not rect:
            continue

        w = rect.width
        h = rect.height
        if h == 0 or w == 0:
            continue

        aspect = w / h

        items = draw.get("items", [])
        c_count = sum(1 for item in items if item[0] == 'c')

        # A whole note candidate typically has an aspect ratio of >1.0 (oval-shaped)
        # and is drawn with bezier curves (often 4 for a full ellipse).
        # We also ensure it is a hollow shape (no fill or explicit stroke).
        if 1.2 <= aspect <= 2.0 and c_count >= 2:
            is_hollow = not draw.get("fill")
            if is_hollow:
                # Check for an attached or adjacent stem
                has_stem = False
                margin_x = 3.0
                margin_y = 5.0
                for line in vertical_lines:
                    near_left = abs(line["x0"] - rect.x0) <= margin_x
                    near_right = abs(line["x0"] - rect.x1) <= margin_x
                    if near_left or near_right:
                        if not (line["y1"] < rect.y0 - margin_y or line["y0"] > rect.y1 + margin_y):
                            has_stem = True
                            break

                if not has_stem:
                    candidates.append({
                        "kind": "whole_note_candidate",
                        "bbox": [round(rect.x0, 3), round(rect.y0, 3), round(rect.x1, 3), round(rect.y1, 3)],
                        "width": round(w, 3),
                        "height": round(h, 3),
                        "aspect_ratio": round(aspect, 3)
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
