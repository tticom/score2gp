"""Manual OMIT-03 mutation/reachability probe; no synthetic domain evidence.

Run with the product Python:
    python tests/omit_03_label_probe.py suite
    python tests/omit_03_label_probe.py survey
    python tests/omit_03_label_probe.py compare --base <pre-task-commit>

The suite command runs the existing public/private label tests against isolated
package copies. The survey uses every mounted private PDF, without references.
It prints counts, codes and corpus indices only. Extraction artifacts stay in
ignored work/. A compiler refusal is recorded, never replaced by an invented
score. A surviving mutant is a residual, not an acceptance success.
"""

from __future__ import annotations

import argparse
from collections import Counter
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work/omit-03-fu1"
MUTANTS = {
    "band": ("_ANNOTATION_BAND_STAFF_SPACES = 5",
             "_ANNOTATION_BAND_STAFF_SPACES = 7"),
    "system": ("len(near) != 1", "len(near) < 1"),
    "bar": ("len(matching) != 1", "len(matching) < 1"),
    "margin": ("_BEAT_DISTANCE_MARGIN_PT = 2",
               "_BEAT_DISTANCE_MARGIN_PT = 0.5"),
    "status": ('if event.get("status") == "read":', "if True:"),
}


def mutate(source: str, name: str) -> str:
    old, new = MUTANTS[name]
    if source.count(old) != 1:
        raise ValueError(f"mutation site drift: {name}")
    return source.replace(old, new)


