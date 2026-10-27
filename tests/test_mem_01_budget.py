"""Public conversion budget for ScoreIR candidate provenance.

MEM-01-FU1 measurement at 1f14c4d, Windows, PDF-only CLI, 4/4:
all 223 tracked public PDFs were attempted; 15 emitted IR, 208 emitted none
(inputs without IR have no bytes/bar measurement). Successful measurements:

    PDF (relative to fixtures/public/ or tests/fixtures/pdf/)   bytes / bars
    Just-Practice-Like-THIS-Every-Day.pdf                       259459 / 42
    Melodic Soloing Masterclass.pdf                            307757 / 8
    generated_simple/simple/4QuarterNotes.pdf                   18144 / 1
    generated_simple/simple/QuarterRestThenNotes.pdf            14048 / 1
    cfw_04/grace_stemless_wave.pdf                              18421 / 1
    cfw_04/grace_stemless_wave_2x.pdf                           18435 / 1
    cfw_04/tie_over_grace.pdf                                   17665 / 1
    layout_01/uneven_engraved_rows.pdf                          27385 / 3
    omit_03/boundary.pdf                                       28112 / 3
    omit_03/nonfirst.pdf                                       28002 / 3
    omit_03/occupied.pdf                                       28717 / 3
    omit_03/tie.pdf                                            28113 / 3
    omit_03/unavailable.pdf                                    28102 / 3
    scale_01/large.pdf                                          7723 / 3
    scale_01/normal.pdf                                         5899 / 3

The original bound was 20,000 bytes/bar for layout_01 alone. Keep that fixture
and add the two successfully converted real public scores with their own bounds
about 24% above measurement. Sizes include paths, so allow platform/path drift.
This is a serialization-size guard; it makes no recognition or fidelity claim.

Named mutants rejected by the same budget assertion:
* double_ir_bytes: valid JSON whitespace doubles the serialized IR size.
* restore_full_raw: restores the pre-MEM-01 candidate raw payload in provenance.
The negative-control test also rejects an over-wide budget (including the old
20,000 bound on layout_01), because double_ir_bytes would then escape it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MAX_IR_BYTES_PER_BAR = 11_300
PUBLIC_BUDGETS = [
    ("tests/fixtures/pdf/layout_01/uneven_engraved_rows.pdf", 3, MAX_IR_BYTES_PER_BAR),
    ("fixtures/public/Just-Practice-Like-THIS-Every-Day.pdf", 42, 7_700),
    ("fixtures/public/Melodic Soloing Masterclass.pdf", 8, 48_000),
]

# Mutate only the child process; never edit or replace production source files.
RESTORE_FULL_RAW = """
from score2gp.tabraw import TabCandidate
original = TabCandidate.to_provenance
def restore_full_raw(self):
    provenance = original(self)
    provenance.raw = {
        'kind': self.kind, 'raw_text': self.raw_text,
        'parsed_fret': self.parsed_fret, 'string': self.string,
        'x': self.x, 'y': self.y, **self.raw,
    }
    return provenance
TabCandidate.to_provenance = restore_full_raw
from score2gp.cli import app
app()
"""


def _assert_budget(ir_path, expected_bars, bound):
    bars = len(json.loads(ir_path.read_text(encoding="utf-8"))["bars"])
    assert bars == expected_bars
    bytes_per_bar = ir_path.stat().st_size / bars
    assert bytes_per_bar <= bound, f"{bytes_per_bar:.2f} bytes/bar exceeds {bound}"


def _convert(pdf, scratch, mutant=None):
    entrypoint = (["-c", RESTORE_FULL_RAW] if mutant == "restore_full_raw"
                  else ["-m", "score2gp.cli"])
    result = subprocess.run(
        [sys.executable, *entrypoint, "convert", "--pdf", str(ROOT / pdf),
         "--pdf-only-tab", "--time-signature", "4/4", "--out", str(scratch / "score.gp"),
         "--work-dir", str(scratch / "work")],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-1200:]
    ir_path = scratch / "work/score.ir.json"
    if mutant == "double_ir_bytes":
        # Trailing JSON whitespace preserves the score and doubles actual bytes.
        payload = ir_path.read_bytes()
        ir_path.write_bytes(payload + b" " * len(payload))
    return ir_path


@pytest.mark.parametrize("pdf,expected_bars,bound", PUBLIC_BUDGETS)
def test_public_ir_bytes_per_bar_budget(pdf, expected_bars, bound):
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        _assert_budget(_convert(pdf, scratch), expected_bars, bound)


@pytest.mark.parametrize("pdf,expected_bars,bound", PUBLIC_BUDGETS)
@pytest.mark.parametrize("mutant", ["double_ir_bytes", "restore_full_raw"])
def test_public_ir_budget_rejects_reinflation(pdf, expected_bars, bound, mutant):
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        ir_path = _convert(pdf, Path(directory), mutant)
        with pytest.raises(AssertionError, match="bytes/bar exceeds"):
            _assert_budget(ir_path, expected_bars, bound)
