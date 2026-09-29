"""Public conversion budget for ScoreIR candidate provenance."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "tests/fixtures/pdf/layout_01/uneven_engraved_rows.pdf"
# Baseline checkout on this fixture: 355,429 bytes / 3 bars = 118,476 bytes per bar.
# The bound leaves room above the measured compact result (9,014 bytes/bar).
MAX_IR_BYTES_PER_BAR = 20_000


def test_public_ir_bytes_per_bar_budget():
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(PDF),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(scratch / "score.gp"),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        ir_path = scratch / "work/score.ir.json"
        bars = len(json.loads(ir_path.read_text(encoding="utf-8"))["bars"])
        assert bars == 3
        assert ir_path.stat().st_size / bars <= MAX_IR_BYTES_PER_BAR
