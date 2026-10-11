"""DUR-01-FU1: unclassified forms on a head or stem are located by class on approved real sources."""
from pathlib import Path

import pytest

from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
OVERLAP_REASONS = ("accidental_beside_notehead", "over_or_under_notehead")


def _overlaps(name):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    result = nd.read_note_durations(source)
    located = [u for u in result["diagnostics"].get("unread_symbols", [])
               if u["class"] == "unsupported_overlapping_form"]
    return result, located


@pytest.mark.parametrize("name,expected", [("G-Am-C-Lick", 11), ("Lesson-3", 12), ("Derek Trucks BB King", 12)])
def test_every_counted_overlap_is_a_located_unread_symbol(name, expected):
    result, located = _overlaps(name)
    counted = result["diagnostics"]["ignored_symbols_by_reason"]
    # Located forms are the counted ones that no accidental reading claimed.
    assert len(located) == expected
    for reason in OVERLAP_REASONS:
        assert sum(u["reason"] == reason for u in located) <= counted.get(reason, 0)
    for symbol in located:
        assert symbol["status"] == "unread" and symbol["shape_class"]
        assert all(symbol["location"][key] is not None
                   for key in ("page_index", "system_index", "bar_index", "event_index"))
        assert symbol["width_spaces"] > 0 and symbol["height_spaces"] > 0


def test_dropping_the_overlap_location_mutant_fails_on_real_sources(monkeypatch):
    _overlaps("G-Am-C-Lick")  # passes unmutated
    monkeypatch.setattr(nd, "_unread_shape_class", lambda glyph, space: "")
    result, located = _overlaps("G-Am-C-Lick")
    with pytest.raises(AssertionError):
        assert all(symbol["shape_class"] for symbol in located)
