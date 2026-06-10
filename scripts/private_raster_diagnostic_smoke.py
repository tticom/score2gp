from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import fitz  # type: ignore[import-not-found]
from score2gp.pdf_raster_staff_diagnostics import build_raster_notation_diagnostics  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run raster-backed staff diagnostics on a PDF."
    )
    parser.add_argument("--pdf", required=True, type=Path, help="PDF input.")
    args = parser.parse_args(argv)

    try:
        doc = fitz.open(args.pdf)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    results = []
    for index, page in enumerate(doc, start=1):
        diags = build_raster_notation_diagnostics(page, page_index=index, scale=2.0)
        results.append(diags)

    print(json.dumps({"pages": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
