"""CFW-04 public vector fixtures: source geometry through note reader, TAB route, and GPIF."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

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
