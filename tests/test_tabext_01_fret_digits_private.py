"""Real-source fret digits that TAB extraction excluded before the route (TABEXT-01).

Two causes, both on printed fret digits, are read now:

* A TAB system whose painted rows are cut by its own digits (a knocked-out gap behind every digit) was not detected,
  so every digit in it was excluded as a page or legend number. Bars now written: `12 Bar Blues Solo Guitar Jam.pdf`
  bars 20-23 and `E_Chord_Lick_Chord.pdf` bar 15 (a tied chord printed in brackets). Both have no reference `.gp`: they are
  labelled NOT independently verified against a file; each bar is checked against the printed page (beat and note
  counts read off the page). `The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord.pdf` bar 24 has the same cause but
  only two legacy rows intact: below the DUR-03 evidence bar, so it stays refused (reported unfinished).
* A "0" glyph beside another digit was merged into "0n" (`012` -> fret 12), losing the open string. `Ex 2 Hands Up.pdf`
  bar 5 is written now and is compared with its reference `.gp` (the reference bar is found by content).

Synthetic tests carry no acceptance weight: none are used. Page numbers and legends must stay excluded: the pass
only ever adds a system, keeps every base system object exactly (so a source that converted keeps its bytes), and
`Lesson-5.pdf` (digits outside every system on each page) gains nothing.
Mutants (each fails a test below):
  DROP_SYSTEM_RECOVERY  the digit-interrupted system pass never adds a system: the four sources' bars stay refused.
  DROP_ROW_EVIDENCE     the DUR-03 legacy-row evidence is not required: `Melodic_Expressions.pdf` pages 9/12 gain a system.
  REPLACE_BASE_SYSTEMS  the recovery pass result replaces the base systems: their extent/barlines change.
  MERGE_LEADING_ZERO    "0" merges with the next digit again: Ex 2 Hands Up bar 5 stays refused.
"""
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pymupdf
import pytest
from typer.testing import CliRunner

from score2gp import pdf
from score2gp.cli import app

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"

# source -> {source bar index: (beats, notes)} read off the printed page (counts only).
PRINTED = {
    "12 Bar Blues Solo Guitar Jam": {20: (4, 12), 21: (8, 16), 22: (8, 16), 23: (8, 16)},
    "E_Chord_Lick_Chord": {15: (1, 3)},
}


