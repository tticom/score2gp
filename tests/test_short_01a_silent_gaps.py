"""SHORT-01A: the REQ-0005 silent gaps G5, G7 and G8, on real approved PDFs.

Every test runs the product CLI on a private corpus PDF and asserts counts, codes and statuses only; no
musical content is stored here. Synthetic fixtures carry no acceptance weight and none is used. Each test
names the wrong implementation (mutant) it rejects.

* G5  ``generate-sidecar`` on a source whose first-staff timeline is invalid must refuse with a located
  reason code, not a traceback.
* G7  a run that wrote a rest the page does not print (rhythm implied, not read) must not report ``success``
  and must name the located bars; a run that wrote only printed rhythm stays ``success``.
* G8  no rest, and no note whose positions were copied, is carried at confidence 1.0 with empty provenance;
  the implied rest says it is implied and carries zero confidence.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures" / "private"
TWELVE_BAR = "12 Bar Blues Solo Guitar Jam"
FINGER = "Finger postition tips TAB"
SIDECAR_REFUSED = ("Back In Black", "Ex 2 Hands Up")
SKIP = "mounted private corpus is unavailable"


def _pdf(name: str) -> Path:
    path = PRIVATE / f"{name}.pdf"
    if not path.is_file():
        pytest.skip(SKIP)
    return path


@pytest.fixture(scope="module")
def work() -> Path:
    base = ROOT / "work"  # the repository's ignored directory
    base.mkdir(exist_ok=True)
    return base


_CONVERTED: dict[str, tuple[Path, dict, dict]] = {}


def _convert(name: str, work: Path) -> tuple[Path, dict, dict]:
    """Run ``convert --pdf-only-tab`` once; return the work directory, the JSON report and the ScoreIR."""
    if name in _CONVERTED:
        return _CONVERTED[name]
    folder = work / ("short01a-" + re.sub(r"\W+", "_", name))
    folder.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(_pdf(name)), "--out", str(folder / "o.gp"),
           "--work-dir", str(folder / "w"), "--json-report", str(folder / "r.json"), "--pdf-only-tab", "--no-strict"]
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr[-400:]
    report = json.loads((folder / "r.json").read_text(encoding="utf-8"))
    score = json.loads((folder / "w" / "score.ir.json").read_text(encoding="utf-8"))
    _CONVERTED[name] = (folder / "w", report, score)
    return _CONVERTED[name]


@pytest.mark.parametrize("name", SIDECAR_REFUSED)
def test_g5_generate_sidecar_refuses_with_a_located_code_not_a_traceback(name: str, work: Path) -> None:
    """Rejects: the old behaviour, an uncaught ValueError (traceback, no reason code, no location)."""
    done = subprocess.run(
        [sys.executable, "-m", "score2gp.cli", "generate-sidecar", "--pdf", str(_pdf(name)),
         "--out", str(work / "short01a-sidecar.musicxml")],
        capture_output=True, text=True, check=False)
    assert done.returncode == 1
    assert "Traceback" not in done.stderr
    assert "sidecar_generation_measure_capacity_invalid" in done.stderr
    assert re.search(r"measure \d+ of the first staff \(page_index=\d+, system_index=\d+, staff_index=\d+\)", done.stderr)
    assert not (work / "short01a-sidecar.musicxml").exists()


def test_g7_run_with_an_implied_rest_is_partial_and_names_the_bars(work: Path) -> None:
    """Rejects: the old behaviour, status ``success`` for a run that wrote a rest the page does not print."""
    _, report, _ = _convert(TWELVE_BAR, work)
    diag = report["pdf_only_diagnostics"]
    assert report["status"] == "partial" and report["exit_code"] == 0 and report["output_written"] is True
    assert diag["inferred_rhythm_status"] == "implied_rest" and diag["conversion_complete"] is False
    assert [(b["output_bar_index"], b["implied_rests"]) for b in diag["implied_rest_bars"]] == [(26, 1)]


def test_g7_run_with_only_printed_rhythm_stays_success(work: Path) -> None:
    """Rejects: a blanket downgrade that turns every PDF-only run into ``partial`` (a loosened or noisy status)."""
    _, report, _ = _convert(FINGER, work)
    assert report["status"] == "success"
    assert report["pdf_only_diagnostics"]["inferred_rhythm_status"] == "note_type"
    assert "implied_rest_bars" not in report["pdf_only_diagnostics"]


def test_g8_no_rest_or_copied_note_is_full_confidence_without_provenance(work: Path) -> None:
    """Rejects: the old behaviour, rests and tie-continuation notes at confidence 1.0 with empty provenance."""
    for name in (TWELVE_BAR, FINGER):
        _, _, score = _convert(name, work)
        events = [e for bar in score["bars"] for e in bar["events"]]
        for event in events:
            if event["is_rest"]:
                assert event["provenance"], event["id"]
            for note in event["notes"]:
                assert not (note["confidence"] == 1.0 and not note["provenance"]), event["id"]
            assert not (event["confidence"] == 1.0 and not event["provenance"]), event["id"]


def test_g8_implied_rest_is_labelled_and_carries_zero_confidence(work: Path) -> None:
    """Rejects: an implied rest carried at the confidence of a read symbol, or indistinguishable from a printed rest."""
    _, _, score = _convert(TWELVE_BAR, work)
    rests = [e for bar in score["bars"] for e in bar["events"] if e["is_rest"]]
    implied = [e for e in rests if e["provenance"][0]["raw"].get("basis") == "implied_rest"]
    printed = [e for e in rests if e["provenance"][0]["raw"].get("origin") == "notation_rest_glyph"]
    assert len(implied) == 1 and len(printed) == len(rests) - 1 >= 1
    assert implied[0]["confidence"] == 0.0 and implied[0]["provenance"][0]["source_stage"] == "inferred"
    assert all(e["provenance"][0]["page"] >= 1 and e["provenance"][0]["bar_index"] >= 1 for e in rests)


def test_g8_tie_continuation_cites_the_note_it_copies_from(work: Path) -> None:
    """Rejects: a digit-less tie end whose copied positions carry confidence 1.0 and no evidence."""
    _, _, score = _convert(TWELVE_BAR, work)
    bar = next(b for b in score["bars"] if b["index"] == 26)
    stops = [n for e in bar["events"] for n in e["notes"] if any(t.get("state") == "stop" for t in n["techniques"])]
    assert stops
    for note in stops:
        assert note["provenance"] and note["provenance"][0]["raw"].get("derived_from") == "tie_continuation"