def suite_worker(name: str) -> int:
    """Keep mutations active even in CLI children that replace PYTHONPATH."""
    shadow = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=OUT)) / "src"
    shutil.copytree(ROOT / "src/score2gp", shadow / "score2gp",
                    dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    target = shadow / "score2gp/pdf_text_labels.py"
    if name != "baseline":
        target.write_text(mutate(target.read_text(encoding="utf-8"), name), encoding="utf-8")
    sys.path.insert(0, str(shadow))
    import score2gp.pdf_text_labels as labels

    assert Path(labels.__file__).resolve() == target.resolve()
    real_run = subprocess.run

    def run(*args, **kwargs):
        env = dict(kwargs.get("env", os.environ))
        env["PYTHONPATH"] = str(shadow) + os.pathsep + env.get("PYTHONPATH", "")
        return real_run(*args, **{**kwargs, "env": env})

    subprocess.run = run
    os.environ["SCORE2GP_REQUIRE_PRIVATE_CORPUS"] = "1"
    import pytest

    return pytest.main([
        "-q", "tests/test_omit_03_public.py", "tests/test_omit_03_private.py",
        "tests/test_omit_03_fu3_private.py",
        "--basetemp", str(ROOT.parent / ".tmp" / f"omit03-fu1-{name}"),
        "--junitxml", str(OUT / f"suite-{name}.xml"),
    ])


def observe_attachment(labels, pdf, durations, score):
    """Observe locals at production guards; fail on source drift, not silently zero.

    This tracing is test infrastructure for measuring reachability. It provides
    no independent oracle for the correctness of the recognition or geometry.
    """
    markers = {
        "system": (labels._locate_bar, "if len(near) != 1:"),
        "bar": (labels._locate_bar, "if len(matching) != 1:"),
        "available": (labels._choose_beat, "if target_bar is None or not target_bar.events"),
        "margin": (labels._choose_beat, "if not ranked or (len(ranked) > 1"),
    }
    sites = {}
    for name, (function, marker) in markers.items():
        lines, start = inspect.getsourcelines(function)
        matches = [start + i for i, line in enumerate(lines) if line.strip().startswith(marker)]
        if len(matches) != 1:
            raise ValueError(f"observer site drift: {name}")
        sites[function.__code__, matches[0]] = name
    counts = Counter()
    gaps = []
    nonread_bars = {int(event["bar_index"]) for event in durations["events"]
                    if event.get("status") != "read"}

    def trace(frame, event, arg):
        if event == "line":
            site = sites.get((frame.f_code, frame.f_lineno))
            local = frame.f_locals
            if site == "system":
                counts["label_candidates"] += 1
                counts[f"system_matches_{len(local['near'])}"] += 1
            elif site == "bar":
                counts[f"bar_matches_{len(local['matching'])}"] += 1
            elif site == "available":
                has_nonread = frame.f_back.f_locals["source_bar"] in nonread_bars
                counts["candidate_visits_with_nonread_events"] += has_nonread
                target = local["target_bar"]
                available = bool(target and target.events
                                 and len(target.events) == len(local["source_events"]))
                counts["available_candidate_visits_with_nonread_events"] += has_nonread and available
            elif site == "margin":
                counts["ranked_candidates"] += 1
                ranked = local["ranked"]
                if len(ranked) > 1:
                    gap = ranked[1][0] - ranked[0][0]
                    gaps.append(gap)
                    counts["margin_changed_interval"] += 0.5 <= gap < 2
        return trace

    previous = sys.gettrace()
    sys.settrace(trace)
    try:
        result = labels.attach_pdf_text_labels(pdf, durations, score)
    finally:
        sys.settrace(previous)
    return result, dict(counts), min(gaps, default=None)


def survey_one(pdf: Path, index: int) -> dict:
    from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_tabraw_only
    from score2gp.notation_omr.note_duration import read_note_durations
    from score2gp.pdf import extract_tab, inspect_pdf, read_notation_barline_signals
    from score2gp.pdf_resource_budget import INSPECTION_BUDGET_CODE, PdfInspectionResourceLimit
    from score2gp.tabraw import TabRaw
    import score2gp.pdf_text_labels as labels
    import pymupdf

    directory = OUT / "survey" / str(index)
    directory.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf) as document:
        pages = len(document)
    record = {"index": index, "pages": pages, "label_stage_reached": False}
    try:
        inspection = inspect_pdf(pdf, directory / "inspect")
    except PdfInspectionResourceLimit as exc:
        return {**record, "inspection_refusal": INSPECTION_BUDGET_CODE,
                "inspection_page_nodes": exc.count, "page_index": exc.page_index}
    tabfile = directory / "tab.json"
    extract_tab(pdf, tabfile, inspection=inspection, diagnostic_artifacts=False)
    durations = read_note_durations(pdf, time_signature=(4, 4))
    record.update({"systems": len(durations["systems"]),
              "source_events": len(durations["events"]),
              "nonread_events": sum(e.get("status") != "read" for e in durations["events"])})
    tabraw = TabRaw.from_json_file(tabfile)
    tabraw.structural_signals["notation_barlines"] = read_notation_barline_signals(pdf, durations)
    tabraw.to_json_file(tabfile)
    try:
        score, _ = build_ir_from_tabraw_only(tabfile, note_durations=durations)
    except BuildIrInputRiskError as exc:
        return {**record, "compiler_refusal": exc.category, "label_stage_reached": False}

    record["label_stage_reached"] = True
    baseline_score = score.model_copy(deep=True)
    baseline, counts, gap = observe_attachment(labels, pdf, durations, baseline_score)
    record.update({"counts": counts, "min_gap": gap, "baseline_counts": baseline["counts_by_reason"]})
    source = Path(labels.__file__).read_text(encoding="utf-8")
    comparisons = {}
    for name in MUTANTS:
        namespace = dict(labels.__dict__)
        exec(compile(mutate(source, name), labels.__file__, "exec"), namespace)
        mutant_score = score.model_copy(deep=True)
        result = namespace["attach_pdf_text_labels"](pdf, durations, mutant_score)
        comparisons[name] = {
            "decision_changes": sum(a != b for a, b in zip(baseline["decisions"], result["decisions"], strict=True)),
            "score_changed": baseline_score != mutant_score,
        }
    return {**record, "mutants": comparisons}


def summarize(records: list[dict]) -> dict:
    reached = [record for record in records if record["label_stage_reached"]]
    guards = Counter()
    for record in reached:
        guards.update(record["counts"])
    gaps = [record["min_gap"] for record in reached if record["min_gap"] is not None]
    return {
        "sources": len(records),
        "pages": sum(record["pages"] for record in records),
        "label_stage_reached": len(reached),
        "compiler_refused": sum("compiler_refusal" in record for record in records),
        "inspection_refused": sum("inspection_refusal" in record for record in records),
        "source_events": sum(record.get("source_events", 0) for record in records),
        "nonread_events": sum(record.get("nonread_events", 0) for record in records),
        "guard_counts": dict(guards),
        "system_overlap_candidates": sum(value for key, value in guards.items()
                                         if key.startswith("system_matches_") and int(key.rsplit("_", 1)[1]) > 1),
        "bar_overlap_candidates": sum(value for key, value in guards.items()
                                      if key.startswith("bar_matches_") and int(key.rsplit("_", 1)[1]) > 1),
        "margin_changed_interval": guards["margin_changed_interval"],
        "min_gap": min(gaps, default=None),
        "mutants": {name: {
            "sources_with_decision_changes": sum(bool(record["mutants"][name]["decision_changes"])
                                                 for record in reached),
            "sources_with_score_changes": sum(record["mutants"][name]["score_changed"]
                                              for record in reached),
        } for name in MUTANTS},
    }


