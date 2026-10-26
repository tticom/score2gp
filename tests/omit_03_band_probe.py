"""OMIT-03-FU3 real-source survey and isolated mutation receipts.

Run `python tests/omit_03_band_probe.py survey`, `... compare`, or `... mutants`.
The survey measures the PDF line's bottom edge against each notation staff's
top line, using the production staff detector and rounding. It counts only
lines whose left edge meets the existing horizontal annotation gate. No GP
reference is opened. Indices address the sorted mounted PDF corpus; output
contains counts, distances, indices and refusal/candidate role codes only.
`pdf_text_label` here means a classifier candidate, not a proved source role.
In particular a source running title and an extended technique instruction
survive that classifier; this survey does not authorise a wider band.
"""

from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work/omit-03-fu3"
MUTANTS = {
    "drop_rotated_reason": ('return "pdf_text_rotated_text"',
                            'return "pdf_text_outside_annotation_band"'),
    "widen_without_role_rule": ("gap <= 5 * spacing", "gap <= 7 * spacing"),
}


def survey() -> int:
    import pymupdf
    from score2gp.notation_omr.note_duration import extract_page_symbols, find_staves
    from score2gp.pdf_text_labels import _classify

    sources = sorted((ROOT / "fixtures/private").glob("*.pdf"))
    if not sources:
        raise RuntimeError("private corpus absent")
    records = []
    for index, pdf in enumerate(sources):
        rows = []
        systems = 0
        with pymupdf.open(pdf) as document:
            for page_index, page in enumerate(document):
                notation, _ = find_staves(extract_page_symbols(page, page_index))
                systems += len(notation)
                for block_index, block in enumerate(page.get_text("dict")["blocks"]):
                    for line_index, line in enumerate(block.get("lines", [])):
                        spans = line["spans"]
                        text = "".join(s["text"] for s in spans).strip()
                        if not text:
                            continue
                        x0, _, _, y1 = line["bbox"]
                        for system_index, staff in enumerate(sorted(notation, key=lambda s: s.top)):
                            distance = (round(staff.top, 3) - y1) / round(staff.space, 4)
                            if (5 < distance <= 7
                                    and round(staff.x0, 3) - 5 <= x0 <= round(staff.x1, 3)):
                                rows.append({
                                    "page_index": page_index, "block_index": block_index,
                                    "line_index": line_index, "system_index": system_index,
                                    "distance_spaces": round(distance, 4),
                                    "candidate_role_code": _classify(
                                        text, spans[0]["font"], max(s["size"] for s in spans), True),
                                })
            records.append({"source_index": index, "pages": len(document),
                            "systems": systems, "count": len(rows), "lines": rows})
        print(json.dumps({"source_index": index, "count": len(rows)}), flush=True)
    result = {"sources": len(sources), "lines": sum(r["count"] for r in records),
              "counts_by_candidate_role": dict(Counter(
                  line["candidate_role_code"] for r in records for line in r["lines"])),
              "records": records}
    (OUT / "band-survey.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}), flush=True)
    return 0


def worker(name: str) -> int:
    shadow = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=OUT)) / "src"
    shutil.copytree(ROOT / "src/score2gp", shadow / "score2gp",
                    ignore=shutil.ignore_patterns("__pycache__"))
    target = shadow / "score2gp/pdf_text_labels.py"
    source = target.read_text(encoding="utf-8")
    if name != "baseline":
        old, new = MUTANTS[name]
        if source.count(old) != 1:
            raise RuntimeError(f"mutation site drift: {name}")
        target.write_text(source.replace(old, new), encoding="utf-8")
    # CLI acceptance tests set PYTHONPATH explicitly: keep the isolated package
    # first in their children too, as in omit_03_label_probe.py.
    sys.path.insert(0, str(shadow))
    import score2gp.pdf_text_labels as labels
    assert Path(labels.__file__).resolve() == target.resolve()
    real_run = subprocess.run

    def run(*args, **kwargs):
        env = dict(kwargs.get("env", os.environ))
        env["PYTHONPATH"] = str(shadow) + os.pathsep + env.get("PYTHONPATH", "")
        return real_run(*args, **{**kwargs, "env": env})

    subprocess.run = run
    import pytest
    return pytest.main([
        "-q", "tests/test_omit_03_fu3_private.py",
        "--basetemp", str(ROOT.parent / ".tmp" / f"o3f3-{name}"),
        "--junitxml", str(OUT / f"mutant-{name}.xml"),
    ])


