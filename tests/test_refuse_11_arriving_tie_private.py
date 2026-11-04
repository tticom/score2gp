"""Real-source ties that arrive from the previous system (REFUSE-11).

Re-measured over the whole private set, the largest refusal class that is a reader gap with an unambiguous
musical symbol was the note a tie carries over a system break: the previous system's last note prints a tie
arc that runs off the system end, the next system's first note prints an arc coming in from the left margin
and no TAB digit (the TAB prints an empty "( )" there). The reader marked only the leaving side, so the
route found a notation note with no TAB column and refused the bar (`notation_note_without_tab_digit`).

The route now ties the two only when BOTH ends are drawn and agree: the previous written note's tie left its
system at one staff position and the arc arriving on the next system's first note ends at that same position
(single heads). Nothing is counted or spaced; a note without the previous written bar stays refused, now with
its true cause `tie_stop_without_written_predecessor`.

Sources (all reference-less: no `.gp` exists for them, so each newly written bar was checked against the
PRINTED PAGE by the author and by the bar-total gate; they are NOT independently verified against a reference
file): `Brown Sugar.pdf` bar 4, `Back In Black.pdf` bar 4, `Crossroads.pdf` bars 21 and 23. `Black Dog.pdf`
bar 3 and `Crossroads.pdf` bar 26 print the same tie but the bar before them is refused, so they stay refused.
Synthetic tests carry no acceptance weight; none are used. Mutants (each fails a test below):
  DROP_ARRIVING_TIE      `note_duration.ENABLE_ARRIVING_TIE` False: the four bars stay refused.
  NO_TIE_STOP            the written continuation loses its tie stop: the page's tie is dropped from the IR.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp import pdf_tab_bar_assembler as assembler
from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"

WRITTEN = {"Brown Sugar": (4,), "Back In Black": (4,), "Crossroads": (21, 23)}
STAY_REFUSED = {"Black Dog": (3,), "Crossroads": (26,)}


def _convert(source, tmp_path):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_REFUSE_11_SOURCE_MISSING"
    build = tmp_path / source.replace(" ", "_")
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                             "--out", str(build / "output.gp"), "--work-dir", str(build / "w")])
    route = json.loads((build / "w" / "note-type-route.json").read_bytes())
    ir = json.loads((build / "w" / "score.ir.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, {b["index"]: b for b in ir["bars"]}


def _notes(ir_bar, last):
    event = ir_bar["events"][-1 if last else 0]
    return [(n["string"], n["fret"], tuple(t["state"] for t in n["techniques"] if t["kind"] == "tie"))
            for n in event["notes"]]


def _check_written(source, tmp_path):
    bars, ir = _convert(source, tmp_path)
    for bar in WRITTEN[source]:
        assert bars[bar]["status"] == "written", f"BAR_REFUSED_{source}_{bar}"
        first = bars[bar]["events"][0]["match"]
        assert first["kind"] == "tie_continuation" and first["tie_from_previous_system"] is True, "NOT_A_TIE"
        # the previous (written) bar's last note is the same string and fret, tie start -> stop
        assert bars[bar - 1]["status"] == "written", "PREDECESSOR_REFUSED"
        # IR bar indices are one-based: IR bar `bar` is source bar `bar - 1`.
        after, last = _notes(ir[bar + 1], False), _notes(ir[bar], True)
        assert [(s, f) for s, f, _ in after] == [(s, f) for s, f, _ in last], "TIED_NOTE_POSITION"
        assert "start" in last[0][2] and "stop" in after[0][2], "TIE_TECHNIQUE_MISSING"


def _check_stay_refused(source, tmp_path):
    bars, _ir = _convert(source, tmp_path)
    for bar in STAY_REFUSED[source]:
        assert bars[bar]["status"] == "refused", f"BAR_WRITTEN_{source}_{bar}"
        evidence = bars[bar]["refusal_evidence"]
        assert evidence["cause"] == "tie_stop_without_written_predecessor", "REFUSAL_NOT_LOCATED"


@pytest.mark.parametrize("source", list(WRITTEN))
def test_system_break_ties_are_written_and_match_the_printed_page(tmp_path, source):
    """Rejects a note tied over a system break being refused, written at another position, or without its tie."""
    _check_written(source, tmp_path)


@pytest.mark.parametrize("source", list(STAY_REFUSED))
def test_tie_without_written_predecessor_stays_refused_and_says_why(tmp_path, source):
    """Rejects writing a tied note whose previous bar is refused, or leaving the refusal's cause unlocated."""
    _check_stay_refused(source, tmp_path)


def test_mutant_drop_arriving_tie_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "ENABLE_ARRIVING_TIE", False)
    with pytest.raises(AssertionError):
        _check_written("Brown Sugar", tmp_path)
    with pytest.raises(AssertionError):
        _check_stay_refused("Black Dog", tmp_path)


def test_mutant_no_tie_stop_fails(tmp_path, monkeypatch):
    real = assembler.build_note_type_event

    def without_stop(record, **kwargs):
        tie = {**(record.get("tie") or {}), "stop": False}
        return real({**record, "tie": tie}, **kwargs)

    monkeypatch.setattr(assembler, "build_note_type_event", without_stop)
    with pytest.raises(AssertionError):
        _check_written("Brown Sugar", tmp_path)
