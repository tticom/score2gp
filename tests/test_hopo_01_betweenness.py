"""HOPO-01: a hammer-on/pull-off marker pairs only the two digits it lies between.

Real-source part: the approved sources with a reference .gp. Measured at base and head, no written HOPO
there has a marker outside its two digits, so those tests guard the bars already right (their pairing,
and the located refusals of the ambiguous ones); no approved source holds a marker keyed to a
destination bar, so they cannot reject the betweenness or backward-pairing mutants.

Synthetic part: zero acceptance weight. The generated DUR-02 page supplies the digit geometry only so the
pairing paths no approved source reaches (backward across a barline; marker outside the two notes) can
fail under the mutants named on each test.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

import pytest

from test_dur_02_note_type_route import _attachment_probe
from test_dur_02_oracle import read_gp_bars

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"

# (stem, reference origins also written, reference origins refused with an ambiguity warning)
REAL = {
    "Lesson-5": (8, 0),
    "Lesson-4": (8, 0),
    "Melodic Soloing Masterclass": (12, 0),
    "Can't Find My Way Home (open chord shenanigans)": (14, 0),
    "Bebop Licks in Am": (24, 5),
}


@lru_cache(maxsize=None)
def _convert(stem):
    assert (PRIVATE / f"{stem}.pdf").is_file(), "required approved PDF absent"
    (ROOT / "work").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
        scratch = Path(directory)
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(PRIVATE / f"{stem}.pdf"),
             "--pdf-only-tab", "--out", str(scratch / "out.gp"), "--work-dir", str(scratch / "wd")],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stderr[-1000:]
        warnings = json.loads((scratch / "wd/warnings.json").read_text())
        return (scratch / "out.gp").read_bytes(), warnings


def _origins(bars):
    return {(i + 1, j + 1) for i, b in enumerate(bars) for j, e in enumerate(b["events"] or [])
            if e.get("hopo_origin")}


@pytest.mark.parametrize("stem", sorted(REAL))
def test_written_hopo_origins_are_all_in_the_reference_and_the_rest_are_refused(stem):
    """Rejects a pairing that writes a technique the reference lacks (a guessed side or pair) and one
    that silently drops the ambiguous ones instead of locating a refusal."""
    reference = PRIVATE / f"{stem}.gp"
    assert reference.is_file(), "required approved reference absent"
    try:
        expected = _origins(read_gp_bars(reference))
    except Exception:  # multi-track reference: the first track, first staff
        expected = _origins(read_gp_bars(reference, track_id="0", staff_index=0))
    data, warnings = _convert(stem)
    produced = read_gp_bars(data)
    actual = _origins(produced)
    # A bar the product refused is written empty; only the written bars are judged here.
    expected = {(b, e) for b, e in expected if produced[b - 1]["events"] is not None}
    written, refused = REAL[stem]
    assert actual <= expected, "a written HOPO is not in the reference"
    assert len(actual) == written
    assert len(expected - actual) == refused
    ambiguous = [w for w in warnings if w["code"] == "ambiguous_technique_attachment"
                 and w["message"].startswith("Span technique")]
    assert len(ambiguous) >= refused
    assert all(w["provenance"] and w["provenance"][0]["bar_index"] for w in ambiguous)



@pytest.fixture
def probe_dir():
    # A neutral directory name: the generated page extracts differently under some pytest tmp_path names.
    (ROOT / "work").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "work") as directory:
        yield Path(directory)


def _marker(candidate_id, x0, x1, digit, bar_index):
    from score2gp.tabraw import make_tab_candidate
    return make_tab_candidate(
        candidate_id=candidate_id, raw_text="p", kind="technique-text", confidence=0.9,
        bbox_values=(x0, digit.y - 12, x1, digit.y - 4), page_index=digit.page_index,
        system_index=digit.system_index, staff_index=digit.staff_index, bar_index=bar_index)


def _attach(score, raw, placed, *markers):
    from score2gp.build_ir import _attach_symbols_and_techniques
    raw.candidates = list(markers)
    _attach_symbols_and_techniques(score, raw, placed_frets=placed)


def test_marker_keyed_to_the_destination_bar_pairs_backward_not_into_that_bars_own_pair(probe_dir):
    """Rejects: no backward pairing (nothing written) and nearest-pair-regardless-of-side (the
    destination bar's own pair takes the marker). Synthetic geometry, zero acceptance weight."""
    score, raw, placed = _attachment_probe(probe_dir)
    origin = score.bars[1].events[0].notes[0]
    destination = score.bars[2].events[0].notes[0]
    destination.string = origin.string          # a same-string pair across the barline
    last = max(placed[1], key=lambda c: c.x)
    first = min(placed[2], key=lambda c: c.x)
    # Just before the destination digit: nearer the midpoint of that bar's own first pair than of the
    # pair across the barline, yet between the two digits that the printed span joins.
    near = first.x - 4
    _attach(score, raw, placed, _marker("dest-keyed", near - 2, near + 2, last, first.bar_index))
    assert [(t.kind, t.target_event_id) for t in origin.techniques] == [("pull-off", score.bars[2].events[0].id)]
    assert not any(n.techniques for e in score.bars[2].events for n in e.notes)


def test_marker_outside_both_notes_of_a_two_note_bar_is_refused_not_guessed(probe_dir):
    """Rejects the old exact-two-notes fallback that attached whatever the marker's side. Synthetic."""
    score, raw, placed = _attachment_probe(probe_dir)
    bar = score.bars[0]
    bar.events = bar.events[:2]
    digits = sorted(placed[0], key=lambda c: c.x)[:2]
    for event, digit in zip(bar.events, digits):
        for note in event.notes:
            note.string = digits[0].string
    left = digits[0].x - 12
    _attach(score, raw, placed, _marker("outside", left - 2, left + 2, digits[0], digits[0].bar_index))
    assert not any(n.techniques for e in bar.events for n in e.notes)
    [warning] = [w for w in score.warnings if w.code == "ambiguous_technique_attachment"]
    assert "outside the two notes" in warning.message and "bar 1" in warning.message
