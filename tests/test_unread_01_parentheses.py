"""Unsupported paired contours stay with their real owning note events."""
from pathlib import Path
import pytest
from score2gp.notation_omr.note_duration import read_note_durations

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name,events,strokes", [
    ("Derek Trucks BB King", 4, 8), ("Am-blues-lick", 2, 4),
])
def test_real_parentheses_are_located_refusals_on_their_owning_heads(name, events, strokes):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    result = read_note_durations(source)
    located = [e for e in result["events"] if e.get("unread_symbols")]
    assert len(located) == events
    assert sum(len(e["unread_symbols"]) for e in located) == strokes
    checks = {bar["bar_index"]: bar for bar in result["bar_checks"]}
    for event in located:
        assert event["status"] == "unread" and event["written"] is None
        assert event["shape_class"] == "notehead_parenthesis"
        assert event["notehead"]["count"] >= 1
        assert checks[event["bar_index"]]["status"] == "incomplete"
        for symbol in event["unread_symbols"]:
            assert symbol["class"] == "notehead_parenthesis"
            assert symbol["width_spaces"] == pytest.approx(0.8, abs=0.005)
            assert symbol["height_spaces"] == pytest.approx(1.0, abs=0.005)
            assert all(symbol["location"][key] == event[key] for key in
                       ("page_index", "system_index", "bar_index", "event_index"))
            assert len(symbol["location"]["bbox"]) == 4
