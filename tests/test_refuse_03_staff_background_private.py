"""Real-source bars whose rests were hidden by a page-background shape (REFUSE-03).

A shape whose box encloses the whole staff (a page background fill) sorted first in the staff-header
scan, so the "header" ran to the staff's right edge and every rest on that staff was skipped: rest-only
bars were refused as bar_without_notation_event and bars missing a printed rest as bar_total_mismatch.

Oracle: where a reference GP exists (Ex 2 Hands Up) the written bar is compared with it; the other
sources have none and are checked against the printed notation (not independently verified).
Synthetic tests have no acceptance weight; none are used here. Mutant:
  DROP_BACKGROUND_RULE  `_covers_staff` returns False, so the background shape is a glyph of the staff
                        again and the rests are lost. Each real-source assertion below must fail.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd
from test_dur_02_oracle import read_gp_bars

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
# Zero-based source bar index -> printed (kind, written type, dots) per event, in order. Counts of printed
# values only; a chord is one event. The 9-event bar holds one printed triplet of three eighths.
EXPECTED = {
    "Just-Practice-Like-THIS-Every-Day.pdf": {
        10: [("rest", "eighth", 0)] + [("note", "eighth", 0)] * 8,
        11: [("note", "quarter", 0)] * 2 + [("rest", "half", 0)],
        12: [("rest", "whole", 0)], 13: [("rest", "whole", 0)],
        14: [("rest", "whole", 0)], 15: [("rest", "whole", 0)],
    },
    "The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord.pdf": {
        69: [("rest", "whole", 0)], 70: [("rest", "whole", 0)],
        71: [("rest", "whole", 0)], 72: [("rest", "whole", 0)],
    },
    "Melodic_Expressions_Chap_19_.pdf": {
        2: [("note", "eighth", 0), ("note", "half", 1), ("rest", "eighth", 0)],
        3: [("note", "eighth", 0), ("note", "half", 1), ("rest", "eighth", 0)],
    },
}


def _printed(source: str, bars: dict):
    path = PRIVATE / source
    assert path.is_file(), "REQUIRED_REFUSE_03_PDF_MISSING"
    result = nd.read_note_durations(path)
    checks = {c["bar_index"]: c for c in result["bar_checks"]}
    for bar, expected in bars.items():
        events = sorted((e for e in result["events"] if e["bar_index"] == bar), key=lambda e: e["event_index"])
        got = [("rest" if e["kind"] == "rest" else "note", e["written"], e["dots"]["count"]) for e in events]
        assert got == expected, f"PRINTED_EVENTS_{bar}"
        assert checks[bar]["status"] == "match", f"BAR_TOTAL_{bar}"


@pytest.mark.parametrize("source", sorted(EXPECTED))
def test_rests_on_background_staves_are_read(source):
    """Rejects the reader that loses a rest on a staff that has a background shape."""
    _printed(source, EXPECTED[source])


def test_mutant_without_background_rule_loses_the_rests(monkeypatch):
    """Rejects dropping the rule: the rest-only bars lose their rests on a real source."""
    monkeypatch.setattr(nd, "_covers_staff", lambda glyph, staff: False)
    with pytest.raises(AssertionError):
        _printed("Just-Practice-Like-THIS-Every-Day.pdf", EXPECTED["Just-Practice-Like-THIS-Every-Day.pdf"])


def _convert(source: str, tmp_path):
    output, build = tmp_path / "output.gp", tmp_path / "build"
    result = CliRunner().invoke(app, [
        "convert", "--pdf", str(PRIVATE / source), "--pdf-only-tab", "--out", str(output),
        "--work-dir", str(build)])
    assert result.exit_code == 0, f"REFUSE_03_CLI_EXIT_{result.exit_code}"
    return output, json.loads((build / "note-type-route.json").read_bytes())


def test_just_practice_bars_are_written_with_printed_rhythm(tmp_path):
    """Rejects a refused bar, a wrong duration or a lost rest in the written GPIF."""
    source = "Just-Practice-Like-THIS-Every-Day.pdf"
    output, route = _convert(source, tmp_path)
    packaged = read_gp_bars(output)
    for bar, expected in EXPECTED[source].items():
        entry = next(b for b in route["bars"] if b["source_bar_index"] == bar)
        assert entry["status"] == "written", f"BAR_REFUSED_{bar}"
        events = packaged[entry["output_bar_index"] - 1]["events"]
        assert [(("rest" if e["kind"] == "rest" else "note"), e["written"], e["dots"]) for e in events] == expected, \
            f"GPIF_RHYTHM_{bar}"


def test_ex_2_hands_up_bar_matches_reference(tmp_path):
    """Rejects a written bar whose rhythm differs from the reference GP (independent oracle)."""
    reference = PRIVATE / "Ex 2 Hands Up.gp"
    assert reference.is_file(), "REQUIRED_REFUSE_03_REFERENCE_MISSING"
    output, route = _convert("Ex 2 Hands Up.pdf", tmp_path)
    entry = next(b for b in route["bars"] if b["source_bar_index"] == 10)
    assert entry["status"] == "written", "EX2_BAR_REFUSED"
    # REFUSE-17: the clef/start-repeat stub is no bar, so output bar n is the reference's bar n.
    shape = lambda events: [(e["kind"], e["written"], e["dots"]) for e in events]  # noqa: E731
    written = shape(read_gp_bars(output)[entry["output_bar_index"] - 1]["events"])
    expected = shape(read_gp_bars(reference)[entry["output_bar_index"] - 1]["events"])
    assert written == expected, "EX2_BAR_DIFFERS_FROM_REFERENCE"
