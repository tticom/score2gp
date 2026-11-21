"""TECH-01: slides the reference files have are written from the printed marks.

Genuine private sources only (counts, positions and flags asserted, never content). The independent
oracle ``tests/test_dur_02_oracle.py`` (it does not import score2gp) compares the written GPIF with the
``.gp`` reference. The reader never sees the reference; the reference only judges the result.

Mutants these tests reject (each shown failing in the TECH-01 handback):
  * restore "any digit earlier in the system blocks a slide-in" -> Melodic slide-in positions
  * refuse every slide across a barline again                  -> Melodic cross-bar slides, Bebop holdout
  * restore the 50-unit stroke cap                              -> Melodic bar 8 legato slide
  * write a slide-in over a note that also starts a slide       -> the oracle slide differences on Mixing-style
    notes are caught by the no-extra-slide checks below
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
spec = importlib.util.spec_from_file_location("tech01_oracle", ROOT / "tests/test_dur_02_oracle.py")
assert spec and spec.loader
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)

_results: dict[str, dict] = {}


def _compare(stem: str) -> dict:
    pdf, reference = PRIVATE / f"{stem}.pdf", PRIVATE / f"{stem}.gp"
    if not pdf.is_file() or not reference.is_file():
        pytest.skip("private corpus absent")
    if stem not in _results:
        scratch_root = ROOT / "work"
        scratch_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tech01_", dir=scratch_root) as directory:
            scratch = Path(directory)
            output = scratch / "output.gp"
            run = subprocess.run(
                [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf), "--pdf-only-tab",
                 "--time-signature", "4/4", "--out", str(output), "--work-dir", str(scratch / "work")],
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True)
            assert run.returncode == 0, run.stderr[-1000:]
            _results[stem] = oracle.compare_gp(reference, output)
    return _results[stem]


def _slide_differences(stem: str) -> list[tuple[int, int]]:
    return [(d["bar_index"], d["event_index"]) for d in _compare(stem)["differences"] if d["field"] == "slide"]


def test_melodic_soloing_writes_every_reference_slide():
    """Design source: six reference slides were missing (two slide-ins mid-system, two legato slides
    across a barline, one legato slide with a long stroke, one more across a barline)."""
    assert _slide_differences("Melodic Soloing Masterclass") == []


def test_melodic_soloing_changes_nothing_but_the_slides():
    counts = _compare("Melodic Soloing Masterclass")["difference_counts"]
    assert counts == {"bend": 3, "double_bar": 1, "master_bar_extra_children": 8, "tie": 2}


def test_bebop_holdout_matches_one_more_reference_slide_and_adds_none():
    """Holdout (not tuned on): the legato slide over a barline now matches the reference; the other
    reference slide is still missing and no slide that the reference lacks is written."""
    assert _slide_differences("Bebop Licks in Am") == [(9, 7)]


def test_lesson_5_slide_is_no_worse():
    """The one reference slide is still not written (its printed mark is bound at one end only) and
    nothing extra is written."""
    assert _slide_differences("Lesson-5") == [(16, 0)]


@pytest.mark.parametrize("stem, expected", [
    ("Ex 2 Hands Up", [(4, 7)]),
    ("Can't Find My Way Home (open chord shenanigans)", [(7, 2), (15, 4), (15, 12)]),
])
def test_other_holdouts_are_unchanged_and_get_no_extra_slide(stem, expected):
    assert _slide_differences(stem) == expected
