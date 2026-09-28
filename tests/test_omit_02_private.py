"""OMIT-02 acceptance against genuine PDFs and independent GP references.

The private corpus is mounted locally; no source pages or musical data are tracked.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

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
def test_private_lesson_double_bars_agree_per_bar(lesson, tmp_path):
    pdf = PRIVATE / f"Lesson-{lesson}.pdf"
    reference = PRIVATE / f"Lesson-{lesson}.gp"
    if not pdf.exists() or not reference.exists():
        pytest.skip("private lesson corpus absent")
    produced = tmp_path / "produced.gp"
    result = subprocess.run(
        [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
         "--pdf-only-tab", "--time-signature", "4/4", "--out", str(produced),
         "--work-dir", str(tmp_path / "work")],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
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
    assert gpif.find("MasterBars").findall("MasterBar")[-1].find("Barline") is None


def test_real_repeat_end_decision_does_not_depend_on_last_bar_position():
    pdf = PRIVATE / "Ex 2 Hands Up.pdf"
    if not pdf.exists():
        pytest.skip("private repeat corpus absent")
    durations = read_note_durations(pdf, time_signature=(4, 4))
    full = {signal["bar_index"]: signal for signal in
            read_notation_barline_signals(pdf, durations)}
    assert (full[1]["status"], full[1]["kind"]) == ("read", "repeat-start")
    assert [(full[i]["status"], full[i]["kind"]) for i in (12, 19, 24)] == [
        ("read", "repeat-end")] * 3
    assert all(full[i]["kind"] not in ("double", "end") for i in (12, 19, 24))
    durations["systems"] = durations["systems"][:2]
    truncated = {signal["bar_index"]: signal for signal in
                 read_notation_barline_signals(pdf, durations)}
    assert (truncated[24]["status"], truncated[24]["kind"]) == ("read", "repeat-end")
