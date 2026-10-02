"""Private-source acceptance: reference GP is read only after no-reference conversion."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures" / "private"
PDF = PRIVATE / "Can't Find My Way Home (open chord shenanigans).pdf"
REFERENCE = PRIVATE / "Can't Find My Way Home (open chord shenanigans).gp"
FIELDS = ("kind", "positions", "written", "dots", "tuplet", "grace")


@pytest.mark.skipif(not PDF.exists() or not REFERENCE.exists(), reason="private source is not mounted")
def test_every_written_bar_matches_reference_and_every_refusal_is_located():
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cfw04-private-", dir=work) as directory:
        folder = Path(directory)
        output = folder / "output.gp"
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(PDF), "--out", str(output),
             "--work-dir", str(folder / "intermediate"), "--json-report", str(folder / "report.json"),
             "--pdf-only-tab", "--time-signature", "4/4", "--no-strict"],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        route = json.loads((folder / "intermediate" / "note-type-route.json").read_text(encoding="utf-8"))
        assert len(route["bars"]) == 21
        assert route["summary"]["written_bars"] == 18
        refused = [bar for bar in route["bars"] if bar["status"] == "refused"]
        assert [(bar["source_bar_index"], bar["reason"]) for bar in refused] == [
            (3, "notehead_digit_count_mismatch"),
            (6, "bar_total_mismatch"),
            (9, "notehead_digit_count_mismatch"),
        ]
        assert all(bar["location"]["bar_index"] == bar["source_bar_index"] for bar in refused)

        spec = importlib.util.spec_from_file_location("cfw04_oracle", ROOT / "tests" / "test_dur_02_oracle.py")
        assert spec and spec.loader
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        expected = oracle.read_gp_bars(REFERENCE, include_grace=True)
        actual = oracle.read_gp_bars(output, include_grace=True)
        assert len(expected) == len(actual) == 21
        for bar, (want, have) in enumerate(zip(expected, actual)):
            if route["bars"][bar]["status"] != "written":
                assert have["events"] is None
                continue
            assert len(want["events"]) == len(have["events"]), bar
            for index, (left, right) in enumerate(zip(want["events"], have["events"])):
                assert {field: left[field] for field in FIELDS} == {field: right[field] for field in FIELDS}, (bar, index)
