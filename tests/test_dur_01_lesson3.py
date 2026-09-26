"""DUR-01 real-source acceptance: Lesson-3.pdf against Lesson-3.gp, per event.

The ground truth is read by scripts/native_slice_reference.py, the independent standard-library
GPIF reader, through scripts/dur_01_compare.py. Assertions hold counts, indices and codes only.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from score2gp.notation_omr.note_duration import read_note_durations

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "fixtures" / "private" / "Lesson-3.pdf"
GP = ROOT / "fixtures" / "private" / "Lesson-3.gp"

pytestmark = pytest.mark.skipif(not (PDF.exists() and GP.exists()), reason="private Lesson-3 corpus not mounted")


def _compare_module():
    spec = importlib.util.spec_from_file_location("dur_01_compare", ROOT / "scripts" / "dur_01_compare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def comparison():
    compare = _compare_module()
    records = read_note_durations(PDF, time_signature=(4, 4))
    return records, compare.compare(records, compare.ground_truth(GP))


def test_ground_truth_comes_from_the_independent_reader():
    source = (ROOT / "scripts" / "native_slice_reference.py").read_text(encoding="utf-8")
    assert "import score2gp" not in source and "from score2gp" not in source


def test_first_system_every_event_read_and_equal_to_ground_truth(comparison):
    _, result = comparison
    first = result["summary"]["first_system"]
    assert first == {"bars": 3, "events": 17, "matched": 17, "all_read_and_equal": True}


def test_whole_document_coverage_and_match_rate(comparison):
    records, result = comparison
    summary = result["summary"]
    assert summary["ground_truth_bars"] == summary["read_bars"] == 66
    assert summary["ground_truth_events"] == 465
    assert summary["read_events"] == 465 and summary["matched_events"] == 465
    assert summary["coverage"] == 1.0 and summary["match_rate"] == 1.0
    assert summary["mismatches"] == [] and summary["causes"] == {}
    assert records["summary"]["unread_events"] == 0


def test_every_mismatch_would_be_located_by_page_bar_and_event(comparison):
    _, result = comparison
    for row in result["rows"]:
        assert {"page_index", "system_index", "bar_index", "event_index", "cause"} <= set(row)


def test_bar_total_is_only_a_check_against_the_declared_signature(comparison):
    records, _ = comparison
    assert records["summary"]["bar_check_status"] == {"match": 66}
    assert {c["time_signature_source"] for c in records["bar_checks"]} == {"caller_declared"}
    undeclared = read_note_durations(PDF)
    assert [e["duration_quarters"] for e in undeclared["events"]] == [e["duration_quarters"] for e in records["events"]]
    assert undeclared["summary"]["bar_check_status"] == {"time_signature_unread": 66}
