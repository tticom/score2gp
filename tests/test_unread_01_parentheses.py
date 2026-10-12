"""Unsupported paired contours stay with their real owning note events."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from zipfile import ZipFile

import pytest
from score2gp.notation_omr.note_duration import read_note_durations
from test_dur_02_oracle import read_gp_bars

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


def _convert(name, folder, runtime=ROOT):
    folder.mkdir()
    env = dict(os.environ, PYTHONPATH=(runtime / "src").as_posix())
    run = subprocess.run([
        sys.executable, "-m", "score2gp.cli", "convert", "--pdf",
        (ROOT / "fixtures/private" / (name + ".pdf")).as_posix(),
        "--pdf-only-tab", "--out", (folder / "output.gp").as_posix(),
        "--work-dir", folder.as_posix(),
    ], cwd=runtime, env=env, capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    route = json.loads((folder / "note-type-route.json").read_text())
    return route, folder / "output.gp"


@pytest.mark.parametrize("name,refused,written", [
    ("Derek Trucks BB King", (0, 14), (3, 11)),
    ("Ex 2 Hands Up", (10,), (1, 2, 3, 4)),
])
def test_new_parenthesized_bars_are_located_refusals_in_final_output(name, refused, written):
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unread01-parenthesis-", dir=work) as directory:
        route, gp = _convert(name, Path(directory) / "head")
        assert tuple(b["source_bar_index"] for b in route["bars"]
                     if b["status"] == "written") == written
        final_bars = read_gp_bars(gp)
        for index in refused:
            entry = next(b for b in route["bars"] if b["source_bar_index"] == index)
            assert entry["status"] == "refused"
            assert entry["detail"] == "parenthesized_head_unrepresented"
            assert entry["reason"] == "note_duration_event_unread"
            assert all(entry["location"][key] is not None for key in
                       ("page_index", "system_index", "bar_index", "event_index"))
            assert entry["unread_symbols"] and not entry["events"]
            assert final_bars[index]["events"] is None
        # Inspect the emitted package, not just the diagnostic route: every
        # unsupported parenthesis that lacks base preservation has no beats.
        for entry in route["bars"]:
            parentheses = [s for s in entry.get("unread_symbols", [])
                           if s["class"] == "parenthesized_head_unrepresented"]
            if parentheses and entry["overlap_preservation_basis"] == "base_equivalent_refused":
                assert final_bars[entry["source_bar_index"]]["events"] is None


@pytest.mark.parametrize("name,indices,base_gpif_sha256", [
    ("Melodic Soloing Masterclass", (7,),
     "617f1764bf748cfe044cc8d9277678ac736b3f78b23985df7ea069fb8b4f2f76"),
    ("Melodic_Expressions_Chap_19_", (21, 23),
     "4a8ce9039885fbccd9b336da391be831ed85a7e00d6f3ee5c08aedb29edf06c7"),
])
def test_base_written_parentheses_keep_byte_identical_gpif(name, indices, base_gpif_sha256):
    # Whole-GPIF byte digests from ordinary no-reference conversion at actual
    # base dfe05d05978d6625a0e3658fe54280aec3189f53; rechecked in the frozen
    # base/head corpus sweep. No private musical content is embedded here.
    # A digest keeps this regression executable in CI's shallow checkout.
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unread01-parenthesis-base-", dir=work) as directory:
        folder = Path(directory)
        head_route, head_gp = _convert(name, folder / "head")
        with ZipFile(head_gp) as after:
            assert hashlib.sha256(after.read("Content/score.gpif")).hexdigest() == base_gpif_sha256
        for index in indices:
            after = next(b for b in head_route["bars"] if b["source_bar_index"] == index)
            assert after["status"] == "written"
            assert after["overlap_preservation_basis"] == "base_equivalent_written"
            assert any(s["class"] == "parenthesized_head_unrepresented"
                       for s in after["unread_symbols"])
