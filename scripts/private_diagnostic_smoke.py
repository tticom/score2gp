from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from score2gp.private_diagnostics import run_private_diagnostic_smoke  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a private diagnostic-only PDF -> TabRaw -> optional MusicXML build-ir smoke. "
            "Write detailed outputs under an ignored work directory and print a sanitized summary."
        )
    )
    parser.add_argument("--pdf", required=True, type=Path, help="Private PDF input.")
    parser.add_argument("--musicxml", type=Path, help="Matching private MusicXML/XML/MXL timing input.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Ignored output directory, usually work/private_diagnostics/<name>.")
    args = parser.parse_args(argv)

    summary = run_private_diagnostic_smoke(pdf_path=args.pdf, musicxml_path=args.musicxml, out_dir=args.out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
