"""CFW-04 public vector fixtures: source geometry through note reader, TAB route, and GPIF."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

import pytest

from score2gp import pdf_tab_bar_assembler as assembler
from score2gp.notation_omr import note_duration as nd


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "pdf" / "cfw_04"


def _read(name: str) -> dict:
    return nd.read_note_durations(FIXTURES / name, time_signature=(4, 4))


def _convert(name: str):
    # The production route treats paths containing "test" differently when extracting TAB. Work under
    # the repository's ignored directory and create it explicitly for a clean git-archive checkout.
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cfw04-", dir=work) as directory:
        folder = Path(directory)
        output = folder / "output.gp"
        cmd = [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(FIXTURES / name),
               "--out", str(output), "--work-dir", str(folder / "intermediate"),
               "--json-report", str(folder / "report.json"), "--pdf-only-tab", "--time-signature", "4/4",
               "--no-strict"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        route = json.loads((folder / "intermediate" / "note-type-route.json").read_text(encoding="utf-8"))
        package = output.read_bytes() if output.exists() else None
        return result.returncode, route, package


def test_source_small_head_flag_and_stemless_and_wave_have_separate_outcomes():
    read = _read("grace_stemless_wave.pdf")
    assert read["summary"]["bars"] == 1
    assert read["summary"]["events"] == 5
    assert read["bar_checks"][0]["status"] == "match"
    assert Fraction(read["bar_checks"][0]["total_quarters"]) == 4
    grace = read["events"][0]
    assert grace["flags"]["count"] == 1
    assert grace["grace"]["beat_event_index"] == read["events"][1]["event_index"]
    assert 0 < grace["grace"]["gap_spaces"] < nd.GRACE_MAX_GAP_SPACES
    assert Fraction(grace["duration_quarters"]) == 0
    assert read["diagnostics"]["non_events_by_reason"] == {
        "small_notehead_without_stem": 1, "stroke_fragment_outside_staff_band": 1,
    }
    assert all(item["bar_index"] == 0 and len(item["bbox"]) == 4
               for item in read["diagnostics"]["non_events"])


def test_staff_scale_controls_the_small_head_rule(monkeypatch):
    scaled = _read("grace_stemless_wave_2x.pdf")
    assert scaled["bar_checks"][0]["status"] == "match"
    assert scaled["events"][0]["grace"] is not None
    # An absolute-point threshold would miss the same engraved head at twice the page scale.
    monkeypatch.setattr(nd, "_is_small_head", lambda glyph, space: glyph.w < 4.25 and glyph.h < 3.61)
    mutant = _read("grace_stemless_wave_2x.pdf")
    assert "grace" not in mutant["events"][0]
    assert mutant["bar_checks"][0]["status"] != "match"


def test_disabling_small_head_recognition_fails_the_grace_and_stemless_outcome(monkeypatch):
    monkeypatch.setattr(nd, "_is_small_head", lambda glyph, space: False)
    mutant = _read("grace_stemless_wave.pdf")
    assert mutant["bar_checks"][0]["status"] != "match"
    assert mutant["diagnostics"]["non_events_by_reason"].get("small_notehead_without_stem", 0) == 0


def test_gpif_writes_a_zero_time_32nd_grace_on_beat():
    code, route, package = _convert("grace_stemless_wave.pdf")
    assert code == 0
    assert route["summary"]["written_bars"] == 1
    assert package is not None
    spec = importlib.util.spec_from_file_location("cfw04_oracle", ROOT / "tests" / "test_dur_02_oracle.py")
    assert spec and spec.loader
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    events = oracle.read_gp_bars(package, include_grace=True)[0]["events"]
    assert len(events) == 5
    assert [(event["written"], event["grace"]) for event in events] == [
        ("32nd", "OnBeat"), ("quarter", None), ("quarter", None), ("quarter", None), ("quarter", None),
    ]


def test_dotted_cross_bar_stays_refused_at_its_location():
    code, route, package = _convert("dotted_cross.pdf")
    assert code != 0
    assert package is None
    assert route["summary"]["written_bars"] == 0
    bar = route["bars"][0]
    assert bar["reason"] == "bar_total_mismatch"
    assert bar["location"] == {"page_index": 0, "system_index": 0, "bar_index": 0}


def _round_trip(name: str):
    from score2gp.gp_package import extract_score_ir_from_gp

    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cfw04rt-", dir=work) as directory:
        folder = Path(directory)
        output = folder / "output.gp"
        cmd = [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(FIXTURES / name),
               "--out", str(output), "--work-dir", str(folder / "intermediate"),
               "--json-report", str(folder / "report.json"), "--pdf-only-tab", "--time-signature", "4/4",
               "--no-strict"]
        assert subprocess.run(cmd, capture_output=True, text=True, check=False).returncode == 0
        return extract_score_ir_from_gp(output)


def test_written_grace_reads_back_as_a_zero_tick_grace():
    score = _round_trip("grace_stemless_wave.pdf")
    events = sorted(score.bars[0].events, key=lambda e: (e.timing.onset_ticks, 0 if e.timing.grace else 1))
    assert len(events) == 5
    grace, principal = events[0], events[1]
    assert grace.timing.grace is not None
    assert grace.timing.grace.position == "on-beat"
    assert grace.timing.grace.duration == "32nd"
    assert grace.timing.duration_ticks == 0
    assert grace.timing.notated_duration.value == "32nd"
    assert principal.timing.grace is None
    assert principal.timing.onset_ticks == grace.timing.onset_ticks
    assert principal.timing.notated_duration.value == "quarter"
    assert principal.timing.duration_ticks == 960
    assert len({e.id for e in events}) == 5
    assert sum(e.timing.duration_ticks for e in events) == score.bars[0].time_signature.numerator * 960


# --- fail-closed gates: each fixture is engraved like the source it stands for, and each refusal is located ---

REFUSED_GRACE_FIXTURES = [
    ("grace_too_far.pdf", 1, "grace_note_beat_too_far"),
    ("grace_before_rest.pdf", 1, "grace_note_before_rest"),
    ("grace_without_flag.pdf", 0, "grace_note_without_flag"),
    ("mixed_small_full_chord.pdf", 0, "small_notehead_mixed_with_full_size"),
]


@pytest.mark.parametrize(("name", "event_index", "reason"), REFUSED_GRACE_FIXTURES)
def test_gate_refuses_the_event_at_its_location_and_writes_no_bar(name, event_index, reason):
    read = _read(name)
    event = read["events"][event_index]
    assert (event["status"], event["reason"]) == ("unread", reason)
    assert event["written"] is None and event["duration_quarters"] is None
    assert event["bar_index"] == 0 and len(event["location"]["bbox"]) == 4
    assert read["bar_checks"][0]["status"] != "match"
    # No other event is refused: the located refusal is the one gate under test.
    assert [e["reason"] for e in read["events"] if e["status"] != "read"] == [reason]
    code, route, package = _convert(name)
    assert code != 0 and package is None
    assert route["summary"]["written_bars"] == 0
    bar = route["bars"][0]
    assert bar["reason"] == "note_duration_event_unread"
    assert bar["detail"] == reason
    assert bar["location"] == {"page_index": 0, "system_index": 0, "bar_index": 0, "event_index": event_index}


def test_grace_gap_is_over_the_limit_and_before_rest_gap_is_within_it():
    too_far = _read("grace_too_far.pdf")["events"][1]["grace"]
    assert too_far["gap_spaces"] > nd.GRACE_MAX_GAP_SPACES
    before_rest = _read("grace_before_rest.pdf")["events"][1]["grace"]
    # Close enough to attach: only the rest after it refuses it, never the gap.
    assert 0 <= before_rest["gap_spaces"] <= nd.GRACE_MAX_GAP_SPACES


def test_unflagged_small_stemmed_head_is_not_written_as_a_grace():
    read = _read("grace_without_flag.pdf")
    assert read["events"][0]["flags"]["count"] == 0
    assert read["events"][0]["grace"]["beat_event_index"] is not None  # close to its beat: the flag is the only gate
    assert read["events"][0]["status"] == "unread" and read["events"][0]["duration_quarters"] is None


def test_tie_runs_over_a_grace_between_its_two_notes():
    read = _read("tie_over_grace.pdf")
    assert read["bar_checks"][0]["status"] == "match"
    grace = read["events"][1]
    assert grace["grace"]["beat_event_index"] == read["events"][2]["event_index"]
    assert grace["tie"] == {"start": False, "stop": False, "sources": []}
    assert read["events"][0]["tie"]["start"] is True
    assert read["events"][2]["tie"]["stop"] is True
    code, route, package = _convert("tie_over_grace.pdf")
    assert code == 0 and package is not None
    assert route["summary"]["written_bars"] == 1
    assert route["summary"]["match_kinds"].get("tie_continuation") == 1


def test_grace_whose_beat_is_not_the_next_note_is_refused_unattached_at_its_event():
    read = _read("grace_stemless_wave.pdf")
    records = [dict(e) for e in read["events"]]
    assert records[0]["grace"]["beat_event_index"] == records[1]["event_index"]
    records[0]["grace"] = {**records[0]["grace"], "beat_event_index": None}
    matched, refusal = assembler._match_bar(records, [], 4.25, None)
    assert matched == []
    assert refusal["reason"] == "grace_note_beat_unattached"
    assert refusal["event_index"] == records[0]["event_index"]
