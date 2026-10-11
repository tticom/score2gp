"""Unsupported paired contours stay with their real owning note events."""
from pathlib import Path
import pytest
from score2gp.notation_omr.note_duration import read_note_durations

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name,events,strokes", [
    ("Derek Trucks BB King", 4, 8), ("Am-blues-lick", 2, 4),
])
def test_real_parentheses_are_located_without_erasing_the_owning_duration(name, events, strokes):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    result = read_note_durations(source)
    located = [e for e in result["events"] if e.get("unread_symbols")]
    assert len(located) == events
    assert sum(len(e["unread_symbols"]) for e in located) == strokes
    for event in located:
        assert event["status"] == "read" and event["written"] is not None
        assert event["notehead"]["count"] >= 1
        for symbol in event["unread_symbols"]:
            assert symbol["status"] == "unread"
            assert symbol["class"] == "parenthesized_head_unrepresented"
            assert symbol in result["diagnostics"]["unread_symbols"]
            assert symbol["width_spaces"] == pytest.approx(0.8, abs=0.005)
            assert symbol["height_spaces"] == pytest.approx(1.0, abs=0.005)
            assert all(symbol["location"][key] == event[key] for key in
                       ("page_index", "system_index", "bar_index", "event_index"))
            assert len(symbol["location"]["bbox"]) == 4


@pytest.mark.parametrize("name,bars", [
    ("Melodic Soloing Masterclass", [7]),
    ("Melodic_Expressions_Chap_19_", [21, 23]),
])
def test_previously_written_parenthesized_bars_keep_their_duration(name, bars):
    result = read_note_durations(ROOT / "fixtures/private" / (name + ".pdf"))
    for bar in bars:
        events = [e for e in result["events"] if e["bar_index"] == bar]
        assert events and all(e["status"] == "read" for e in events)
        symbols = [s for e in events for s in e.get("unread_symbols", [])]
        assert symbols
        assert all(s["class"] == "parenthesized_head_unrepresented" for s in symbols)
