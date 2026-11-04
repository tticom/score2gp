"""Real-source graces under a tuplet bracket (REFUSE-06).

The largest remaining reader-gap class of note_duration_event_unread was `grace_note_in_tuplet`
(Derek Trucks BB King): a small flagged grace standing inside a tuplet bracket's span. A grace has no
metrical duration, the tuplet scales none of it and the bar total never counts it, so refusing the whole
bar for it only lost correct bars. The reader now reads such a grace (it carries the printed bracket
ratio on its beat, as the page and the reference do). Every other grace rule is unchanged.

Oracle: the approved reference `Derek Trucks BB King.gp` (independent of the product), compared bar by
bar through the DUR-02 oracle reader. Reference-independent tests are labelled. Synthetic tests carry no
acceptance weight; none are used. Mutants:
  DROP_GRACE_UNDER_TUPLET_RULE   `_grace_under_tuplet_reason` returns "grace_note_in_tuplet" again: the
                                 four bars below stay refused.
  GRACE_LOSES_BRACKET_RATIO      graces drop the tuplet their beat sits in: the written grace beats then
                                 differ from the reference.
  GRACE_COUNTED_IN_TOTAL         the grace takes a metrical value: bars no longer total the meter.
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
SOURCE = "Derek Trucks BB King"
# Source bars newly written by REFUSE-06 (all four were refused with grace_note_in_tuplet).
NEWLY_WRITTEN = (1, 7, 8, 10)
# Source bars that stay refused for another, unchanged reason.
# (REFUSE-14 reads the ghost-note bars 0, 9 and 14, so they are no longer refused.)
STILL_REFUSED = {2: "rest_glyph_unidentified",
                 4: "unsupported_overlapping_form", 5: "unsupported_overlapping_form",
                 6: "unsupported_overlapping_form",
                 12: "grace_note_beat_too_far", 13: "unsupported_overlapping_form",
                 15: "unsupported_overlapping_form"}
# REFUSE-14: in source bar 9 the reference tags event 4 (an eighth) as a tie start although the next beat is a
# different pitch, which no printed tie can be; the page prints slide arcs there and no tie. Only that one
# `tie` field is exempt, and only where the written beat carries no tie; every other field must equal the reference.
REFERENCE_ONLY_TIE = (9, 4)
# One grace beat the reference tags with a 5:3 tuplet that no printed bracket covers: a zero-duration
# reference-side tag on a grace, not a duration. Every other beat must equal the reference.
UNBRACKETED_GRACE = (7, 0)
FIELDS = ("kind", "written", "dots", "tuplet", "tie", "positions", "grace")


def _convert(tmp_path):
    pdf, reference = PRIVATE / f"{SOURCE}.pdf", PRIVATE / f"{SOURCE}.gp"
    assert pdf.is_file() and reference.is_file(), "REQUIRED_REFUSE_06_SOURCE_MISSING"
    output, build = tmp_path / "output.gp", tmp_path / "build"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                                      "--out", str(output), "--work-dir", str(build)])
    assert result.exit_code == 0, f"REFUSE_06_CLI_EXIT_{result.exit_code}"
    route = json.loads((build / "note-type-route.json").read_bytes())
    return route, read_gp_bars(output, include_grace=True), read_gp_bars(reference, include_grace=True, track_id="0")


def _check(route, packaged, reference):
    by_source = {b["source_bar_index"]: b for b in route["bars"]}
    for bar in NEWLY_WRITTEN:
        assert by_source[bar]["status"] == "written", f"BAR_REFUSED_{bar}"
    for bar, reason in STILL_REFUSED.items():
        entry = by_source[bar]
        assert (entry["status"], entry["reason"]) == ("refused", "note_duration_event_unread"), f"BAR_{bar}"
        assert entry["detail"] == reason, f"REFUSAL_REASON_{bar}"
    for bar in (b["source_bar_index"] for b in route["bars"] if b["status"] == "written"):
        got = packaged[by_source[bar]["output_bar_index"] - 1]["events"]
        want = reference[bar]["events"]
        assert len(got) == len(want), f"EVENT_COUNT_{bar}"
        for index, (g, w) in enumerate(zip(got, want)):
            if (bar, index) == UNBRACKETED_GRACE:
                assert g["grace"] == w["grace"] and g["written"] == w["written"] and g["positions"] == w["positions"]
                continue
            fields = [f for f in FIELDS if not ((bar, index) == REFERENCE_ONLY_TIE and f == "tie")]
            if (bar, index) == REFERENCE_ONLY_TIE:
                assert g["tie"] == (False, False), f"BEAT_{bar}_{index}_TIE"
            assert [g[f] for f in fields] == [w[f] for f in fields], f"BEAT_{bar}_{index}"


def test_graces_under_a_tuplet_bracket_are_read_and_match_the_reference(tmp_path):
    """Rejects a refused grace bar, a wrong duration/tuplet/dot/string/fret, or a bar lost or changed."""
    _check(*_convert(tmp_path))


def test_mutant_drop_grace_under_tuplet_rule_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_grace_under_tuplet_reason", lambda record: "grace_note_in_tuplet")
    with pytest.raises(AssertionError):
        _check(*_convert(tmp_path))


def test_mutant_grace_loses_bracket_ratio_fails(tmp_path, monkeypatch):
    real = nd.read_note_durations

    def stripped(*args, **kwargs):
        result = real(*args, **kwargs)
        for event in result["events"]:
            if "grace" in event:
                event["tuplet"] = None
        return result

    monkeypatch.setattr(nd, "read_note_durations", stripped)
    with pytest.raises(AssertionError):
        _check(*_convert(tmp_path))


def test_mutant_grace_counted_in_total_fails(tmp_path, monkeypatch):
    real = nd.read_note_durations

    def counted(*args, **kwargs):
        result = real(*args, **kwargs)
        for event in result["events"]:
            if "grace" in event:
                event["duration_quarters"] = "1/2"
        return result

    monkeypatch.setattr(nd, "read_note_durations", counted)
    with pytest.raises(AssertionError):
        _check(*_convert(tmp_path))
