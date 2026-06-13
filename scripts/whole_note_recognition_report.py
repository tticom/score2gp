#!/usr/bin/env python3
"""
Product-facing report surface for read-only whole-note recognition outcomes.
Consumes diagnostic candidate evidence and formats it into deterministic JSON.
"""
import sys
import argparse
import json
from pathlib import Path

from score2gp.whole_note_recogniser import run_recognition_on_file

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
