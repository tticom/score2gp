"""DUR-01-FU1: unclassified forms on a head or stem are located by class on approved real sources."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

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


@pytest.mark.parametrize("name,bars,status", [
    ("Derek Trucks BB King", (5, 6, 15), "refused"),
    ("Lesson-3", (24, 65), "written"),
])
def test_overlap_refuses_new_bars_and_preserves_base_written_bars(name, bars, status):
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unread01-overlap-", dir=work) as directory:
        folder = Path(directory)
        run = subprocess.run([
            sys.executable, "-m", "score2gp.cli", "convert", "--pdf",
            (ROOT / "fixtures/private" / (name + ".pdf")).as_posix(),
            "--pdf-only-tab", "--out", (folder / "output.gp").as_posix(),
            "--work-dir", folder.as_posix(),
        ], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        route = json.loads((folder / "note-type-route.json").read_text())
        located = json.loads((folder / "note-durations.json").read_text())["diagnostics"]["unread_symbols"]
        for bar in bars:
            entry = next(b for b in route["bars"] if b["source_bar_index"] == bar)
            assert entry["status"] == status
            symbols = [s for s in located if s["class"] == "unsupported_overlapping_form"
                       and s["location"]["bar_index"] == bar]
            assert symbols and all(all(s["location"][key] is not None for key in
                ("page_index", "system_index", "bar_index", "event_index")) for s in symbols)
            if status == "refused":
                assert entry["detail"] == "unsupported_overlapping_form"
                assert entry["location"]["event_index"] is not None
                assert not entry["events"]
