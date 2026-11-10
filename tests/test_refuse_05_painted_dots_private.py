"""Real-source augmentation dots painted as zero-length round-capped strokes (REFUSE-05).

Four sources paint some augmentation dots as a stroked point (one zero-length line, round caps, a
stroke width about 0.4 staff space) rather than a filled shape, a text character or a font outline. The
duration reader dropped them, the dotted note or rest counted at its undotted value and the bar totalled
short (bar_total_mismatch), the following tied bar then cascading.

Oracle: no reference GP exists for these four sources, so each expected value below is the printed
dotted event, read off the rendered page by eye (counts and note values only): NOT independently
verified against a reference. Synthetic tests carry no acceptance weight; the one synthetic test at the
end exercises only the attachment-ambiguity infrastructure and is labelled so. Mutants:
  DROP_POINT_DOT_READER  `_stroked_point_dot` returns None: no dot is read, the bars total short.
  WRONG_NOTE             `_dot_fits` lets the first event take every dot: dots land on the wrong notes.
  DOT_FROM_BAR_TOTAL     dots are read from nothing; a short bar then dots the first event whose dot would
                         make the total match. It must differ from the printed dots on a real source.
"""
import json
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd
from test_dur_02_oracle import read_gp_bars

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
# source -> {source bar index: {event index: (kind, written note value)}}: every dotted event in the bar,
# one dot each, as printed.
DOTTED = {
    "Black Dog.pdf": {0: {2: ("rest", "eighth")}, 2: {5: ("chord", "eighth")}, 4: {15: ("chord", "eighth")},
                      6: {6: ("note", "eighth")}, 8: {19: ("chord", "quarter")}},
    "Castles Made of Sand.pdf": {0: {1: ("note", "16th"), 3: ("note", "16th")}, 1: {7: ("note", "16th")},
                                 3: {14: ("note", "eighth")}, 6: {13: ("chord", "eighth")}},
    "Crossroads.pdf": {1: {1: ("note", "half")}, 3: {2: ("rest", "quarter")}, 7: {3: ("chord", "quarter")},
                       9: {9: ("note", "eighth")}, 10: {5: ("note", "eighth")}, 18: {8: ("chord", "eighth")},
                       24: {6: ("chord", "eighth")}},
    "Heartbreaker.pdf": {4: {2: ("note", "half")}},
}
# Bars that totalled short before the dot was read and now total the printed meter.
NOW_MATCH = {"Black Dog.pdf": [0, 8], "Castles Made of Sand.pdf": [1, 6],
             "Crossroads.pdf": [3, 9, 10, 24], "Heartbreaker.pdf": [4]}


def _read(source: str) -> dict:
    path = PRIVATE / source
    assert path.is_file(), "REQUIRED_REFUSE_05_PDF_MISSING"
    return nd.read_note_durations(path)


def _check(source: str, result: dict) -> None:
    for bar, dotted in DOTTED[source].items():
        events = [e for e in result["events"] if e["bar_index"] == bar]
        got = {e["event_index"]: (e["kind"], e["written"]) for e in events if e["dots"]["count"]}
        assert got == dotted, f"DOTTED_EVENTS_{bar}"
        assert all(e["dots"]["count"] == 1 for e in events if e["dots"]["count"]), f"DOT_COUNT_{bar}"
    checks = {c["bar_index"]: c["status"] for c in result["bar_checks"]}
    for bar in NOW_MATCH[source]:
        assert checks[bar] == "match", f"BAR_TOTAL_{bar}"


@pytest.mark.parametrize("source", sorted(DOTTED))
def test_painted_point_dots_attach_to_the_printed_note(source):
    """Rejects a reader that misses the dot, puts it on another event, or reads two."""
    _check(source, _read(source))


@pytest.mark.parametrize("source", ["Black Dog.pdf", "Crossroads.pdf"])
def test_mutant_drop_point_dot_reader_fails(monkeypatch, source):
    monkeypatch.setattr(nd, "_stroked_point_dot", lambda drawing, items: None)
    with pytest.raises(AssertionError):
        _check(source, _read(source))


@pytest.mark.parametrize("source", ["Black Dog.pdf", "Crossroads.pdf"])
def test_mutant_dot_on_wrong_note_fails(monkeypatch, source):
    monkeypatch.setattr(nd, "_dot_fits", lambda dot, anchor, edge, row, space, rest: not row)
    with pytest.raises(AssertionError):
        _check(source, _read(source))


