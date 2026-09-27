"""DUR-01 acceptance oracle: the GPIF rhythm reader and the per-event comparison.

The written note value, dots, tuplet ratio and tie are independent GPIF fields. Each must reach the
comparison and be compared on its own: equal sounding durations must never hide a wrong note type or
grouping. Everything here is synthetic; no private source is read.
"""

from __future__ import annotations

import copy
import importlib.util
import zipfile
from fractions import Fraction
from pathlib import Path

import pytest

from score2gp.notation_omr.note_duration import read_note_durations

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "pdf" / "dur_01"


def _compare_module():
    spec = importlib.util.spec_from_file_location("dur_01_compare", ROOT / "scripts" / "dur_01_compare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gpif(rhythms: list[str], beats: list[tuple[str, str | None]], notes: list[str]) -> str:
    """One bar, one voice. ``beats`` holds (rhythm id, note id or None for a rest)."""
    beat_xml = "".join(
        f'<Beat id="{i}"><Rhythm ref="{r}"/>' + (f"<Notes>{n}</Notes>" if n is not None else "") + "</Beat>"
        for i, (r, n) in enumerate(beats))
    return ("<GPIF><MasterBars><MasterBar><Bars>0</Bars></MasterBar></MasterBars>"
            '<Bars><Bar id="0"><Voices>0 -1 -1 -1</Voices></Bar></Bars>'
            f'<Voices><Voice id="0"><Beats>{" ".join(str(i) for i in range(len(beats)))}</Beats></Voice></Voices>'
            f"<Beats>{beat_xml}</Beats><Notes>{''.join(notes)}</Notes><Rhythms>{''.join(rhythms)}</Rhythms></GPIF>")


def _write_gp(tmp_path: Path, xml: str) -> Path:
    path = tmp_path / "bar.gp"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Content/score.gpif", xml)
    return path


TRIPLET_BAR = _gpif(
    rhythms=['<Rhythm id="0"><NoteValue>Eighth</NoteValue><PrimaryTuplet num="3" den="2"/></Rhythm>',
             '<Rhythm id="1"><NoteValue>16th</NoteValue><PrimaryTuplet num="3" den="4"/></Rhythm>',
             '<Rhythm id="2"><NoteValue>Quarter</NoteValue><AugmentationDot count="1"/></Rhythm>',
             '<Rhythm id="3"><NoteValue>Half</NoteValue></Rhythm>'],
    beats=[("0", "0"), ("1", "1"), ("2", None), ("3", "2")],
    notes=['<Note id="0"><Tie origin="true" destination="false"/></Note>',
           '<Note id="1"><Tie origin="false" destination="true"/></Note>', '<Note id="2"/>'],
)


def test_rhythm_reader_carries_written_value_dots_tuplet_and_tie_separately(tmp_path):
    truth = _compare_module().rhythm_ground_truth(_write_gp(tmp_path, TRIPLET_BAR))
    assert truth == [[
        {"kind": "note", "written": "eighth", "dots": 0, "tuplet": (3, 2), "duration": Fraction(1, 3), "tie": (True, False)},
        # The same sounding third of a quarter, written as a sixteenth in a 3:4 grouping.
        {"kind": "note", "written": "16th", "dots": 0, "tuplet": (3, 4), "duration": Fraction(1, 3), "tie": (False, True)},
        {"kind": "rest", "written": "quarter", "dots": 1, "tuplet": None, "duration": Fraction(3, 2), "tie": (False, False)},
        {"kind": "note", "written": "half", "dots": 0, "tuplet": None, "duration": Fraction(2), "tie": (False, False)},
    ]]


@pytest.mark.parametrize("rhythm, code", [
    ('<Rhythm id="0"><NoteValue>128th</NoteValue></Rhythm>', "128th"),
    ('<Rhythm id="0"><NoteValue>Eighth</NoteValue><SecondaryTuplet num="3" den="2"/></Rhythm>', "SecondaryTuplet"),
])
def test_rhythm_reader_refuses_what_it_cannot_read(tmp_path, rhythm, code):
    with pytest.raises(SystemExit, match=code):
        _compare_module().rhythm_ground_truth(_write_gp(tmp_path, _gpif([rhythm], [("0", "0")], ['<Note id="0"/>'])))


def _triplet_truth() -> list[list[dict]]:
    """Ground truth of tests/fixtures/pdf/dur_01/triplet.pdf, written by hand from the music."""
    eighth3 = {"kind": "note", "written": "eighth", "dots": 0, "tuplet": (3, 2), "duration": Fraction(1, 3), "tie": (False, False)}
    quarter3 = {"kind": "note", "written": "quarter", "dots": 0, "tuplet": (3, 2), "duration": Fraction(2, 3), "tie": (False, False)}
    quarter = {"kind": "note", "written": "quarter", "dots": 0, "tuplet": None, "duration": Fraction(1), "tie": (False, False)}
    return [[dict(eighth3), dict(eighth3), dict(eighth3), dict(quarter3), dict(quarter3), dict(quarter3), dict(quarter)]]


def test_the_triplet_fixture_matches_its_hand_written_truth_field_by_field():
    compare = _compare_module()
    result = compare.compare(read_note_durations(FIXTURES / "triplet.pdf"), _triplet_truth())
    assert result["summary"]["matched_events"] == 7 and result["summary"]["mismatches"] == []


def test_negative_control_equal_duration_different_written_value_and_ratio_in_the_truth():
    """A triplet eighth and a sixteenth in a 3:4 grouping both sound a third of a quarter."""
    compare = _compare_module()
    truth = _triplet_truth()
    truth[0][0].update(written="16th", tuplet=(3, 4))
    assert truth[0][0]["duration"] == Fraction(1, 3)
    result = compare.compare(read_note_durations(FIXTURES / "triplet.pdf"), truth)
    assert result["summary"]["matched_events"] == 6
    [row] = [r for r in result["rows"] if r["cause"]]
    assert (row["bar_index"], row["event_index"], row["cause"]) == (0, 0, "written_mismatch")
    assert row["differences"] == ["written", "tuplet"]


def test_negative_control_reviewer_mutation_of_the_read_record():
    """The reviewer's mutation: written eighth to quarter and ratio to 5:4, duration kept."""
    compare = _compare_module()
    records = read_note_durations(FIXTURES / "triplet.pdf")
    mutated = copy.deepcopy(records)
    event = mutated["events"][0]
    event["written"] = "quarter"
    event["tuplet"] = dict(event["tuplet"], actual=5, normal=4)
    result = compare.compare(mutated, _triplet_truth())
    [row] = [r for r in result["rows"] if r["cause"]]
    assert row["cause"] == "written_mismatch" and row["differences"] == ["written", "tuplet"]


@pytest.mark.parametrize("field, value, cause", [
    ("tuplet", None, "tuplet_mismatch"),
    ("dots", 1, "dots_mismatch"),
    ("tie", (True, False), "tie_mismatch"),
])
def test_each_symbol_field_is_compared_on_its_own(field, value, cause):
    compare = _compare_module()
    truth = _triplet_truth()
    truth[0][0][field] = value
    result = compare.compare(read_note_durations(FIXTURES / "triplet.pdf"), truth)
    [row] = [r for r in result["rows"] if r["cause"]]
    assert row["cause"] == cause and row["differences"] == [field]
