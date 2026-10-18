"""Measure production GPIF bytes outside pytest on every mounted private PDF.

Run from the product checkout at each revision, using this same probe:
    .venv/Scripts/python.exe tests/gpif_layout_corpus_probe.py --out work/gpif-hashes.json

Indices follow sorted PDF filenames. Reports contain no private score content.
Refusals remain refusals; a missing output is never counted as byte equality.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from zipfile import ZipFile


def measure(root, item, time_signature=None):
    index, pdf = item
    with TemporaryDirectory(prefix="gpif-layout-", dir=root / "work") as directory:
        scratch = Path(directory)
        output = scratch / "output.gp"
        command = [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
                   "--pdf-only-tab", "--out", str(output),
                   "--work-dir", str(scratch / "conversion")]
        if time_signature is not None:
            command.extend(["--time-signature", time_signature])
        start = time.monotonic()
        result = subprocess.run(command, capture_output=True,
                                env={**os.environ, "PYTHONPATH": str(root / "src")})
        row = {"index": index, "exit_code": result.returncode,
               "seconds": round(time.monotonic() - start, 3), "gpif_sha256": None}
        if output.is_file():
            with ZipFile(output) as package:
                data = package.read("Content/score.gpif")
            row.update(gpif_sha256=hashlib.sha256(data).hexdigest(), gpif_bytes=len(data))
        return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--time-signature", help="Optional declaration passed unchanged to the CLI")
    args = parser.parse_args()
    root = Path.cwd()
    sources = sorted((root / "fixtures/private").glob("*.pdf"))
    if not sources:
        parser.error("private PDF corpus is not mounted")
    (root / "work").mkdir(exist_ok=True)
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(measure, root, item, args.time_signature) for item in enumerate(sources, 1)]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(row["index"], row["exit_code"], row["gpif_sha256"], flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(sorted(rows, key=lambda row: row["index"]), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
