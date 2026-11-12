"""DUR-01-FU1: unclassified forms on a head or stem are located by class on approved real sources."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
from zipfile import ZipFile

import pytest

from score2gp.notation_omr import note_duration as nd
from refuse20_controls import disable_duration_roll_extension, legacy_duration_roll_cli
from test_dur_02_oracle import read_gp_arpeggios

ROOT = Path(__file__).resolve().parents[1]
OVERLAP_REASONS = ("accidental_beside_notehead", "over_or_under_notehead")


def _overlaps(name):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    result = nd.read_note_durations(source)
    located = [u for u in result["diagnostics"].get("unread_symbols", [])
               if u["class"] == "unsupported_overlapping_form"]
    return result, located


# FU5 recognises three printed slanted slurs in G-Am-C-Lick and one in Derek.
@pytest.mark.parametrize("name,expected", [("G-Am-C-Lick", 8), ("Lesson-3", 12), ("Derek Trucks BB King", 8)])
def test_every_counted_overlap_is_a_located_unread_symbol(name, expected, monkeypatch):
    if name == "Lesson-3":
        # Keep the original 12 genuinely unresolved contours under the named
        # DROP_DURATION_ROLL_EXTENSION control; the default is tested below.
        disable_duration_roll_extension(monkeypatch)
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
        command = legacy_duration_roll_cli() if name == "Lesson-3" else [sys.executable, "-m", "score2gp.cli"]
        run = subprocess.run([*command, "convert", "--pdf",
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


def test_read_rolls_own_the_twelve_former_overlaps_without_changing_music(monkeypatch):
    """Reject DROP_DURATION_ROLL_EXTENSION and silent deletion of those shapes.

    The two printed roll columns own these twelve contours. The named rule-drop
    control above keeps all original unknown-symbol assertions executable.
    """
    normal, unknown = _overlaps("Lesson-3")
    assert unknown == []
    waves = [n for n in normal["diagnostics"]["non_events"] if n["reason"] == "wave_column_stroke"]
    assert len(waves) == 12
    assert {n["bar_index"] for n in waves} == {24, 65}
    with monkeypatch.context() as legacy:
        disable_duration_roll_extension(legacy)
        _, unresolved = _overlaps("Lesson-3")
    assert len(unresolved) == 12
    old_locations = {(u["location"]["page_index"], u["location"]["system_index"],
                      u["location"]["bar_index"], tuple(u["location"]["bbox"])) for u in unresolved}
    new_locations = {(u["page_index"], u["system_index"], u["bar_index"], tuple(u["bbox"])) for u in waves}
    assert new_locations == old_locations
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    source = ROOT / "fixtures/private/Lesson-3.pdf"
    with tempfile.TemporaryDirectory(prefix="r20-roll-preservation-", dir=work) as directory:
        folder = Path(directory)
        outputs = []
        for label, command in [("normal", [sys.executable, "-m", "score2gp.cli"]),
                               ("legacy", legacy_duration_roll_cli())]:
            output = folder / (label + ".gp")
            run = subprocess.run([*command, "convert", "--pdf", str(source), "--pdf-only-tab",
                                  "--out", str(output), "--work-dir", str(folder / label)],
                                 capture_output=True, text=True)
            assert run.returncode == 0, run.stderr
            outputs.append(output)
        with ZipFile(outputs[0]) as normal_package, ZipFile(outputs[1]) as legacy_package:
            assert normal_package.read("Content/score.gpif") == legacy_package.read("Content/score.gpif")
        reference = ROOT / "fixtures/private/Lesson-3.gp"
        expected = read_gp_arpeggios(reference)
        assert len(expected) == 2
        assert read_gp_arpeggios(outputs[0]) == expected
