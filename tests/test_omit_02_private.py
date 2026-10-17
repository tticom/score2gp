"""OMIT-02 acceptance against genuine PDFs and independent GP references.

The private corpus is mounted locally; no source pages or musical data are tracked.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from score2gp.gp_package import compare_gp as compare_package
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf import read_notation_barline_signals


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
ORACLE_PATH = Path(__file__).with_name("test_dur_02_oracle.py")
spec = importlib.util.spec_from_file_location("omit02_gp_oracle", ORACLE_PATH)
assert spec and spec.loader
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


@pytest.mark.parametrize("lesson", [3, 4, 5, 6, 7])
def test_private_lesson_double_bars_agree_per_bar(lesson):
    pdf = PRIVATE / f"Lesson-{lesson}.pdf"
    reference = PRIVATE / f"Lesson-{lesson}.gp"
    if not pdf.exists() or not reference.exists():
        pytest.skip("private lesson corpus absent")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        produced = scratch / "produced.gp"
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(produced),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": os.environ.get("SCORE2GP_OMIT02_MUTANT_SRC", str(ROOT / "src"))},
            text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        comparison = oracle.compare_gp(reference, produced)
        differences = [(d["bar_index"] + 1, d["field"])
                       for d in comparison["differences"] if d["field"] == "double_bar"]
        assert differences == ([(72, "double_bar")] if lesson == 6 else [])
        if lesson == 3:
            assert [i for i, bar in enumerate(oracle.read_gp_bars(produced), 1)
                    if bar["double_bar"]] == [3, 7, 13, 18, 25, 28, 34, 40, 49, 53, 59]
        with ZipFile(produced) as package:
            gpif = ET.fromstring(package.read("Content/score.gpif"))
        bars = gpif.findall("MasterBars/MasterBar")
        assert all(bar.find("Barline") is None for bar in bars)
        # Existing layout extensions now become visible; do not erase them to
        # make a stricter comparator green. Only the task's barline shape changes.
        extras = [d for d in comparison["differences"]
                  if d["field"] == "master_bar_extra_children"]
        assert [(d["bar_index"] + 1, d["actual"]) for d in extras] == [
            (i, ["XProperties"]) for i in
            ({4: [1], 5: list(range(1, 44)), 7: [1, 2]}.get(lesson, []))]
        # Real-source negative controls reject both the old writer and an unknown child.
        # Compare the unmodified output to its mutant to isolate the extra-child defect
        # from existing, independently recorded reference differences.
        for tag in ("Barline", "UnexpectedMasterBarChild", "DoubleBar"):
            target = next(bar for bar in bars if bar.find("DoubleBar") is not None)
            extra = ET.SubElement(target, tag)
            extra.text = "Double"
            mutant = scratch / "mutant.gp"
            with ZipFile(produced) as package, ZipFile(mutant, "w") as changed:
                for name in package.namelist():
                    changed.writestr(name, ET.tostring(gpif) if name == "Content/score.gpif"
                                     else package.read(name))
            mutant_comparison = oracle.compare_gp(reference, mutant)
            extra_differences = [d for d in mutant_comparison["differences"]
                                 if d["field"] == "master_bar_extra_children"]
            assert extra_differences
            assert any(tag in d["actual"] for d in extra_differences)
            assert not compare_package(produced, mutant)["matches"]
            if tag == "Barline":
                cli = subprocess.run(
                    [sys.executable, "-m", "score2gp.cli", "compare", str(produced), str(mutant)],
                    capture_output=True, text=True)
                assert cli.returncode == 1
                assert '"master_bar_extra_children"' in cli.stdout
            target.remove(extra)


def test_real_repeat_end_decision_does_not_depend_on_last_bar_position():
    pdf = PRIVATE / "Ex 2 Hands Up.pdf"
    if not pdf.exists():
        pytest.skip("private repeat corpus absent")
    durations = read_note_durations(pdf, time_signature=(4, 4))
    # Run 5 source evidence: 15 strokes touch filled U+E0A4 heads and are
    # stems, not barlines. Source boundaries give 5/4/3 partitions, including
    # the leading header-only partition: 11 musical bars, also 11 reference
    # master bars. Repeat indices below come from those source boundaries.
    assert [system["bar_count"] for system in durations["systems"]] == [5, 4, 3]
    full = {signal["bar_index"]: signal for signal in
            read_notation_barline_signals(pdf, durations)}
    assert (full[1]["status"], full[1]["kind"]) == ("read", "repeat-start")
    assert [(full[i]["status"], full[i]["kind"]) for i in (5, 7, 9)] == [
        ("read", "repeat-end")] * 3
    assert all(full[i]["kind"] not in ("double", "end") for i in (5, 7, 9))
    durations["systems"] = durations["systems"][:2]
    truncated = {signal["bar_index"]: signal for signal in
                 read_notation_barline_signals(pdf, durations)}
    assert (truncated[9]["status"], truncated[9]["kind"]) == ("read", "repeat-end")


def test_real_repeat_package_uses_reference_flags():
    """Reject legacy RepeatStart/Barline and a repeat end without native flags."""
    pdf = PRIVATE / "Ex 2 Hands Up.pdf"
    reference = PRIVATE / "Ex 2 Hands Up.gp"
    assert pdf.is_file() and reference.is_file()
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as directory:
        scratch = Path(directory)
        output = scratch / "repeat.gp"
        run = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "build")], capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": os.environ.get("SCORE2GP_OMIT02_MUTANT_SRC", str(ROOT / "src"))})
        assert run.returncode == 0, run.stderr[-1200:]
        with ZipFile(reference) as package:
            truth = ET.fromstring(package.read("Content/score.gpif"))
        with ZipFile(output) as package:
            produced = ET.fromstring(package.read("Content/score.gpif"))
        truth_repeats = truth.findall("MasterBars/MasterBar/Repeat")
        repeats = produced.findall("MasterBars/MasterBar/Repeat")
        assert truth_repeats and repeats
        assert not produced.findall("MasterBars/MasterBar/Barline")
        assert not produced.findall("MasterBars/MasterBar/RepeatStart")
        assert {tuple(sorted(r.attrib)) for r in repeats} == {
            tuple(sorted(r.attrib)) for r in truth_repeats}
        assert {r.get("start") for r in repeats} == {r.get("start") for r in truth_repeats}
        assert {r.get("end") for r in repeats} == {r.get("end") for r in truth_repeats}
        # Written flags preserve source decisions/counts, independent of reference counts.
        import json
        source = json.loads((scratch / "build/score.ir.json").read_text())
        actual = []
        for bar in produced.findall("MasterBars/MasterBar"):
            repeat = bar.find("Repeat")
            kind = ("repeat-start" if repeat.get("start") == "true" else "repeat-end") if repeat is not None else None
            actual.append((kind, int(repeat.get("count")) if repeat is not None else None))
        assert actual == [
            (b["barline"], (b["repeat_count"] or 2) if b["barline"] in {"repeat-start", "repeat-end"}
             else b["repeat_count"]) for b in source["bars"]]
