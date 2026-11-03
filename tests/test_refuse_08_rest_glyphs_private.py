"""Real-source rest glyphs (REFUSE-08).

Two reader gaps refused bars whose rest glyph was a plain, readable rest:

* ``rest_glyph_beside_note``: a rest whose own form fixes its value, standing just left of a notehead
  where an accidental would stand, was filed as an overlapping form and its whole bar refused.
* a sixteenth rest was counted as an eighth: the stem-removal cut left slivers (<= 0.1 space) on the slanted
  stem that joined the two hook balls into one piece. The wrong value overshot the bar total, so bars were
  refused as ``bar_total_mismatch`` (or written with a wrong value where no total check caught it).

Sources: ``Black Dog.pdf`` (bar 5), ``Hey Joe.pdf`` (bars 2, 6), ``Brown Sugar.pdf`` (bar 6) and
``The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord.pdf`` (bar 91). None has a reference .gp in the
approved corpus: the oracle is the PRINTED PAGE, read by the author (hook count of each rest glyph), so these
are NOT independently verified against a reference file. Synthetic tests carry no acceptance weight; none are
used. Mutants:
  DROP_REST_BESIDE_RULE   `_rest_form_outranks_accidental_position` returns False: Black Dog 5, Hey Joe 2 and 6
                          and The_EXACT 91 stay refused (rest_glyph_beside_note).
  DROP_SLIVER_RULE        REST_HOOK_MIN_WIDTH_SPACES ~ 0: the sixteenth rests read as eighth (Hey Joe, Black Dog,
                          Brown Sugar), so the value check fails.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
EXACT = "The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord"
# bar -> {event_index: written value of the rest}, read off the printed page.
EXPECTED = {
    "Black Dog": {5: {0: "16th"}},
    "Hey Joe": {2: {4: "16th", 11: "16th"}, 6: {2: "16th"}},
    "Brown Sugar": {6: {15: "16th"}},
    EXACT: {91: {2: "eighth", 4: "quarter", 5: "eighth"}},
}
BESIDE_BARS = {"Black Dog": [5], "Hey Joe": [2, 6], EXACT: [91]}


def _convert(source, tmp_path):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_REFUSE_08_SOURCE_MISSING"
    build = tmp_path / "build"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                                      "--out", str(tmp_path / "output.gp"), "--work-dir", str(build)])
    assert result.exit_code == 0, f"REFUSE_08_CLI_EXIT_{result.exit_code}"
    route = json.loads((build / "note-type-route.json").read_bytes())
    durations = json.loads((build / "note-durations.json").read_bytes())
    return route, durations


def _check(source, tmp_path):
    route, durations = _convert(source, tmp_path)
    by_source = {b["source_bar_index"]: b for b in route["bars"]}
    for bar, rests in EXPECTED[source].items():
        assert by_source[bar]["status"] == "written", f"BAR_REFUSED_{bar}:{by_source[bar]['reason']}"
        events = {e["event_index"]: e for e in durations["events"] if e["bar_index"] == bar}
        for index, value in rests.items():
            assert events[index]["kind"] == "rest" and events[index]["written"] == value, f"REST_{bar}_{index}"
        assert {i for i, e in events.items() if e["kind"] == "rest"} == set(rests), f"EXTRA_RESTS_{bar}"


@pytest.mark.parametrize("source", sorted(EXPECTED))
def test_rest_bars_are_read_and_match_the_printed_page(source, tmp_path):
    """Rejects a refused rest bar or a rest value that disagrees with the printed glyph."""
    _check(source, tmp_path)


@pytest.mark.parametrize("source", sorted(BESIDE_BARS))
def test_mutant_drop_rest_beside_rule_fails(source, tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_rest_form_outranks_accidental_position", lambda beside, kind: False)
    with pytest.raises(AssertionError):
        _check(source, tmp_path)


@pytest.mark.parametrize("source", ["Black Dog", "Hey Joe", "Brown Sugar"])
def test_mutant_drop_sliver_rule_fails(source, tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "REST_HOOK_MIN_WIDTH_SPACES", 1e-9)
    with pytest.raises(AssertionError):
        _check(source, tmp_path)
