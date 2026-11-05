"""Real-source chords whose tie leaves one head (TIEOWN-01).

Measured on the whole private set (counts and codes only): the bars refused as
`mixed_percussive_tie_ownership_unread` (3) are a chord of strikes plus ONE filled head whose tie arc leaves that
filled head and ends on the single note after it, which prints no digit. Two cascade bars (the next bar's first
note) waited on them. The reader now records which head each arc end sits on (position and rank among the
chord's heads); the route writes the chord only when the arc's rank is the filled head's rank and the event it
ends on accounts for that arc, so the tie is on that head alone and the strikes carry none.

Sources: `Crossroads.pdf` bars 0->1 and 14->15 and `Pride and Joy.pdf` bar 8. None has a reference `.gp`, so these
bars are NOT independently verified against a reference; each was checked against the printed page by eye.
`Lesson-6.pdf` bar 26 (reference `Lesson-6.gp`) is the guard: a first version wrote it with two of the three tie
origins the reference has (a third arc is not read), so it must stay refused until every arc is read.
Synthetic tests carry no acceptance weight; none are used. Mutants (each fails a test below):
  DROP_RULE              `assembler.ENABLE_HEAD_OWNED_TIES` False: the mixed chord bars stay refused.
  DROP_READER_OWNERSHIP  `note_duration.ENABLE_TIED_HEAD_OWNERSHIP` False: no arc end is recorded, so refused.
  TIE_EVERY_HEAD         every note of the chord gets the event's tie: the strikes carry a tie.
  SKIP_CONSUMER_CHECK    `assembler._accounts_for` always True: Lesson-6 bar 26 is written with a missing tie.
"""
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp import pdf_tab_bar_assembler as assembler
from score2gp import pdf_tab_event_factory as factory
from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
# (source, zero-based source bar of the chord, bar holding the note it ties to)
CHORDS = [("Crossroads", 0, 1), ("Crossroads", 14, 15), ("Pride and Joy", 8, 8)]


def _convert(source, tmp_path):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_TIEOWN_01_SOURCE_MISSING"
    build = tmp_path / source.replace(" ", "_")
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                             "--out", str(build / "output.gp"), "--work-dir", str(build / "w")])
    route = json.loads((build / "w" / "note-type-route.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, build / "output.gp"


def _notes(gp_path, bar_index):
    """Per beat of one bar: [(string, fret, dead, origin, destination)] of its notes."""
    root = ET.fromstring(zipfile.ZipFile(gp_path).read("Content/score.gpif"))
    voices = {v.get("id"): v for v in root.find("Voices")}
    beats = {b.get("id"): b for b in root.find("Beats")}
    notes = {n.get("id"): n for n in root.find("Notes")}
    out = []
    for voice_id in root.find("Bars")[bar_index].find("Voices").text.split():
        if voice_id == "-1":
            continue
        for beat_id in voices[voice_id].find("Beats").text.split():
            beat = beats[beat_id]
            played = []
            for note_id in (beat.find("Notes").text.split() if beat.find("Notes") is not None else []):
                note = notes[note_id]
                props = {p.get("name"): p for p in note.find("Properties")}
                tie = note.find("Tie")
                played.append((props["String"].find("String").text, props["Fret"].find("Fret").text,
                               note.find("DeadNote") is not None,
                               tie is not None and tie.get("origin") == "true",
                               tie is not None and tie.get("destination") == "true"))
            out.append(sorted(played))
    return out


def _check_chord_bars(tmp_path):
    cache = {}
    for source, chord_bar, tied_bar in CHORDS:
        if source not in cache:
            cache[source] = _convert(source, tmp_path)
        bars, output = cache[source]
        for bar in {chord_bar, tied_bar}:
            assert bars[bar]["status"] == "written", f"CHORD_BAR_REFUSED_{source}_{bar}"
        chord = next(b for b in reversed(_notes(output, chord_bar)) if len(b) > 1)
        origins = [n for n in chord if n[3]]
        assert len(origins) == 1, "TIE_NOT_ON_EXACTLY_ONE_HEAD"
        assert any(n[2] for n in chord), "CHORD_HAS_NO_STRIKE"
        assert not any(n[3] or n[4] for n in chord if n[2]), "TIE_ON_A_STRIKE"
        tied = [b for b in _notes(output, tied_bar) if any(n[4] for n in b)]
        assert len(tied) == 1 and len(tied[0]) == 1, "TIED_NOTE_NOT_THE_ONE_AFTER"
        assert tied[0][0][:2] == origins[0][:2], "TIE_ENDS_ON_ANOTHER_STRING_OR_FRET"


def test_strike_chords_tie_only_their_filled_head_and_the_note_after_continues_it(tmp_path):
    """Rejects the chord bars staying refused, the tie on a strike or every head, or a destination elsewhere."""
    _check_chord_bars(tmp_path)


def test_a_chain_whose_arcs_are_not_all_read_stays_refused(tmp_path):
    """Rejects writing Lesson-6 bar 26: its last chord ties three heads to the next chord, two arcs are read."""
    bars, _ = _convert("Lesson-6", tmp_path)
    assert bars[26]["status"] == "refused", "UNCONFIRMED_TIE_BAR_WRITTEN"
    assert bars[26]["reason"] == "tie_head_ownership_unconfirmed", "REFUSAL_NOT_LOCATED"
    assert bars[27]["status"] == "written", "NEXT_BAR_LOST"


def test_mutant_drop_rule_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(assembler, "ENABLE_HEAD_OWNED_TIES", False)
    with pytest.raises(AssertionError):
        _check_chord_bars(tmp_path)


def test_mutant_drop_reader_ownership_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "ENABLE_TIED_HEAD_OWNERSHIP", False)
    with pytest.raises(AssertionError):
        _check_chord_bars(tmp_path)


def test_mutant_tie_every_head_fails(tmp_path, monkeypatch):
    real = factory.build_note_type_event

    def tie_all(record, **kwargs):
        kwargs["tie_states"] = None
        return real(record, **kwargs)

    monkeypatch.setattr(assembler, "build_note_type_event", tie_all)
    with pytest.raises(AssertionError):
        _check_chord_bars(tmp_path)


def test_mutant_skip_consumer_check_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(assembler, "_accounts_for", lambda *args, **kwargs: True)
    with pytest.raises(AssertionError):
        _convert_lesson6_bar_26_is_refused(tmp_path)


def _convert_lesson6_bar_26_is_refused(tmp_path):
    bars, _ = _convert("Lesson-6", tmp_path)
    assert bars[26]["status"] == "refused", "UNCONFIRMED_TIE_BAR_WRITTEN"