def _convert(source, tmp_path):
    pdf_path = PRIVATE / f"{source}.pdf"
    assert pdf_path.is_file(), "REQUIRED_TABEXT_01_SOURCE_MISSING"
    build = tmp_path / "build"
    out = tmp_path / "output.gp"
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf_path), "--pdf-only-tab", "--out", str(out),
                             "--work-dir", str(build)])
    route = json.loads((build / "note-type-route.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, out


def _gpif_bars(path):
    """Per bar (voice 1): [(note value, sorted (string, fret) notes)]."""
    root = ET.fromstring(zipfile.ZipFile(path).read("Content/score.gpif"))
    notes = {n.get("id"): n for n in root.find("Notes")}
    beats = {b.get("id"): b for b in root.find("Beats")}
    rhythms = {r.get("id"): r for r in root.find("Rhythms")}
    voices = {v.get("id"): v for v in root.find("Voices")}
    bars = {b.get("id"): b for b in root.find("Bars")}
    out = []
    for master in root.find("MasterBars"):
        voice_id = bars[master.find("Bars").text.split()[0]].find("Voices").text.split()[0]
        sequence = []
        if voice_id != "-1":
            for beat_id in voices[voice_id].find("Beats").text.split():
                beat = beats[beat_id]
                found = []
                if beat.find("Notes") is not None:
                    for note_id in beat.find("Notes").text.split():
                        props = {p.get("name"): p for p in notes[note_id].find("Properties")}
                        found.append((int(props["String"][0].text), int(props["Fret"][0].text)))
                sequence.append((rhythms[beat.find("Rhythm").get("ref")].find("NoteValue").text, tuple(sorted(found))))
        out.append(sequence)
    return out


def _check_system_bars(tmp_path):
    for source, bars_expected in PRINTED.items():
        sub = tmp_path / source[:12].replace(" ", "_")
        sub.mkdir()
        bars, out = _convert(source, sub)
        ours = _gpif_bars(out)
        for bar, (beats, notes) in bars_expected.items():
            assert bars[bar]["status"] == "written", f"{source[:12]}_BAR_{bar}_REFUSED"
            written = ours[bars[bar]["output_bar_index"] - 1]
            assert len(written) == beats, f"{source[:12]}_BAR_{bar}_BEAT_COUNT"
            assert sum(len(found) for _value, found in written) == notes, f"{source[:12]}_BAR_{bar}_NOTE_COUNT"


def _check_leading_zero_bar(tmp_path):
    bars, out = _convert("Ex 2 Hands Up", tmp_path)
    # REFUSE-17: the clef/start-repeat stub is no bar, so this bar (source 5 before) is source bar 4.
    assert bars[4]["status"] == "written", "EX2_BAR_4_REFUSED"
    written = _gpif_bars(out)[bars[4]["output_bar_index"] - 1]
    assert written in _gpif_bars(PRIVATE / "Ex 2 Hands Up.gp"), "EX2_BAR_4_DIFFERS_FROM_REFERENCE"


def _systems(source, page_number):
    return pdf._detect_tab_systems(pymupdf.open(PRIVATE / f"{source}.pdf")[page_number - 1], page_number)


def _check_base_systems_kept():
    for source in ("12 Bar Blues Solo Guitar Jam", "E_Chord_Lick_Chord"):
        page = pymupdf.open(PRIVATE / f"{source}.pdf")[0]
        original = pdf._digit_interrupted_systems_added
        pdf._digit_interrupted_systems_added = lambda *a, **k: None
        try:
            base = pdf._detect_tab_systems(page, 1)
        finally:
            pdf._digit_interrupted_systems_added = original
        new = pdf._detect_tab_systems(page, 1)
        assert len(new) == len(base) + 1, f"{source[:12]}_SYSTEM_NOT_ADDED"
        for system in base:
            kept = next(s for s in new if s.line_ys == system.line_ys)
            assert (kept.x0, kept.x1, kept.barlines) == (system.x0, system.x1, system.barlines),                 f"{source[:12]}_BASE_SYSTEM_CHANGED"


def _check_page_numbers_gain_no_system():
    page_count = len(pymupdf.open(PRIVATE / "Lesson-5.pdf"))
    for number in range(1, page_count + 1):
        with_pass = _systems("Lesson-5", number)
        original = pdf._digit_interrupted_systems_added
        pdf._digit_interrupted_systems_added = lambda *a, **k: None
        try:
            without_pass = _systems("Lesson-5", number)
        finally:
            pdf._digit_interrupted_systems_added = original
        assert [s.line_ys for s in with_pass] == [s.line_ys for s in without_pass], f"LESSON5_PAGE_{number}_GAINED"


def test_digit_interrupted_systems_are_read_into_written_bars(tmp_path):
    """Rejects a system cut by its own digits staying undetected, so its digits are dropped and its bars refused."""
    _check_system_bars(tmp_path)


def test_leading_zero_digit_is_its_own_fret_and_matches_reference(tmp_path):
    """Rejects "0 12" merged into one fret 12 (the open string lost), checked against the reference .gp."""
    _check_leading_zero_bar(tmp_path)


def test_base_systems_are_kept_exactly_and_one_system_is_added():
    """Rejects a recovery that rewrites systems already detected (a converted source would change bytes)."""
    _check_base_systems_kept()


def test_page_numbers_and_legends_never_become_a_system():
    """Rejects the recovery adding a system on a page whose outside digits are only page numbers/legends."""
    _check_page_numbers_gain_no_system()


def test_mutant_drop_system_recovery_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf, "_digit_interrupted_systems_added", lambda *a, **k: None)
    with pytest.raises(AssertionError):
        _check_system_bars(tmp_path)


def _check_weak_row_evidence_pages_unchanged():
    for page_number, count in ((9, 4), (12, 4)):
        assert len(_systems("Melodic_Expressions", page_number)) == count, f"MELODIC_P{page_number}_GAINED_SYSTEM"


def test_system_without_legacy_row_evidence_is_not_added():
    """Rejects admitting a recovered system with fewer legacy rows than DUR-03 requires (negative real-source pages)."""
    _check_weak_row_evidence_pages_unchanged()


def test_mutant_drop_row_evidence_fails(monkeypatch):
    monkeypatch.setattr(pdf, "_added_system_has_row_evidence", lambda system, drawn: True)
    with pytest.raises(AssertionError):
        _check_weak_row_evidence_pages_unchanged()


def test_mutant_replace_base_systems_fails(monkeypatch):
    def replace_base(page, page_index, first_bar_index, cumulative_y_offset, base_systems):
        return pdf._detect_tab_systems(page, page_index, first_bar_index, cumulative_y_offset, _recover_paint=True)

    monkeypatch.setattr(pdf, "_digit_interrupted_systems_added", replace_base)
    with pytest.raises(AssertionError):
        _check_base_systems_kept()


def test_mutant_merge_leading_zero_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf, "_glyphs_form_one_fret", lambda left, right: True)
    with pytest.raises(AssertionError):
        _check_leading_zero_bar(tmp_path)
