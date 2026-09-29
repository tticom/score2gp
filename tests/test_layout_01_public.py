"""Uneven rows from a public engraved notation/TAB PDF reach final GPIF."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from score2gp.build_ir import _source_system_row_counts
from score2gp.ir import ScoreIR


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "tests/fixtures/pdf/layout_01/uneven_engraved_rows.pdf"
spec = importlib.util.spec_from_file_location("dur02_oracle", ROOT / "tests/test_dur_02_oracle.py")
assert spec and spec.loader
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def test_uneven_engraved_rows_from_production_cli():
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="layout01_public_", dir=work) as directory:
        scratch = Path(directory)
        output = scratch / "output.gp"
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(PDF),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        layouts = oracle.read_gp_systems_layout(output)
        assert layouts == [{"track_id": "0", "default": "3", "layout": (2, 1)}]
        assert sum(layouts[0]["layout"]) == len(oracle.read_gp_bars(output)) == 3

        durations = json.loads((scratch / "work/note-durations.json").read_text(encoding="utf-8"))
        durations["systems"][1]["first_bar_index"] += 1
        score = ScoreIR.from_json_file(scratch / "work/score.ir.json")
        counts, warning = _source_system_row_counts(durations["systems"], score.bars)
        assert counts is None and warning is not None
        for systems in ([], [{**durations["systems"][0], "bar_count": 4}],
                        [durations["systems"][0],
                         {**durations["systems"][1], "page_index": 3,
                          "first_bar_index": 2}]):
            rejected, located = _source_system_row_counts(systems, score.bars)
            assert rejected is None and located.code == "pdf_systems_layout_fallback"
        score.tracks[0].source_system_bars = counts
        assert score.tracks[0].source_system_bars is None
        assert warning.code == "pdf_systems_layout_fallback"
        assert warning.provenance[0].page == 2
        score.warnings.append(warning)
        ir = scratch / "fallback.ir.json"
        score.to_json_file(ir)
        fallback_gp = scratch / "fallback.gp"
        written = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "write-gp", str(ir), "--out", str(fallback_gp)],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True, capture_output=True,
        )
        assert written.returncode == 0, written.stderr
        assert oracle.read_gp_systems_layout(fallback_gp)[0]["layout"] == (3,)
