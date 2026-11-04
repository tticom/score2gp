"""Real-source chord whose one head is the end of a tie (REFUSE-12).

Whole-set re-measurement after REFUSE-11 (counts and codes only): the refusal classes with the most bars are
(1) a TAB that prints no rhythm at all (`tab_column_without_rhythm_mark`, one source) and (2) bars with nothing
printed (`bar_without_notation_or_tab_item`): neither can be read without counting or spacing, which the task
forbids, so they are not reader gaps. Of the classes that are reader gaps with an unambiguous symbol, the
largest this task could read safely is the chord whose single head is tied from the note before it: the tie arc
ends on ONE head, that head prints no TAB digit, the other head prints its digit. The route refused it
(`notehead_digit_count_mismatch`, two heads and one digit).

The reader now records which head the arc ends on (`tie.stop_head_positions`); the route writes the bar only
when the arc is one drawing shared by the note before and this chord, ends on exactly one head, and that head
is the only one without a digit. The tied head copies the previous note's string and fret and carries the tie
stop; the digit's head carries none.

Source with a reference: `Lesson-5.pdf` bar 17 (checked bar-for-bar against `Lesson-5.gp`, read at test time,
not copied). `E_Chord_Lick_Chord.pdf` bar 7 passes this chord but stays refused at a later event, and
`Lesson-6.pdf` bar 26 (tie both ends on the chord, head ownership of the outgoing tie unread) stays refused.
Synthetic tests carry no acceptance weight; none are used. Mutants (each fails a test below):
  DROP_PARTIAL_TIE       `assembler.ENABLE_PARTIAL_TIE` False: the Lesson-5 bar stays refused.
  DROP_HEAD_OWNERSHIP    `note_duration.ENABLE_TIED_HEAD_OWNERSHIP` False: the reader names no tied head, so refused.
  TIE_EVERY_HEAD         the tie stop is put on every note of the chord (event-level tie): the untied head is wrong.
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
SOURCE_BAR = 17  # Lesson-5.pdf, zero-based source bar index


def _convert(source, tmp_path):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_REFUSE_12_SOURCE_MISSING"
    build = tmp_path / source.replace(" ", "_")
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                             "--out", str(build / "output.gp"), "--work-dir", str(build / "w")])
    route = json.loads((build / "w" / "note-type-route.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, build / "output.gp"


def _beats(gp_path, bar_index):
    """[(note value, dots, [(string, fret, tie)])] for every beat of one bar of a Guitar Pro file."""
    root = ET.fromstring(zipfile.ZipFile(gp_path).read("Content/score.gpif"))
    voices = {v.get("id"): v for v in root.find("Voices")}
    beats = {b.get("id"): b for b in root.find("Beats")}
    notes = {n.get("id"): n for n in root.find("Notes")}
    rhythms = {r.get("id"): r for r in root.find("Rhythms")}
    out = []
    for voice_id in root.find("Bars")[bar_index].find("Voices").text.split():
        if voice_id == "-1":
            continue
        for beat_id in voices[voice_id].find("Beats").text.split():
            beat = beats[beat_id]
            rhythm = rhythms[beat.find("Rhythm").get("ref")]
            dots = rhythm.find("AugmentationDot")
            played = []
            for note_id in (beat.find("Notes").text.split() if beat.find("Notes") is not None else []):
                note = notes[note_id]
                props = {p.get("name"): p for p in note.find("Properties")}
                tie = note.find("Tie")
                played.append((props["String"].find("String").text, props["Fret"].find("Fret").text,
                               tuple(sorted(tie.attrib.items())) if tie is not None else None))
            out.append((rhythm.find("NoteValue").text, dots.get("count") if dots is not None else 0, sorted(played)))
    return out


def _check_written_like_the_reference(tmp_path):
    bars, output = _convert("Lesson-5", tmp_path)
    assert bars[SOURCE_BAR]["status"] == "written", "PARTIAL_TIE_CHORD_BAR_REFUSED"
    kinds = [e["match"]["kind"] for e in bars[SOURCE_BAR]["events"]]
    assert kinds[-1] == "tab_column_with_tie_continuation", "CHORD_NOT_READ_AS_PARTIAL_TIE"
    reference = PRIVATE / "Lesson-5.gp"
    assert reference.is_file(), "REQUIRED_REFUSE_12_REFERENCE_MISSING"
    assert _beats(output, SOURCE_BAR) == _beats(reference, SOURCE_BAR), "BAR_DIFFERS_FROM_REFERENCE"


def test_partial_tie_chord_is_written_and_equals_the_reference(tmp_path):
    """Rejects the chord bar staying refused, the tied head at another string/fret, or the tie on the wrong head."""
    _check_written_like_the_reference(tmp_path)


@pytest.mark.parametrize("source,bar", [("Lesson-6", 26), ("E_Chord_Lick_Chord", 7)])
def test_bars_not_settled_by_the_tie_stay_refused(tmp_path, source, bar):
    """Rejects widening the rule to a chord whose outgoing tie head is unread, or past a later unreadable event."""
    bars, _ = _convert(source, tmp_path)
    assert bars[bar]["status"] == "refused", f"BAR_WRITTEN_{source}_{bar}"
    assert bars[bar]["reason"] == "notehead_digit_count_mismatch", "REFUSAL_NOT_LOCATED"


def test_mutant_drop_partial_tie_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(assembler, "ENABLE_PARTIAL_TIE", False)
    with pytest.raises(AssertionError):
        _check_written_like_the_reference(tmp_path)


def test_mutant_drop_head_ownership_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "ENABLE_TIED_HEAD_OWNERSHIP", False)
    with pytest.raises(AssertionError):
        _check_written_like_the_reference(tmp_path)


def test_mutant_tie_every_head_fails(tmp_path, monkeypatch):
    real = factory.build_note_type_event

    def tie_all(record, **kwargs):
        kwargs["tied_positions"] = None
        return real(record, **kwargs)

    monkeypatch.setattr(assembler, "build_note_type_event", tie_all)
    with pytest.raises(AssertionError):
        _check_written_like_the_reference(tmp_path)
