"""Private source PDF systems must survive the production CLI into GPIF."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import pytest
from score2gp.build_ir import _source_system_row_counts
from score2gp.ir import ScoreIR


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
spec = importlib.util.spec_from_file_location("dur02_oracle", ROOT / "tests/test_dur_02_oracle.py")
assert spec and spec.loader
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


@pytest.mark.parametrize("name", [f"Lesson-{index}" for index in range(3, 8)])
def test_lesson_source_rows_reach_gpif(name):
    pdf, reference = PRIVATE / f"{name}.pdf", PRIVATE / f"{name}.gp"
    if not pdf.is_file() or not reference.is_file():
        pytest.skip("private corpus absent")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="layout01_", dir=scratch_root) as directory:
        scratch = Path(directory)
        output = scratch / "output.gp"
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        assert oracle.compare_gp_systems_layout(reference, output) == []
        assert sum(oracle.read_gp_systems_layout(output)[0]["layout"]) == len(oracle.read_gp_bars(output))
        score = ScoreIR.from_json_file(scratch / "work/score.ir.json")
        for track in score.tracks:
            track.source_system_bars = None
        legacy_ir = scratch / "legacy.ir.json"
        score.to_json_file(legacy_ir)
        legacy = scratch / "legacy.gp"
        legacy_result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "write-gp", str(legacy_ir),
             "--out", str(legacy)],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, capture_output=True,
        )
        assert legacy_result.returncode == 0, legacy_result.stderr
        changes = oracle.compare_gp(legacy, output)["difference_counts"]
        assert changes == {"systems_layout": 1}
        with zipfile.ZipFile(legacy) as package:
            old_xml = ET.fromstring(package.read("Content/score.gpif"))
        with zipfile.ZipFile(output) as package:
            new_xml = ET.fromstring(package.read("Content/score.gpif"))
        for old, new in zip(old_xml.findall("Tracks/Track"), new_xml.findall("Tracks/Track")):
            new.find("SystemsLayout").text = old.findtext("SystemsLayout")
        assert ET.tostring(new_xml) == ET.tostring(old_xml)


@pytest.mark.parametrize("name,total,consumed", [("Lesson-3", 66, 3), ("Lesson-4", 79, 2)])
def test_fallback_message_keeps_full_real_source_total(name, total, consumed):
    """Reject the old prefix-as-total message using actual source row counts.

    The corpus normally retains all row ordinals. Fault injection changes only
    one first-bar index to exercise the diagnostic, not recognition/grouping.
    """
    pdf, reference = PRIVATE / f"{name}.pdf", PRIVATE / f"{name}.gp"
    if not pdf.is_file() or not reference.is_file():
        pytest.skip("private corpus absent")
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="layout01_fallback_", dir=scratch_root) as directory:
        scratch = Path(directory)
        output = scratch / "output.gp"
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        durations = json.loads((scratch / "work/note-durations.json").read_text(encoding="utf-8"))
        score = ScoreIR.from_json_file(scratch / "work/score.ir.json")
        systems = durations["systems"]
        assert sum(system["bar_count"] for system in systems) == total
        assert len(score.bars) == len(oracle.read_gp_bars(reference)) == total
        assert systems[0]["bar_count"] == consumed < total
        assert systems[1]["page_index"] == 0 and systems[1]["system_index"] == 1
        systems[1]["first_bar_index"] += 1
        counts, warning = _source_system_row_counts(systems, score.bars)
        assert counts is None and warning is not None
        assert warning.code == "pdf_systems_layout_fallback"
        assert warning.message == (
            "PDF row layout unavailable or disagrees with written bars at page 1, "
            f"system 2; source bars {total}, consumed bars {consumed}, written bars {total}. "
            "Using the track's SystemsDefautLayout as fixed bars per row."
        )
        assert warning.provenance[0].page == 1
        assert warning.provenance[0].system_id == "system-2"
        assert warning.provenance[0].bar_index == consumed + 1