def _dot_from_bar_total(result: dict) -> dict:
    """The forbidden inference: where a bar totals short, dot the first event the deficit would fit."""
    for check in result["bar_checks"]:
        if check["status"] != "mismatch":
            continue
        deficit = Fraction(check["expected_quarters"]) - Fraction(check["total_quarters"])
        for e in [e for e in result["events"] if e["bar_index"] == check["bar_index"] and e["duration_quarters"]]:
            if deficit > 0 and Fraction(e["duration_quarters"]) / 2 == deficit:
                e["dots"]["count"] = 1
                check["status"] = "match"
                break
    return result


@pytest.mark.parametrize("source", ["Black Dog.pdf", "Castles Made of Sand.pdf", "Crossroads.pdf"])
def test_mutant_dot_from_bar_total_is_rejected(monkeypatch, source):
    """The total is the check, not the evidence: inferring dots from it must disagree with the page."""
    monkeypatch.setattr(nd, "_stroked_point_dot", lambda drawing, items: None)
    with pytest.raises(AssertionError):
        _check(source, _dot_from_bar_total(_read(source)))


def test_black_dog_dotted_bars_are_written_with_printed_durations(tmp_path):
    """Rejects a refused bar or a wrong dotted duration in the written GPIF (not independently verified)."""
    output, build = tmp_path / "output.gp", tmp_path / "build"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(PRIVATE / "Black Dog.pdf"), "--pdf-only-tab",
                                      "--out", str(output), "--work-dir", str(build)])
    assert result.exit_code == 0, f"REFUSE_05_CLI_EXIT_{result.exit_code}"
    route = json.loads((build / "note-type-route.json").read_bytes())
    packaged = read_gp_bars(output)
    for bar, dotted in ((0, {2: ("eighth", 1)}), (8, {19: ("quarter", 1)})):
        entry = next(b for b in route["bars"] if b["source_bar_index"] == bar)
        assert entry["status"] == "written", f"BAR_REFUSED_{bar}"
        events = packaged[entry["output_bar_index"] - 1]["events"]
        assert sum(1 for e in events if e["dots"]) == len(dotted), f"GPIF_DOT_COUNT_{bar}"
        for index, expected in dotted.items():
            dotted_event = next(e for e in route["bars"] if e is entry)["events"][index]["event_index"]
            assert dotted_event == index
            assert any((e["written"], e["dots"]) == expected for e in events), f"GPIF_DOT_{bar}"


def test_brown_sugar_short_bar_is_settled_without_a_dot():
    """REFUSE-05 left this short bar refused because nothing is painted as a dot in it. DUR-04 settles it from a
    different printed symbol (the "3" scoped to the notes it stands over); no dot is read or invented.

    Mutant: painting a dot onto a note to make the bar fit would leave a dot in this bar.
    """
    result = _read("Brown Sugar.pdf")
    checks = {c["bar_index"]: c["status"] for c in result["bar_checks"]}
    assert checks[7] == "match", "BROWN_SUGAR_BAR_7_STILL_SHORT"
    events = [e for e in result["events"] if e["bar_index"] == 7]
    assert not any(e["dots"]["count"] for e in events), "BROWN_SUGAR_BAR_7_DOT_INVENTED"
    assert sum(1 for e in events if e["tuplet"]) == 3


def _fake_event(x0, y0, x1, y1, dots=()):
    head = SimpleNamespace(bbox=(x0, y0, x1, y1))
    return {"_heads": [head], "_dots": [list(dots)] if dots else []}


def test_synthetic_point_dot_between_two_events_is_left_unread():
    """SYNTHETIC infrastructure only, zero acceptance weight: a dot two events accept is ambiguous.

    Mutant: `_ambiguous_point_dots` returning an empty set lets the dot stay on one of them.
    """
    dot = SimpleNamespace(ident="d", bbox=(104.0, 99.0, 105.6, 100.6), cy=99.8,
                          drawing={"source_form": nd.POINT_DOT_FORM})
    owner = _fake_event(95.0, 98.0, 100.0, 102.0, [dot])
    other = _fake_event(98.0, 98.0, 103.0, 102.0)
    assert nd._ambiguous_point_dots([owner, other], 4.0) == {"d"}
    assert nd._ambiguous_point_dots([owner], 4.0) == set()
