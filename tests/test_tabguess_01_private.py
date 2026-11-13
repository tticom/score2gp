"""TABGUESS-01: the spacing model for TAB that prints no rhythm, scored on real sources where the rhythm is read.

Acceptance rests on the approved private sources (counts only, never content). The oracle is each source's own
READ rhythm (strategies 1 and 2 of knowledge/tab-rhythm-reading-strategy.md), hidden from the model: the
model sees only the x of the TAB columns and the meter. SYNTHETIC TESTS CARRY NO ACCEPTANCE WEIGHT and none
are used here. Reference-less sources (no .gp in the corpus) are NOT independently verified: their "truth" is
the reader's own output.

Nothing guessed is written anywhere: the no-rhythm source keeps its 68 + 8 refused bars (test below).

Mutants (each shown to fail the test it is named under; see the handback):
  UNIFORM_SPACING   SPACING_RULE = "uniform": every column gets an equal share of the bar, spacing ignored.
                    Rejected by test_design_source_scores_floor (12 Bar: 61 bars exact -> 45).
  DROP_METER_TOTAL  ENFORCE_METER_TOTAL = False: no total check, the last column is taken from its own gap.
                    Rejected by test_every_inferred_bar_adds_up_to_the_meter (inferred bars no longer add up).
"""
import json
from fractions import Fraction
from pathlib import Path

import pytest
from typer.testing import CliRunner

import tabguess_01_scorer as T
from score2gp.cli import app

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"

DESIGN = ("12 Bar Blues Solo Guitar Jam", "Mixing Lead & Rhythm pt1")
NO_RHYTHM = "7_Grateful_Dead_Melodies"


@pytest.fixture(scope="session")
def build_root(tmp_path_factory):
    return tmp_path_factory.mktemp("tabguess01")


def _convert(build_root, name):
    out = build_root / name
    build = out / "build"
    if not (build / "note-type-route.json").is_file():
        pdf = PRIVATE / f"{name}.pdf"
        assert pdf.is_file(), "REQUIRED_TABGUESS_01_SOURCE_MISSING"
        out.mkdir(parents=True, exist_ok=True)
        CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(out / "o.gp"),
                                 "--work-dir", str(build)])
    return out, build


def _score(build_root, names):
    total = T.Score()
    for name in names:
        total.add(T.score_bars(T.load_bars(_convert(build_root, name)[1], name)))
    return total


def test_design_source_scores_floor(build_root):
    """Rejects UNIFORM_SPACING (and any rule that does not read the spacing): equal division reaches 45 of 61 on
    the TAB-only source, the spacing model reaches 61, and over both design sources the model beats equal
    division by a wide margin."""
    s = _score(build_root, DESIGN)
    assert s.comparable == 95
    assert s.exact == 95, f"TABGUESS_EXACT_{s.exact}_OF_{s.comparable}"
    assert s.baseline_exact <= 79
    assert s.exact - s.baseline_exact >= 16


def test_every_inferred_bar_adds_up_to_the_meter(build_root):
    """Rejects DROP_METER_TOTAL: with no total check the inferred durations of real bars stop adding up."""
    s = _score(build_root, DESIGN)
    assert s.total_mismatch == 0
    for name in DESIGN:
        for bar in T.load_bars(_convert(build_root, name)[1], name):
            if bar.truth is None:
                continue
            guess = T.infer_rhythm(bar.col_x, bar.capacity)
            assert guess is None or sum(guess) == bar.capacity


def test_mutants_are_caught_on_the_real_source(build_root, monkeypatch):
    """The two named mutants really do fail the assertions above, on the same real source."""
    monkeypatch.setattr(T, "SPACING_RULE", "uniform")
    assert _score(build_root, DESIGN).exact < 95
    monkeypatch.setattr(T, "SPACING_RULE", "log_gap")
    monkeypatch.setattr(T, "ENFORCE_METER_TOTAL", False)
    assert _score(build_root, DESIGN).total_mismatch > 0


def test_holdout_sources_scored_once_pinned(build_root):
    """The two-plus held-out sources, scored once with the model as fixed before they were scored. Pinned so the
    published accuracy cannot change silently; this is a measurement, not a tuned target."""
    s = _score(build_root, T.HOLDOUT)
    assert (s.comparable, s.exact, s.abstained, s.total_mismatch) == (79, 49, 0, 0)
    assert len(T.HOLDOUT) >= 2


def test_no_rhythm_source_keeps_every_refusal_and_writes_no_guess(build_root):
    """Rejects writing guessed bars: the source that prints no rhythm keeps its 68 + 8 refused bars, the GP
    holds only the 7 printed whole-rest bars, and the word GUESS appears in no output."""
    out, build = _convert(build_root, NO_RHYTHM)
    route = json.loads((build / "note-type-route.json").read_bytes())["summary"]
    # REFUSE-22 additionally writes the 4 bars in which nothing at all is printed (no rhythm is guessed for them:
    # they hold no event); the other 4 bars without an event keep their refusal.
    assert route["written_bars"] == 7 + 4
    assert route["refused_bars"] == 72
    assert route["refusal_reasons"] == {"note_duration_event_unread": 68, "bar_without_notation_event": 4}
    for artefact in build.rglob("*.json"):
        assert T.GUESS_LABEL not in artefact.read_text(encoding="utf-8", errors="ignore")
    bars = T.load_bars(build, NO_RHYTHM)
    refused = [b for b in bars if b.status == "refused"]
    assert len(refused) == 72
    # every refused bar with a printed TAB digit has its column(s), and the model only reports a labelled guess
    columned = [b for b in refused if b.col_x]
    assert len(columned) == 68  # TABEXT-03: was 53; the 14 digit-bearing bars that lay outside a system now have columns
    assert sum(len(b.col_x) for b in columned) == 238  # was 202 before TABEXT-03: the printed digits outside a system are columns now
    for b in columned:
        guess = T.infer_rhythm(b.col_x, b.capacity)
        assert guess is not None and sum(guess) == Fraction(b.capacity)
    assert all(b.truth is None for b in refused)  # a guess is never a read result
