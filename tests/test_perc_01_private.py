"""Printed bar/strike census; counts only, no reference score or musical data.

This is recognition evidence, not an event-fidelity oracle. A written bar still
requires a separate independently transcribed ledger and native GPIF comparison.
"""
from pathlib import Path
import copy
import json

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.notation_omr import font_glyphs, note_duration


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "Castles Made of Sand": ([2, 2, 1, 2, 2, 3], {1: 2, 3: 3, 8: 3}),
    "Crossroads": ([4, 4, 3, 3, 3, 2, 2, 2, 3, 4, 2, 2, 2, 2],
                   {1: 3, 3: 3, 8: 2, 14: 2, 15: 2, 16: 2, 19: 6, 25: 8, 26: 3, 33: 2}),
}


def assert_census(reading, name):
    counts, strikes = SOURCES[name]
    assert [s["bar_count"] for s in reading["systems"]] == counts, "printed_bar_census"
    for bar in range(sum(counts)):
        actual = sum(h["kind"] == "cross" for r in reading["events"]
                     if r["bar_index"] == bar
                     for h in (r.get("notehead") or {}).get("heads", []))
        assert actual == strikes.get(bar + 1, 0), (bar + 1, "printed_strike_census")


@pytest.fixture(scope="module", params=SOURCES)
def census(request):
    name = request.param
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved PERC-01 source missing"
    return name, source, note_duration.read_note_durations(source)


def test_printed_bar_boundaries_and_all_cross_heads(census):
    """Reject lost legacy font outlines and straight-cross/stem ownership.

    The five source pages were inspected independently. Bar counts are per
    system in page order; omitted strike-count entries mean zero printed Xs.
    """
    name, _, reading = census
    assert_census(reading, name)


@pytest.mark.parametrize("mutant", ["drop_legacy_outlines", "drop_straight_crosses", "cross_stems_as_barlines"])
def test_real_source_census_rejects_recognition_mutants(census, monkeypatch, mutant):
    """Run the reader with each lost-evidence mutant on both approved PDFs."""
    name, source, reading = census
    assert_census(reading, name)
    if mutant == "drop_legacy_outlines":
        monkeypatch.setattr(font_glyphs, "LEGACY_MUSIC_FONT_FAMILIES", frozenset())
    elif mutant == "drop_straight_crosses":
        original = note_duration._is_dead_note_x_head
        monkeypatch.setattr(note_duration, "_is_dead_note_x_head",
                            lambda g, s: g.curved and original(g, s))
    else:
        original = note_duration.extract_page_symbols

        def without_straight_head_contact(*args, **kwargs):
            result = original(*args, **kwargs)
            result.head_shapes = [g.shape for g in result.glyphs if g.curved]
            return result

        monkeypatch.setattr(note_duration, "extract_page_symbols", without_straight_head_contact)
    with pytest.raises(AssertionError, match="printed_(bar|strike)_census"):
        assert_census(note_duration.read_note_durations(source), name)


def assert_located_refusals(located, name):
    counts, strikes = SOURCES[name]
    assert len(located) == sum(counts), "located_bar_count"
    assert [r["location"]["bar_index"] for r in located] == list(range(sum(counts)))
    for index, refusal in enumerate(located):
        assert refusal["reason"] == "unsafe_tab_layout_not_independently_partitionable"
        assert len(refusal["location"]["bbox"]) == 4
        assert refusal["blocking_layout_warnings"]
        assert refusal["notation_strike_count"] == strikes.get(index + 1, 0), "refused_strike_census"
        assert sum(s["head_count"] for s in refusal["notation_strikes"]) == strikes.get(index + 1, 0)
        assert all(s["location"]["bar_index"] == index and len(s["head_sources"]) == s["head_count"]
                   for s in refusal["notation_strikes"])


def assert_local_observations(located, reading):
    """Diagnostic completeness only; not an independent musical-value oracle."""
    for refusal in located:
        bar = refusal["location"]["bar_index"]
        expected = [{"code": event["reason"], "location": event["location"]}
                    for event in reading["events"]
                    if event["bar_index"] == bar and event["status"] != "read"]
        assert refusal.get("unread_notation_events") == expected, "unread_bar_evidence"
        assert refusal.get("refusal_scope") == "source_layout", "inherited_refusal_scope"
        assert refusal.get("strike_candidate_count_matches") == (
            refusal["notation_strike_count"] == refusal["tab_strike_candidate_count"]
        ), "strike_candidate_disagreement"


def test_normal_cli_refuses_all_printed_bars_with_strike_locations(census, tmp_path):
    """Reject the old whole-file-only refusal and silently omitted X heads.

    This asserts continued refusal, not correct written musical events. No GP
    may be emitted while the layout is unsafe.
    """
    name, source, reading = census
    output = tmp_path / "out.gp"
    folder = tmp_path / "build"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(source), "--pdf-only-tab",
                                   "--out", str(output), "--work-dir", str(folder)])
    assert result.exit_code == 4
    assert not output.exists()
    diagnostic = json.loads((folder / "diagnostics.json").read_text())
    assert diagnostic["category"] == "pdf_only_tab_grouping_unsafe"
    located = diagnostic["details"]["located_bar_refusals"]
    assert_located_refusals(located, name)
    assert_local_observations(located, reading)
    # Named diagnostic mutants: restore the old record (drop this change),
    # attribute a source refusal to the local bar, and hide a strike mismatch.
    for field, value, message in [
        ("unread_notation_events", None, "unread_bar_evidence"),
        ("refusal_scope", "local_bar", "inherited_refusal_scope"),
        ("strike_candidate_count_matches", True, "strike_candidate_disagreement"),
    ]:
        mutant = copy.deepcopy(located)
        first = next(r for r in mutant if r["notation_strike_count"])
        first[field] = value
        with pytest.raises(AssertionError, match=message):
            assert_local_observations(mutant, reading)
    # Named output mutants: erase the old missing ledger, or drop one strike.
    with pytest.raises(AssertionError, match="located_bar_count"):
        assert_located_refusals([], name)
    mutant = copy.deepcopy(located)
    first = next(r for r in mutant if r["notation_strike_count"])
    first["notation_strike_count"] -= 1
    with pytest.raises(AssertionError, match="refused_strike_census"):
        assert_located_refusals(mutant, name)
