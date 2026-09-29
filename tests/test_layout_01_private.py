"""Private source PDF systems must survive the production CLI into GPIF."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import pytest
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
