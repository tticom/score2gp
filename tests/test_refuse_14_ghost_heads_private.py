"""Real-source ghost (parenthesised) heads (REFUSE-14).

A head enclosed by its own printed parenthesis pair is the notation for a ghost note. Six bars were refused for it
(`parenthesized_head_unrepresented`) only because the score model had no ghost flag. Bars read now:
`Ex 2 Hands Up.pdf` bars 7, 9, 10 and `Derek Trucks BB King.pdf` bars 0, 9, 14. Both have a reference `.gp`, and
each newly written bar is compared with the reference bar (notes, string, fret, note value and ghost flag; the
reference bar is found by content, not by an offset constant). Synthetic tests carry no acceptance weight: none are
used. `Melodic Soloing Masterclass.pdf` bar 7 prints a parenthesised head the reference does not mark as ghost and the
bar was written before; it must stay byte-identical (no ghost flag). `Derek Trucks BB King.pdf` bar 15 keeps another
overlapping form beside its parenthesis and must stay refused. Mutants (each fails a test below):
  DROP_GHOST_FLAG      the event factory never sets `is_ghost`: the written bars lose the ghost flag.
  DROP_GHOST_RULE      the reader never marks a fully parenthesised event as ghost: the bars stay refused.
  GHOST_OVERRIDES_BASE a written bar's ghost flag is kept: the Melodic Soloing Masterclass bar changes.
"""
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp import pdf_tab_bar_assembler as assembler
from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
CASES = {"Ex 2 Hands Up": (7, 9, 10), "Derek Trucks BB King": (0, 9, 14)}


def _convert(source, tmp_path):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_REFUSE_14_SOURCE_MISSING"
    build = tmp_path / "build"
    out = tmp_path / "output.gp"
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(out),
                             "--work-dir", str(build)])
    route = json.loads((build / "note-type-route.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, out


def _gpif_bars(path):
    """Per bar (voice 1): [(note value, sorted (string, fret, ghost) notes)]."""
    root = ET.fromstring(zipfile.ZipFile(path).read("Content/score.gpif"))
    notes = {n.get("id"): n for n in root.find("Notes")}
    beats = {b.get("id"): b for b in root.find("Beats")}
    rhythms = {r.get("id"): r for r in root.find("Rhythms")}
    voices = {v.get("id"): v for v in root.find("Voices")}
    bars = {b.get("id"): b for b in root.find("Bars")}
    out = []
    for master in root.find("MasterBars"):
        voice_id = bars[master.find("Bars").text.split()[0]].find("Voices").text.split()[0]
        sequence = []
        if voice_id != "-1":
            for beat_id in voices[voice_id].find("Beats").text.split():
                beat = beats[beat_id]
                found = []
                if beat.find("Notes") is not None:
                    for note_id in beat.find("Notes").text.split():
                        note = notes[note_id]
                        props = {p.get("name"): p for p in note.find("Properties")}
                        found.append((int(props["String"][0].text), int(props["Fret"][0].text),
                                      note.find("AntiAccent") is not None))
                sequence.append((rhythms[beat.find("Rhythm").get("ref")].find("NoteValue").text, tuple(sorted(found))))
        out.append(sequence)
    return out


def _check_ghost_bars(tmp_path):
    for source, bars_expected in CASES.items():
        sub = tmp_path / source.replace(" ", "_")
        sub.mkdir()
        bars, out = _convert(source, sub)
        ours = _gpif_bars(out)
        reference = _gpif_bars(PRIVATE / f"{source}.gp")
        for bar in bars_expected:
            assert bars[bar]["status"] == "written", f"{source}_BAR_{bar}_REFUSED"
            written = ours[bars[bar]["output_bar_index"] - 1]
            assert any(note[2] for _value, found in written for note in found), f"{source}_BAR_{bar}_NO_GHOST_FLAG"
            assert written in reference, f"{source}_BAR_{bar}_DIFFERS_FROM_REFERENCE"


def _check_written_bar_unchanged(tmp_path):
    bars, out = _convert("Melodic Soloing Masterclass", tmp_path)
    assert bars[7]["status"] == "written"
    assert not any(note[2] for bar in _gpif_bars(out) for _value, found in bar for note in found), \
        "WRITTEN_BAR_GAINED_GHOST_FLAG"


def test_ghost_bars_are_written_and_match_their_reference(tmp_path):
    """Rejects a parenthesised head refusing its bar, or written without the ghost flag, or with another note."""
    _check_ghost_bars(tmp_path)


def test_bar_with_a_second_overlapping_form_stays_refused(tmp_path):
    """Rejects a ghost reading that also writes a bar holding an unread accidental/overlap form."""
    bars, _out = _convert("Derek Trucks BB King", tmp_path)
    assert bars[15]["status"] == "refused", "DEREK_BAR_15_MUST_STAY_REFUSED"


def test_previously_written_parenthesised_bar_is_unchanged(tmp_path):
    """Rejects a ghost flag appearing in a bar that was already written (its reference carries none)."""
    _check_written_bar_unchanged(tmp_path)


def test_mutant_drop_ghost_flag_fails(tmp_path, monkeypatch):
    real = assembler.build_note_type_event

    def no_ghost(record, **kwargs):
        record = {k: v for k, v in record.items() if k != "ghost"}
        return real(record, **kwargs)

    monkeypatch.setattr(assembler, "build_note_type_event", no_ghost)
    with pytest.raises(AssertionError):
        _check_ghost_bars(tmp_path)


def test_mutant_drop_ghost_rule_fails(tmp_path, monkeypatch):
    real = nd._record

    def no_ghost(event, *args, **kwargs):
        event.pop("_ghost", None)
        return real(event, *args, **kwargs)

    monkeypatch.setattr(nd, "_record", no_ghost)
    with pytest.raises(AssertionError):
        _check_ghost_bars(tmp_path)


def test_mutant_ghost_overrides_written_bar_fails(tmp_path, monkeypatch):
    real = assembler.build_note_type_event

    def keep_ghost(record, **kwargs):
        if record.get("unread_symbols"):
            record = {**record, "ghost": {"parenthesis_sources": []}}
        return real(record, **kwargs)

    monkeypatch.setattr(assembler, "build_note_type_event", keep_ghost)
    with pytest.raises(AssertionError):
        _check_written_bar_unchanged(tmp_path)
