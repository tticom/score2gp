#!/usr/bin/env python3
"""
Product-facing report surface for read-only generic note-candidate recognition outcomes.
Consumes diagnostic candidate evidence and formats it into deterministic JSON.
"""
import sys
import argparse
import json
from pathlib import Path

# Make the script runnable from source checkouts
src_path = Path(__file__).resolve().parent.parent / "src"
if src_path.is_dir() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from score2gp.whole_note_recogniser import run_recognition_on_file

def main():
    parser = argparse.ArgumentParser(description="Read-Only Note-Candidate Recognition Report")
    parser.add_argument("--pdf", type=str, default="tests/fixtures/pdf/generated_standard_staff_whole_note.pdf", help="Path to the PDF fixture")
    parser.add_argument("--json", action="store_true", help="Output machine-checkable JSON")
    parser.add_argument("--assume-treble-clef", action="store_true", help="Explicit opt-in to map read-only pitch using an assumed treble clef")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    res = run_recognition_on_file(
        pdf_path,
        include_x_aligned_clusters=True,
        include_left_margin_candidates=True,
        include_flag_beam_candidates=True,
        assume_treble_clef=args.assume_treble_clef,
        include_ledger_line_candidates=True
    )
    if not res:
        sys.exit(1)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        # Default behaviour if JSON is not explicitly requested, though prompt says "Keep JSON output simple and deterministic"
        print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
