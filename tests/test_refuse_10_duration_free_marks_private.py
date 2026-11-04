"""Real-source duration-free marks (REFUSE-10).

Three marks that carry no duration, pitch or string were refusing whole bars:
- a vibrato/trill line (a thin zigzag above the staff) drawn over noteheads was called an unsupported
  overlapping form, or an unclassified symbol, and refused the bar;
- a long tie or slur is a shallow crescent taller than the ordinary arc bound, so a tie to the next
  same-position note was refused (`unclassified_same_position_arc`) and a slur was an overlapping form;
- a framed section label printed below a staffless TAB system was a "mark below the strings".

Sources (all reference-less: no `.gp` exists for them, so every newly written bar was checked against the
PRINTED PAGE by the author and by the bar-total gate; they are NOT independently verified against a
reference file): `Brown Sugar.pdf` bars 2, 3, 8, 9; `Heartbreaker.pdf` bars 6, 7; `Castles Made of Sand.pdf`
bar 8; `Crossroads.pdf` bar 24; `Back In Black.pdf` bars 1, 3; `7_Grateful_Dead_Melodies.pdf` bars 8, 9, 45
(still refused, now for their true reason). `Derek Trucks BB King.pdf` carries parenthesised ghost-note and
accidental forms; those bars are correct refusals and must stay refused. Synthetic tests carry no
acceptance weight; none are used. Mutants (each fails a test below):
  DROP_WAVY_LINE        `_is_wavy_line_outside_staff` always False: the wave bars stay refused.
  DROP_CRESCENT_TIES    `_shallow_crescent_ties` returns nothing: the tall tie bars stay refused.
  CENTRE_ONLY_SLUR_REACH `_vertical_gap` back to head-centre distance: the Back In Black slur bar stays refused.
  DROP_BOXED_LABEL      `_is_boxed_text_label` always False: the framed label is a rhythm mark again.
  NO_HAMMER_ON_GUARD    `_carries_accidental` always False and `ARC_MAX_RISE_RATIO` huge: hammer-on/pull-off
                        arcs are read as ties (each guard alone is enough on this corpus, so both are removed).
  ANY_CURVE_IS_SLUR     `_slanted_slur_ids` returns every curved glyph: the ghost-note bars get written.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp import pdf_tab_rhythm as rhythm
from score2gp.cli import app
from score2gp.notation_omr import note_duration as nd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


def _convert(source, tmp_path):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_REFUSE_10_SOURCE_MISSING"
    build = tmp_path / "build"
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                             "--out", str(tmp_path / "output.gp"), "--work-dir", str(build)])
    route = json.loads((build / "note-type-route.json").read_bytes())
    durations = json.loads((build / "note-durations.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, durations


def _events(durations, bar):
    return sorted((e for e in durations["events"] if e["bar_index"] == bar), key=lambda e: e["event_index"])


def _shape(durations, bar):
    return [(e["written"], e["dots"]["count"], e["tie"]["start"], e["tie"]["stop"]) for e in _events(durations, bar)]


def _check_brown_sugar(tmp_path):
    bars, durations = _convert("Brown Sugar", tmp_path)
    for bar in (2, 3, 8, 9):
        assert bars[bar]["status"] == "written", f"BROWN_SUGAR_BAR_{bar}_REFUSED"
    # bar 9 is one whole note: the long crescent from bar 8's last eighth is its tie
    assert _shape(durations, 9) == [("whole", 0, False, True)], "BROWN_SUGAR_9_TIE_STOP"
    last = _shape(durations, 8)[-1]
    assert last == ("eighth", 0, True, False), "BROWN_SUGAR_8_TIE_START"
    # the wave over bar 2 is a located non-event, never a note or rest
    assert [e["kind"] for e in _events(durations, 2)].count("rest") == 1
    assert durations["diagnostics"]["non_events_by_reason"].get("wavy_line_outside_staff", 0) >= 1


def _check_heartbreaker(tmp_path):
    bars, durations = _convert("Heartbreaker", tmp_path)
    assert bars[6]["status"] == "written" and bars[7]["status"] == "written", "HEARTBREAKER_BARS_REFUSED"
    assert _shape(durations, 6) == [("eighth", 0, False, False), ("eighth", 0, False, False),
                                    ("eighth", 0, False, False), ("eighth", 0, True, False),
                                    ("half", 0, True, True)], "HEARTBREAKER_6_VALUES_OR_TIES"
    assert _shape(durations, 7) == [("whole", 0, False, True)], "HEARTBREAKER_7_TIE_STOP"
    assert not durations["diagnostics"].get("unclassified_tie_contours"), "TIE_CONTOUR_STILL_REFUSED"


def _check_waves(tmp_path_factory_dir):
    for source, bar, count in (("Castles Made of Sand", 8, 16), ("Crossroads", 24, 7)):
        sub = tmp_path_factory_dir / source.replace(" ", "_")
        sub.mkdir()
        bars, durations = _convert(source, sub)
        assert bars[bar]["status"] == "written", f"{source}_BAR_{bar}_REFUSED"
        assert len(_events(durations, bar)) == count, f"{source}_EVENT_COUNT"
        assert durations["diagnostics"]["non_events_by_reason"].get("wavy_line_outside_staff", 0) >= 1


def _check_back_in_black(tmp_path):
    bars, durations = _convert("Back In Black", tmp_path)
    assert bars[1]["status"] == "written", "BACK_IN_BLACK_BAR_1_REFUSED"  # vibrato line over the last eighth
    assert bars[3]["status"] == "written", "BACK_IN_BLACK_BAR_3_REFUSED"  # slur over three heads
    assert len(_events(durations, 1)) == 15 and len(_events(durations, 3)) == 21
    assert all(not e["tie"]["start"] and not e["tie"]["stop"] for e in _events(durations, 3)[:-1]), "SLUR_READ_AS_TIE"


def _check_boxed_label(tmp_path):
    bars, durations = _convert("7_Grateful_Dead_Melodies", tmp_path)
    for bar in (8, 9, 45):
        assert bars[bar]["status"] == "refused", f"BAR_{bar}_MUST_STAY_REFUSED"  # no rhythm mark is printed
        assert bars[bar]["detail"] != "unclassified_mark_below_strings", f"BAR_{bar}_FRAME_IS_NOT_A_RHYTHM_MARK"


def _check_hammer_ons_stay_unread_as_ties(tmp_path):
    # Hammer-on / pull-off slurs ("H", "P" printed over them) joining two heads that sit on one staff
    # position are not ties; none of these events may carry a tie.
    for source, bars in (("Bebop Licks in Am", (1, 2)), ("Combining_Maj_minor_pent_-_A", (0, 2, 4))):
        sub = tmp_path / source.replace(" ", "_")
        sub.mkdir()
        _bars, durations = _convert(source, sub)
        for bar in bars:
            assert not any(e["tie"]["start"] or e["tie"]["stop"] for e in _events(durations, bar)),                 f"{source}_BAR_{bar}_HAMMER_ON_READ_AS_TIE"


def _check_correct_refusals(tmp_path):
    bars, _durations = _convert("Derek Trucks BB King", tmp_path)
    for bar in (4, 5, 6, 13, 15):
        assert bars[bar]["status"] == "refused", f"DEREK_BAR_{bar}_MUST_STAY_REFUSED"


def test_brown_sugar_tall_tie_and_vibrato_bars_are_written_and_match_the_printed_page(tmp_path):
    """Rejects a tall tie crescent or a vibrato line refusing the bar, a lost tie, or a wrong value."""
    _check_brown_sugar(tmp_path)


def test_heartbreaker_long_ties_are_read(tmp_path):
    """Rejects a long tie (half note to whole note, over a barline) left refused as an unclassified arc."""
    _check_heartbreaker(tmp_path)


def test_vibrato_line_over_noteheads_does_not_refuse_the_bar(tmp_path):
    """Rejects a thin zigzag above the staff, over heads, refusing a bar as an overlapping form."""
    _check_waves(tmp_path)


def test_slur_over_three_heads_is_a_slur_not_a_refusal_or_a_tie(tmp_path):
    """Rejects a stem-side slur refused for sitting clear of its heads, or a slur read as a tie."""
    _check_back_in_black(tmp_path)


def test_framed_section_label_is_not_a_rhythm_mark(tmp_path):
    """Rejects a framed text label under the TAB being reported as an unclassified mark below the strings."""
    _check_boxed_label(tmp_path)


def test_hammer_on_slurs_are_not_read_as_ties(tmp_path):
    """Rejects a long crescent over two same-position heads (a hammer-on/pull-off) being read as a tie."""
    _check_hammer_ons_stay_unread_as_ties(tmp_path)


def test_parenthesised_ghost_note_bars_stay_refused(tmp_path):
    """Rejects the new rules reading parenthesised/accidental forms (no IR representation) as non-events."""
    _check_correct_refusals(tmp_path)


def test_mutant_drop_wavy_line_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_is_wavy_line_outside_staff", lambda glyph, staff: False)
    with pytest.raises(AssertionError):
        _check_brown_sugar(tmp_path)


def test_mutant_drop_crescent_ties_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_shallow_crescent_ties", lambda glyphs, events, space, neighbours: [])
    with pytest.raises(AssertionError):
        _check_heartbreaker(tmp_path)


def test_mutant_centre_only_slur_reach_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_vertical_gap", lambda head, y: abs(head.cy - y))
    with pytest.raises(AssertionError):
        _check_back_in_black(tmp_path)


def test_mutant_drop_boxed_label_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(rhythm, "_is_boxed_text_label", lambda drawing, box, words: False)
    with pytest.raises(AssertionError):
        _check_boxed_label(tmp_path)


def test_mutant_any_curve_is_slur_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nd, "_slanted_slur_ids", lambda glyphs, events, space: {g.ident for g in glyphs if g.curved})
    with pytest.raises(AssertionError):
        _check_correct_refusals(tmp_path)


def test_mutant_no_hammer_on_guard_fails(tmp_path, monkeypatch):
    # On the approved set the rise bound and the accidental guard each keep these arcs from being read as
    # ties (either alone is enough), so the mutant removes both.
    monkeypatch.setattr(nd, "_carries_accidental", lambda head, neighbours, space: False)
    monkeypatch.setattr(nd, "ARC_MAX_RISE_RATIO", 1000.0)
    with pytest.raises(AssertionError):
        _check_hammer_ons_stay_unread_as_ties(tmp_path)
