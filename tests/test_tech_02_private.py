"""TECH-02: the bends the reference files have, read by the independent oracle and measured on the product.

Genuine private sources only (counts and positions asserted, never content). The oracle
``tests/test_dur_02_oracle.py`` does not import score2gp. The product writes no bend for these printed
bend-and-release / bend marks (goal 3 is blocked, see docs/measurements/tech-02-bends-against-references.md),
so these tests pin the measured gap: they fail if the oracle stops reading a reference bend, and they fail
if the product starts writing a bend that differs from the reference without this file being updated.

Mutants these tests reject (each shown failing in the TECH-02 handback):
  * the oracle ignores ``Bended`` / ``Bend*`` properties       -> reference bend counts become 0
  * the oracle stops reading the bend offsets                  -> the stored offsets asserted below differ
The product-side tests are a pin, not a mutant-driven acceptance: they carry no goal-3 weight.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures" / "private"
spec = importlib.util.spec_from_file_location("tech02_oracle", ROOT / "tests/test_dur_02_oracle.py")
assert spec and spec.loader
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)

DESIGN = "Melodic Soloing Masterclass"
HOLDOUT = "Ex 2 Hands Up"
CANT_FIND = "Can't Find My Way Home (open chord shenanigans)"


def _reference_bends(stem: str, **kw) -> list[tuple[int, int, tuple]]:
    reference = PRIVATE / f"{stem}.gp"
    if not reference.is_file():
        pytest.skip("private corpus absent")
    return [(b, i, tuple(ev["bend"])) for b, bar in enumerate(oracle.read_gp_bars(reference, **kw))
            for i, ev in enumerate(bar["events"] or []) if ev.get("bend")]


@pytest.mark.parametrize("stem, kw, positions", [
    (DESIGN, {}, [(1, 5), (5, 7), (7, 4)]),
    (HOLDOUT, {}, [(9, 0)]),
    (CANT_FIND, {}, [(10, 7), (11, 0), (15, 0), (15, 9), (18, 7), (19, 0)]),
    ("Derek Trucks BB King", {"track_id": "0"},
     [(10, 5), (12, 0), (12, 1), (12, 2), (12, 6), (13, 13), (13, 18), (14, 10)]),
])
def test_oracle_reads_every_reference_bend_by_bar_and_event(stem, kw, positions):
    found = _reference_bends(stem, **kw)
    assert [(b, i) for b, i, _ in found] == positions
    assert all(len(bend) == 1 and len(bend[0]) == 2 + len(oracle.BEND_PROPERTIES)
               and None not in bend[0] for _, _, bend in found)


def test_reference_stores_offsets_that_the_printed_shape_does_not_fix():
    """The three design-source marks print the same shape (labelled up-arrow, release arrow to the next
    note) and the reference stores one envelope for them; the holdout mark prints the same shape and the
    reference stores different middle and destination offsets. No printed quantity is a function of those
    offsets, which is why the product does not write them (goal 3 blocked)."""
    design = {bend[0][2:] for _, _, bend in _reference_bends(DESIGN)}
    holdout = {bend[0][2:] for _, _, bend in _reference_bends(HOLDOUT)}
    assert len(design) == 1 and len(holdout) == 1
    (d,), (h,) = tuple(design), tuple(holdout)
    assert d[:3] == h[:3] and d[5] == h[5]          # origin, origin offset, peak value and release value agree
    assert d[4] != h[4] and d[6] != h[6]            # middle offset 2 and destination offset differ


_results: dict[str, dict] = {}


def _compare(stem: str) -> dict:
    pdf, reference = PRIVATE / f"{stem}.pdf", PRIVATE / f"{stem}.gp"
    if not pdf.is_file() or not reference.is_file():
        pytest.skip("private corpus absent")
    if stem not in _results:
        scratch_root = ROOT / "work"
        scratch_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tech02_", dir=scratch_root) as directory:
            scratch = Path(directory)
            output = scratch / "output.gp"
            run = subprocess.run(
                [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf), "--pdf-only-tab",
                 "--time-signature", "4/4", "--out", str(output), "--work-dir", str(scratch / "work")],
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True)
            assert run.returncode == 0, run.stderr[-1000:]
            _results[stem] = oracle.compare_gp(reference, output)
    return _results[stem]


@pytest.mark.parametrize("stem, positions", [
    (DESIGN, [(1, 5), (5, 7), (7, 4)]),
    (HOLDOUT, [(9, 0)]),
    (CANT_FIND, [(10, 7), (11, 0), (15, 0), (15, 9), (18, 7), (19, 0)]),
])
def test_product_bend_differences_are_exactly_the_located_unwritten_reference_bends(stem, positions):
    """Every reference bend is missing from the output and the product adds none the reference lacks."""
    bends = [d for d in _compare(stem)["differences"] if d["field"] == "bend"]
    assert [(d["bar_index"], d["event_index"]) for d in bends] == positions
    assert all(d["actual"] is None and d["expected"] for d in bends)
