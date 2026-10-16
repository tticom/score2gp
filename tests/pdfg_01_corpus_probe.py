"""Reproduce PDFG-01's private-safe corpus measurements and GPIF preservation check.

Run at base and head with --out under work; use --baseline on the head run.
--module-root permits measuring an immutable source snapshot without Git writes.
Only counts, labels, codes, timings and hashes leave the temporary conversion tree.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def compare(baseline, current):
    before = {r["file"]: r for r in baseline["files"]}
    after = {r["file"]: r for r in current["files"]}
    assert before.keys() == after.keys(), "corpus membership changed"
    preserved = []
    changes = []
    for name, old in before.items():
        new = after[name]
        if old["gpif_sha256"] is not None:
            assert new["gpif_sha256"] == old["gpif_sha256"], f"written GPIF changed: {name}"
            assert new["exit_code"] == old["exit_code"], f"written source status changed: {name}"
            preserved.append(name)
        if (old["exit_code"], old["code"], old["gpif_sha256"]) != (
                new["exit_code"], new["code"], new["gpif_sha256"]):
            changes.append(name)
    return {"preserved_gpifs": len(preserved), "changed_sources": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--module-root", type=Path, default=ROOT / "src")
    args = parser.parse_args()
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    output = args.out.resolve()
    if not output.is_relative_to(work.resolve()):
        parser.error("--out must be under repository work")
    sources = sorted((ROOT / "fixtures/private").glob("*.pdf"))
    if not sources:
        parser.error("approved private corpus is absent")
    env = {**os.environ, "PYTHONPATH": str(args.module_root.resolve())}
    result = {"files": []}
    output.parent.mkdir(parents=True, exist_ok=True)
    for source in sources:
        start = time.monotonic()
        with TemporaryDirectory(prefix="pdfg01_corpus_", dir=work) as directory:
            scratch = Path(directory)
            run = subprocess.run([
                sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
                "--pdf-only-tab", "--time-signature", "4/4", "--out", str(scratch / "out.gp"),
                "--work-dir", str(scratch / "build"), "--json-report", str(scratch / "report.json"),
            ], env=env, capture_output=True, text=True)
            report = json.loads((scratch / "report.json").read_text(encoding="utf-8"))
            digest = None
            if (scratch / "out.gp").is_file():
                with ZipFile(scratch / "out.gp") as package:
                    digest = hashlib.sha256(package.read("Content/score.gpif")).hexdigest()
            route_path = scratch / "build/note-type-route.json"
            route = json.loads(route_path.read_text(encoding="utf-8")) if route_path.exists() else {}
            summary = route.get("summary", {})
            row = {"file": source.name, "exit_code": run.returncode,
                   "code": report.get("refusal_code"), "gpif_sha256": digest,
                   "source_bars": summary.get("source_bars", 0),
                   "written_bars": summary.get("written_bars", 0),
                   "seconds": round(time.monotonic() - start, 2)}
        result["files"].append(row)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(source.name, row["exit_code"], row["code"], flush=True)
    if args.baseline:
        result["comparison"] = compare(json.loads(args.baseline.read_text(encoding="utf-8")), result)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result["comparison"]))


if __name__ == "__main__":
    main()