def compare_baseline(base: str) -> int:
    """Recheck exact decisions and ScoreIR against the frozen pre-task label code."""
    from score2gp.build_ir import build_ir_from_tabraw_only
    from score2gp.notation_omr.note_duration import read_note_durations
    import score2gp.pdf_text_labels as labels

    source = subprocess.run(["git", "show", f"{base}:src/score2gp/pdf_text_labels.py"],
                            cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    namespace = dict(labels.__dict__)
    exec(compile(source, "baseline-pdf_text_labels.py", "exec"), namespace)
    sources = sorted((ROOT / "fixtures/private").glob("*.pdf"))
    summary = json.loads((OUT / "survey-summary.json").read_text())
    if not sources or summary["sources"] != len(sources):
        raise ValueError("a complete survey is required before comparison")
    counts = Counter(sources=len(sources))
    for index, pdf in enumerate(sources):
        directory = OUT / "survey" / str(index)
        record = json.loads((directory / "summary.json").read_text())
        if not record["label_stage_reached"]:
            counts["upstream_refused"] += 1
            continue
        durations = read_note_durations(pdf, time_signature=(4, 4))
        score, _ = build_ir_from_tabraw_only(directory / "tab.json", note_durations=durations)
        baseline_score = score.model_copy(deep=True)
        expected = namespace["attach_pdf_text_labels"](pdf, durations, baseline_score)
        actual = labels.attach_pdf_text_labels(pdf, durations, score)
        counts["label_stage_compared"] += 1
        counts["decision_changes"] += actual != expected
        counts["score_changes"] += score != baseline_score
    (OUT / "before-after.json").write_text(json.dumps(dict(counts), indent=2) + "\n")
    print(json.dumps(dict(counts)), flush=True)
    return int(bool(counts["decision_changes"] or counts["score_changes"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("suite", "survey", "compare", "worker"))
    parser.add_argument("--mutant", choices=("baseline", *MUTANTS))
    parser.add_argument("--base", default="HEAD", help="frozen product revision for compare")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == "worker":
        if args.mutant is None:
            parser.error("worker requires --mutant")
        return suite_worker(args.mutant)
    if args.mode == "suite":
        infrastructure_failed = False
        for name in ("baseline", *MUTANTS):
            log = OUT / f"suite-{name}.log"
            junit = OUT / f"suite-{name}.xml"
            junit.unlink(missing_ok=True)
            with log.open("w", encoding="utf-8") as stream:
                result = subprocess.run([sys.executable, __file__, "worker", "--mutant", name],
                                        cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            totals = {}
            if junit.exists():
                suites = list(ElementTree.parse(junit).getroot().iter("testsuite"))
                totals = {key: sum(int(s.get(key, 0)) for s in suites)
                          for key in ("tests", "failures", "errors", "skipped")}
            infrastructure_failed |= (result.returncode not in (0, 1)
                                      or (name == "baseline" and result.returncode != 0)
                                      or not totals or bool(totals.get("errors") or totals.get("skipped")))
            print(json.dumps({"mutant": name, "exit_code": result.returncode, **totals,
                              "summary": log.read_text(encoding="utf-8").splitlines()[-1:]}), flush=True)
        # Survival is data, not a successful mutation kill. Consult each exit code.
        return int(infrastructure_failed)
    sys.path.insert(0, str(ROOT / "src"))
    if args.mode == "compare":
        return compare_baseline(args.base)
    sources = sorted((ROOT / "fixtures/private").glob("*.pdf"))
    if not sources:
        parser.error("private PDF corpus absent")
    records = []
    for index, pdf in enumerate(sources):
        record = survey_one(pdf, index)
        records.append(record)
        (OUT / "survey" / str(index) / "summary.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record), flush=True)
    summary = summarize(records)
    (OUT / "survey-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"summary": summary}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
