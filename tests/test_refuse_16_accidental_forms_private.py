"""Real-source accidentals printed at grace size, and accidentals inside a ghost head's parentheses (REFUSE-16).

Two printed forms whose meaning is fixed by notation were left unread, which refused their bars as
`unsupported_overlapping_form`:
  * a sharp, flat or natural set at grace size just left of a grace head (`Pride and Joy.pdf` bar 4);
  * a head's own accidental standing inside its parentheses, so the left parenthesis abuts the accidental, not
    the head (`Derek Trucks BB King.pdf` bar 13): a ghost note (REFUSE-14).
The accidental never decides string or fret (the TAB digit does); it is only recognised so that the bar is no
longer refused for an unread form. Written bars: `Derek Trucks BB King` bars 2 and 13 equal the reference `.gp`
bar (found by content, ghost flag included). `Pride and Joy` bar 4 has no reference file: it is checked against
the printed page (ten events, two of them grace notes) and is NOT independently verified against a file.
Bars 4, 6 and 15 of `Derek Trucks BB King` carry other unread forms (accidental too small for the measured
scale, a bend/slide arc) and must stay refused. Synthetic tests carry no acceptance weight: none are used.
Mutants (each fails a test below):
  DROP_GRACE_ACCIDENTAL_RULE  the grace-size accidental is never read: Pride and Joy bar 4 stays refused.
  FULL_SIZE_SCALE             the grace accidental is judged at full-size scale: Pride and Joy bar 4 stays refused.
  DROP_PARENTHESIS_ACCIDENTAL a left parenthesis may only abut the head: Derek Trucks bars 2 and 13 stay refused.
"""
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

from tests.test_refuse_14_ghost_heads_private import _gpif_bars

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


def _convert(source, tmp_path):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_REFUSE_16_SOURCE_MISSING"
    build = tmp_path / "build"
    out = tmp_path / "output.gp"
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(out),
                             "--work-dir", str(build)])
    route = json.loads((build / "note-type-route.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, out


def _check_ghost_accidental_bars(tmp_path):
    bars, out = _convert("Derek Trucks BB King", tmp_path)
    ours = _gpif_bars(out)
    reference = _gpif_bars(PRIVATE / "Derek Trucks BB King.gp")
    bar = 13
    assert bars[bar]["status"] == "written", f"DEREK_BAR_{bar}_REFUSED"
    written = ours[bars[bar]["output_bar_index"] - 1]
    assert any(note[2] for _value, found in written for note in found), f"DEREK_BAR_{bar}_NO_GHOST_FLAG"
    assert written in reference, f"DEREK_BAR_{bar}_DIFFERS_FROM_REFERENCE"
    return bars


def _check_grace_accidental_bar(tmp_path):
    bars, out = _convert("Pride and Joy", tmp_path)
    assert bars[4]["status"] == "written", "PRIDE_BAR_4_REFUSED"
    root = ET.fromstring(zipfile.ZipFile(out).read("Content/score.gpif"))
    bar_row = root.find("MasterBars")[bars[4]["output_bar_index"] - 1]
    bar = {b.get("id"): b for b in root.find("Bars")}[bar_row.find("Bars").text.split()[0]]
    voice = {v.get("id"): v for v in root.find("Voices")}[bar.find("Voices").text.split()[0]]
    beats = {b.get("id"): b for b in root.find("Beats")}
    sequence = [beats[i] for i in voice.find("Beats").text.split()]
    # The printed page: three eighths, a grace and a quarter, a grace and a half, three eighths.
    assert len(sequence) == 10, "PRIDE_BAR_4_EVENT_COUNT_DIFFERS_FROM_PRINT"
    assert sum(1 for b in sequence if b.find("GraceNotes") is not None) == 2, "PRIDE_BAR_4_GRACE_COUNT_DIFFERS_FROM_PRINT"


def test_parenthesised_accidental_heads_are_written_and_match_their_reference(tmp_path):
    """Rejects a ghost head with its own accidental refusing its bar, or written without the ghost flag."""
    _check_ghost_accidental_bars(tmp_path)


def test_grace_size_accidental_bar_is_written_and_matches_the_printed_page(tmp_path):
    """Rejects a grace-size accidental refusing its bar, or a different event/grace count from the print."""
    _check_grace_accidental_bar(tmp_path)


def test_bars_with_other_unread_forms_stay_refused(tmp_path):
    """Rejects a rule wide enough to write a bar that still holds another unread overlapping form."""
    bars, _out = _convert("Derek Trucks BB King", tmp_path)
    for bar in (2, 4, 6, 15):
        assert bars[bar]["status"] == "refused", f"DEREK_BAR_{bar}_MUST_STAY_REFUSED"


def test_mutant_drop_grace_accidental_rule_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_grace_scale_accidental_direction", lambda *args, **kwargs: None)
    with pytest.raises(AssertionError):
        _check_grace_accidental_bar(tmp_path)


def test_mutant_full_size_scale_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_grace_scale_accidental_direction",
                        lambda glyph, space, heads, small_ids: nd._accidental_direction(glyph, space))
    with pytest.raises(AssertionError):
        _check_grace_accidental_bar(tmp_path)


def test_mutant_drop_parenthesis_accidental_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_parenthesis_inner_edges", lambda head, glyphs, space: [head.bbox[0]])
    with pytest.raises(AssertionError):
        _check_ghost_accidental_bars(tmp_path)
