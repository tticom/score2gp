"""Mutants reach approved source contours and the production event reader."""
from pathlib import Path
import inspect
import json
import tempfile

import pymupdf
import pytest
from typer.testing import CliRunner

from score2gp.notation_omr import note_duration as nd
from score2gp.cli import app

ROOT = Path(__file__).resolve().parents[1]


def _scaled_source(name, scale, directory):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    target = Path(directory) / "scaled.pdf"
    with pymupdf.open(source) as original, pymupdf.open() as derived:
        for index, page in enumerate(original):
            output = derived.new_page(width=page.rect.width * scale,
                                      height=page.rect.height * scale)
            output.show_pdf_page(output.rect, original, index)
        derived.save(target)
    return target


def _assert_beams(source, expected):
    result = nd.read_note_durations(source)
    assert sum(e["status"] == "read" and e["beams"]["count"] > 0
               for e in result["events"] if (e.get("notehead") or {}).get("kind") != "cross") == expected
    assert sum(e["status"] == "read" and e["beams"]["count"] > 0
               for e in result["events"] if (e.get("notehead") or {}).get("kind") == "cross") == (16 if expected == 62 else 0)


@pytest.mark.parametrize("name,expected", [
    ("G-Am-C-Lick", 62), ("Lesson-3", 448), ("Derek Trucks BB King", 120),
])
def test_fixed_point_beam_size_mutant_fails_on_scaled_approved_sources(monkeypatch, name, expected):
    # A point-sized substitute for measured staff space must not read the
    # same class on a transformed copy of genuine notation.
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unread01-mutant-", dir=work) as directory:
        source = _scaled_source(name, 0.5, directory)
        _assert_beams(source, expected)
        original = nd._is_beam
        monkeypatch.setattr(nd, "_is_beam", lambda glyph, space: original(glyph, 6.0))
        with pytest.raises(AssertionError):
            _assert_beams(source, expected)


def _assert_located_symbols(source, dead_heads, overlaps):
    result = nd.read_note_durations(source)
    dead = [e for e in result["events"]
            if any(h["kind"] == "cross" for h in (e.get("notehead") or {}).get("heads", []))]
    assert sum(e["notehead"]["count"] for e in dead) == dead_heads
    assert all(e["status"] == "read" and e["duration_quarters"] and e["stem"] for e in dead)
    assert all(e["location"][key] is not None for e in dead
               for key in ("page_index", "system_index", "bar_index", "event_index"))
    unsupported = [e for e in result["diagnostics"].get("unread_symbols", [])
                   if e["class"] == "unsupported_overlapping_form"]
    assert len(unsupported) == overlaps
    assert all(e["status"] == "unread" and e["shape_class"] for e in unsupported)
    assert all(e["location"][key] is not None for e in unsupported
               for key in ("page_index", "system_index", "bar_index", "event_index"))
    dead_bars = {e["bar_index"] for e in dead}
    assert all(bar["status"] == "match" or bar["unread_events"]
               for bar in result["bar_checks"] if bar["bar_index"] in dead_bars)
    # Exercise the ordinary conversion route too: recognition diagnostics alone
    # do not prove that a newly writable overlap bar is actually refused.
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unread01-route-mutant-", dir=work) as directory:
        folder = Path(directory)
        run = CliRunner().invoke(app, [
            "convert", "--pdf", source.as_posix(), "--pdf-only-tab",
            "--out", (folder / "output.gp").as_posix(), "--work-dir", folder.as_posix(),
        ])
        assert run.exit_code == 0, run.output
        route = json.loads((folder / "note-type-route.json").read_text())
        overlap_bars = {s["location"]["bar_index"] for s in unsupported}
        for bar in route["bars"]:
            if bar["source_bar_index"] not in overlap_bars:
                continue
            assert bar["unread_symbols"]
            if bar["overlap_preservation_basis"] == "base_equivalent_refused":
                assert bar["status"] == "refused"
                # Existing refusals retain their matched-event diagnostics.
                # Newly refused overlaps have no emitted route events.
                if bar["detail"] == "unsupported_overlapping_form":
                    assert not bar["events"]


@pytest.mark.parametrize("name,dead_heads,overlaps", [
    ("G-Am-C-Lick", 20, 8), ("Lesson-3", 0, 12), ("Derek Trucks BB King", 0, 11),
])
def test_silent_unclassified_drop_mutant_fails_on_the_real_source(
        monkeypatch, name, dead_heads, overlaps):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    # Counts come from the source-contour census. Base-written overlaps remain
    # located diagnostics; newly writable overlap and dead-head bars refuse.
    _assert_located_symbols(source, dead_heads, overlaps)
    original = nd._read_staff
    code = inspect.getsource(original)
    needle = "    # Assign events to bars."
    assert code.count(needle) == 1
    code = code.replace(needle,
        '    events = [e for e in events if e.get("_kind") != "unclassified"]\n'
        '    located_events = [e for e in located_events if e.get("_kind") != "unclassified"]\n'
        '    overlaps = []\n'
        + needle)
    namespace = dict(nd.__dict__)
    exec(compile(code, "<silent-symbol-drop-mutant>", "exec"), namespace)
    monkeypatch.setattr(nd, "_read_staff", namespace["_read_staff"])
    with pytest.raises(AssertionError):
        _assert_located_symbols(source, dead_heads, overlaps)
