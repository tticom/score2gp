"""Mutants reach approved source contours and the production event reader."""
from pathlib import Path
import inspect
import tempfile

import pymupdf
import pytest

from score2gp.notation_omr import note_duration as nd

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
               for e in result["events"]) == expected


@pytest.mark.parametrize("name,expected", [("G-Am-C-Lick", 54), ("Lesson-3", 448)])
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


def _assert_dead_head_refusals(source):
    result = nd.read_note_durations(source)
    dead = [e for e in result["diagnostics"].get("located_unread_events", [])
            if e["reason"] == "dead_note_x_head"]
    assert len(dead) == 20
    assert all(e["status"] == "unread" and e["written"] is None for e in dead)
    assert all(e["location"][key] is not None for e in dead
               for key in ("page_index", "system_index", "bar_index", "event_index"))


def test_silent_unclassified_drop_mutant_fails_on_the_real_source(monkeypatch):
    source = ROOT / "fixtures/private/G-Am-C-Lick.pdf"
    assert source.is_file(), "required approved private source missing"
    _assert_dead_head_refusals(source)
    original = nd._read_staff
    code = inspect.getsource(original)
    needle = "    # Assign events to bars."
    assert code.count(needle) == 1
    code = code.replace(needle,
        '    events = [e for e in events if e.get("_kind") != "unclassified"]\n'
        '    located_events = [e for e in located_events if e.get("_kind") != "unclassified"]\n'
        + needle)
    namespace = dict(nd.__dict__)
    exec(compile(code, "<silent-symbol-drop-mutant>", "exec"), namespace)
    monkeypatch.setattr(nd, "_read_staff", namespace["_read_staff"])
    with pytest.raises(AssertionError):
        _assert_dead_head_refusals(source)