def mutants() -> int:
    receipts = []
    for name in ("baseline", *MUTANTS):
        log = OUT / f"mutant-{name}.log"
        junit = OUT / f"mutant-{name}.xml"
        junit.unlink(missing_ok=True)
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([sys.executable, __file__, "worker", name],
                                    cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        suites = list(ElementTree.parse(junit).getroot().iter("testsuite"))
        receipt = {"name": name, "exit_code": result.returncode,
                   **{key: sum(int(s.get(key, 0)) for s in suites)
                      for key in ("tests", "failures", "errors", "skipped")}}
        receipts.append(receipt)
        print(json.dumps(receipt), flush=True)
    (OUT / "mutants.json").write_text(json.dumps(receipts, indent=2) + "\n")
    return int(any(r["tests"] != 1 or r["errors"] or r["skipped"]
                   or r["exit_code"] != (0 if r["name"] == "baseline" else 1)
                   or r["failures"] != (0 if r["name"] == "baseline" else 1)
                   for r in receipts))


def compare() -> int:
    """Census classifier changes against the exact pre-task implementation.

    This is a code-path preservation check, not a musical-fidelity oracle.
    A changed label candidate is a failure even if attachment might refuse it.
    """
    import pymupdf
    import score2gp.pdf_text_labels as labels
    from score2gp.notation_omr.note_duration import extract_page_symbols, find_staves

    base = "dab4d67cd642dc0a34d08bcb148a8b9630482a39"
    source = subprocess.run(["git", "show", f"{base}:src/score2gp/pdf_text_labels.py"],
                            cwd=ROOT, check=True, capture_output=True,
                            text=True, encoding="utf-8").stdout
    namespace = dict(labels.__dict__)
    exec(compile(source, "baseline-pdf_text_labels.py", "exec"), namespace)
    records = []
    for index, pdf in enumerate(sorted((ROOT / "fixtures/private").glob("*.pdf"))):
        counts = Counter()
        transitions = Counter()
        with pymupdf.open(pdf) as document:
            for page_index, page in enumerate(document):
                notation, _ = find_staves(extract_page_symbols(page, page_index))
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        spans = line["spans"]
                        text = "".join(s["text"] for s in spans).strip()
                        if not text:
                            continue
                        x0, _, _, y1 = line["bbox"]
                        near = any(0 <= round(s.top, 3) - y1 <= 5 * round(s.space, 4)
                                   and round(s.x0, 3) - 5 <= x0 <= round(s.x1, 3)
                                   for s in notation)
                        args = (text, spans[0]["font"], max(s["size"] for s in spans), near)
                        before = namespace["_classify"](*args)
                        after = labels._classify(*args, direction=tuple(line["dir"]))
                        counts["lines"] += 1
                        if before != after:
                            transitions[f"{before}->{after}"] += 1
                            counts["changed_label_candidates"] += (
                                "pdf_text_label" in (before, after))
        records.append({"source_index": index, "lines": counts["lines"],
                        "changed_label_candidates": counts["changed_label_candidates"],
                        "transitions": dict(transitions)})
    if not records:
        raise RuntimeError("private corpus absent")
    result = {"base": base, "sources": len(records),
              "lines": sum(r["lines"] for r in records),
              "changed_label_candidates": sum(r.get("changed_label_candidates", 0) for r in records),
              "records": records}
    (OUT / "classification-comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return int(bool(result["changed_label_candidates"]))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else "survey"
    if mode == "survey":
        raise SystemExit(survey())
    if mode == "mutants":
        raise SystemExit(mutants())
    if mode == "compare":
        raise SystemExit(compare())
    if mode == "worker" and len(sys.argv) == 3:
        raise SystemExit(worker(sys.argv[2]))
    raise SystemExit("expected survey, compare, mutants, or worker <mutant>")
