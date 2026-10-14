"""Percussive strikes reach the reader from approved source paint and TAB text."""
from pathlib import Path

import pytest

from score2gp.ir import Note
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.tabraw import make_tab_candidate

ROOT = Path(__file__).resolve().parents[1]


def test_percussive_strike_candidate_never_parses_as_a_fret():
    candidate = make_tab_candidate(candidate_id="strike", raw_text="X", page_index=1,
                                   bbox_values=None, confidence=1, string=3)
    assert candidate.kind == "percussive-strike"
    assert candidate.parsed_strike == "X"
    assert candidate.parsed_fret is None


def test_percussive_strike_has_no_source_fret_or_pitch():
    strike = Note(string=3, is_dead=True)
    assert strike.fret is None and strike.pitch is None
    with pytest.raises(ValueError):
        Note(string=3)


@pytest.mark.parametrize("name,count", [("G-Am-C-Lick", 20), ("E_Chord_Lick_Chord", 3),
                                      ("Can't Find My Way Home (open chord shenanigans)", 1)])
def test_real_source_crosses_have_owned_durations(name, count):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    result = read_note_durations(source)
    heads = [(event, head) for event in result["events"]
             for head in (event.get("notehead") or {}).get("heads", [])
             if head["kind"] == "cross"]
    assert len(heads) == count
    assert all(event["status"] == "read" and event["stem"] and event["duration_quarters"]
               for event, head in heads)
