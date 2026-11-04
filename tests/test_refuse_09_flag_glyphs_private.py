"""Real-source stem flags (REFUSE-09).

Two reader gaps left real flags unread:
- a single stem-up flag curls back under its own blade from ~0.55 of its reach, so the notation reader's
  third scan (at 0.6) crossed it twice and the glyph was called unidentified (`flag_glyph_unidentified`);
- the staffless-TAB rhythm reader saw a flag under the strings and always refused the bar
  (`flag_glyph_unread`) although the glyph's hooks fix the value.
A grace's flag count also fixes no duration (a grace has none), so a two-blade grace is no longer refused
for its count (`grace_note_unsupported_flag_count`).

Sources: `Castles Made of Sand.pdf` bar 0 (stem-up eighth flag; reference-less, checked against the PRINTED
PAGE by the author), `PARANOID - BLACK SABBATH.pdf` bars 5, 17, 25, 29, 37 (run with a declared 4/4; also
read against the printed page; NOT independently verified against a reference file), and `Pride and Joy.pdf`
bar 4 (two graces). Bar 23 of PARANOID is a correct refusal and must stay refused: its read totals 9/2 of 4.
Synthetic tests carry no acceptance weight; none are used. Mutants:
  OLD_FLAG_SCANS         FLAG_SCAN_FRACTIONS back to (0.4, 0.5, 0.6): the Castles bar stays refused.
  DROP_TAB_FLAG_READ     `_Reader._flag_hooks_of` returns None: the five PARANOID bars stay refused.
  FLAG_READ_AS_SIXTEENTH `_flag_hooks_of` adds one hook: values differ from the page and totals break.
  GRACE_ONE_HOOK_ONLY    GRACE_READABLE_FLAG_HOOKS back to (1,): Pride and Joy bar 4 graces stay refused for count.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp import pdf_tab_rhythm as rhythm
from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"

PARANOID_EXPECTED = {
    5: [("eighth", 0), ("quarter", 1), ("quarter", 0), ("quarter", 0)],
    17: [("eighth", 0), ("quarter", 0), ("eighth", 0), ("quarter", 0), ("quarter", 0)],
    25: [("eighth", 0), ("eighth", 0), ("eighth", 0), ("quarter", 0), ("quarter", 1)],
    29: [("eighth", 0), ("quarter", 1), ("quarter", 0), ("quarter", 0)],
    37: [("eighth", 0), ("quarter", 1), ("quarter", 0), ("quarter", 0)],
}


def _convert(source, tmp_path, extra=()):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_REFUSE_09_SOURCE_MISSING"
    build = tmp_path / "build"
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", *extra,
                             "--out", str(tmp_path / "output.gp"), "--work-dir", str(build)])
    route = json.loads((build / "note-type-route.json").read_bytes())
    durations = json.loads((build / "note-durations.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, durations


def _events(durations, bar):
    return sorted((e for e in durations["events"] if e["bar_index"] == bar), key=lambda e: e["event_index"])


def _check_castles(tmp_path):
    bars, durations = _convert("Castles Made of Sand", tmp_path)
    assert bars[0]["status"] == "written", "CASTLES_BAR_0_REFUSED"
    events = _events(durations, 0)
    last = events[-1]
    assert (last["written"], last["dots"]["count"], last["flags"]["count"]) == ("eighth", 0, 1), "FLAG_EVENT_VALUE"
    assert len(events) == 15


def _check_paranoid(tmp_path):
    bars, durations = _convert("PARANOID - BLACK SABBATH", tmp_path, ("--time-signature", "4/4"))
    for bar, expected in PARANOID_EXPECTED.items():
        assert bars[bar]["status"] == "written", f"BAR_REFUSED_{bar}"
        got = [(e["written"], e["dots"]["count"]) for e in _events(durations, bar)]
        assert got == expected, f"EVENTS_{bar}"
    assert bars[23]["status"] == "refused" and bars[23]["reason"] == "bar_total_mismatch", "BAR_23_MUST_STAY_REFUSED"


def _check_graces(tmp_path):
    _bars, durations = _convert("Pride and Joy", tmp_path)
    graces = [e for e in _events(durations, 4) if e.get("grace")]
    assert len(graces) == 2
    assert all(e["status"] == "read" and e["duration_quarters"] == "0" for e in graces), "GRACE_COUNT_REFUSED"


def test_stem_up_eighth_flag_bar_is_read_and_matches_the_printed_page(tmp_path):
    """Rejects a stem-up eighth flag called unidentified (bar refused) or a wrong value."""
    _check_castles(tmp_path)


def test_tab_rhythm_flags_are_read_and_match_the_printed_page(tmp_path):
    """Rejects a flagged TAB stem refused as unread, a wrong flag value, and a mismatching bar being written."""
    _check_paranoid(tmp_path)


def test_two_blade_graces_are_not_refused_for_their_flag_count(tmp_path):
    """Rejects a grace refused only because it carries two drawn blades."""
    _check_graces(tmp_path)


def test_mutant_old_flag_scans_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "FLAG_SCAN_FRACTIONS", (0.4, 0.5, 0.6))
    with pytest.raises(AssertionError):
        _check_castles(tmp_path)


def test_mutant_drop_tab_flag_read_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(rhythm._Reader, "_flag_hooks_of", staticmethod(lambda staff, stem: None))
    with pytest.raises(AssertionError):
        _check_paranoid(tmp_path)


def test_mutant_flag_read_as_sixteenth_fails(tmp_path, monkeypatch):
    real = rhythm._Reader._flag_hooks_of

    def one_more(staff, stem):
        n = real(staff, stem)
        return None if n is None else n + 1

    monkeypatch.setattr(rhythm._Reader, "_flag_hooks_of", staticmethod(one_more))
    with pytest.raises(AssertionError):
        _check_paranoid(tmp_path)


def test_mutant_grace_one_hook_only_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "GRACE_READABLE_FLAG_HOOKS", (1,))
    with pytest.raises(AssertionError):
        _check_graces(tmp_path)
