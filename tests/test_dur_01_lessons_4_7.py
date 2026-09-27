"""DUR-01 beyond the acceptance source: Lessons 4-7, per event, against their .gp ground truth.

The reference reader refuses these files (they contain tuplets and ties), so their rhythm is read by
the rhythm-only standard-library reader in scripts/dur_01_compare.py, which is first checked to agree
with the reference reader on Lesson 3. Assertions hold counts and codes only.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

from score2gp.notation_omr.note_duration import read_note_durations

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures" / "private"


def _compare_module():
    spec = importlib.util.spec_from_file_location("dur_01_compare", ROOT / "scripts" / "dur_01_compare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require(*names: str) -> None:
    missing = [n for n in names if not (PRIVATE / n).exists()]
    if missing:
        pytest.skip(f"private corpus not mounted: {', '.join(missing)}")


def test_rhythm_only_reader_agrees_with_the_reference_reader_on_lesson_3():
    _require("Lesson-3.gp")
    compare = _compare_module()
    rhythm = compare.rhythm_ground_truth(PRIVATE / "Lesson-3.gp")
    reference = compare.ground_truth(PRIVATE / "Lesson-3.gp")
    # Every field, including the written value the rhythm reader takes from NoteValue.
    assert rhythm == reference


@pytest.mark.parametrize("lesson, bars, events, tied, tupletted", [
    (4, 79, 557, 6, 0), (5, 43, 523, 6, 261), (6, 72, 663, 10, 569), (7, 50, 474, 0, 0)])
def test_every_event_read_and_equal_to_ground_truth(lesson, bars, events, tied, tupletted):
    """Rest or note, written value, dots, tuplet ratio, sounding duration and tie, each per event."""
    _require(f"Lesson-{lesson}.pdf", f"Lesson-{lesson}.gp")
    compare = _compare_module()
    records = read_note_durations(PRIVATE / f"Lesson-{lesson}.pdf")
    summary = compare.compare(records, compare.rhythm_ground_truth(PRIVATE / f"Lesson-{lesson}.gp"))["summary"]
    assert (summary["ground_truth_bars"], summary["read_bars"]) == (bars, bars)
    assert summary["ground_truth_events"] == summary["read_events"] == summary["matched_events"] == events
    assert summary["ground_truth_tied_events"] == tied
    assert summary["ground_truth_tupletted_events"] == tupletted
    assert summary["fields"] == {f: {"compared": events, "equal": events} for f in compare.FIELDS}
    assert summary["mismatches"] == []
    assert records["diagnostics"]["events_outside_bars"] == 0


def test_negative_control_real_tuplet_with_its_written_value_and_ratio_changed():
    """The reviewer's Lesson-5 mutation: written eighth to quarter, ratio to 5:4, sounding duration kept."""
    _require("Lesson-5.pdf", "Lesson-5.gp")
    compare = _compare_module()
    records = read_note_durations(PRIVATE / "Lesson-5.pdf")
    truth = compare.rhythm_ground_truth(PRIVATE / "Lesson-5.gp")
    mutated = copy.deepcopy(records)
    event = next(e for e in mutated["events"] if e["tuplet"] and e["written"] == "eighth")
    event["written"] = "quarter"
    event["tuplet"] = dict(event["tuplet"], actual=5, normal=4)
    summary = compare.compare(mutated, truth)["summary"]
    assert summary["matched_events"] == 522
    [mismatch] = summary["mismatches"]
    assert (mismatch["bar_index"], mismatch["event_index"]) == (event["bar_index"], event["event_index"])
    assert mismatch["cause"] == "written_mismatch" and mismatch["differences"] == ["written", "tuplet"]


def test_real_tuplets_and_ties_are_read_not_just_synthetic_ones():
    _require("Lesson-5.pdf", "Lesson-6.pdf")
    tuplets = ties = 0
    for lesson in (5, 6):
        for event in read_note_durations(PRIVATE / f"Lesson-{lesson}.pdf")["events"]:
            tuplets += bool(event["tuplet"])
            ties += event["tie"]["start"]
    assert tuplets > 0 and ties > 0
