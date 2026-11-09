"""GROUP-03: the sources still refused at TAB grouping, located on the real sources.

Re-measured, not trusted: four approved sources end in ``pdf_only_tab_grouping_unsafe``. Two are scanned books
(already located by NOROUTE-01), one is a hand-drawn raster page whose text layer holds no TAB row, one prints
ASCII TAB rows with no bar separator and no rhythm. None can be written without inventing a bar boundary or a
duration, so every one stays refused; this test pins that and pins the located cause of the two that had none.

Oracle: the printed pages, viewed (counts and classes only). No reference file exists for any of the four, so
nothing here is independently verified. Synthetic tests carry no acceptance weight; none are used.
Mutant:
  DROP_UNGROUPED_LOCATION   `_ungrouped_source_details` returns {}: the refusal of the ASCII page and of the
                            hand-drawn page no longer says why (the diagnostics carry only the warning code).
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp import build_ir
from score2gp.cli import app

PRIVATE = Path(__file__).resolve().parents[1] / "fixtures/private"
ASCII_SOURCE = "Lick in All 5 CAGED Shapes start on the 5 _ guitar tab creator"
TEXT_SOURCE = "LegatoLicks"


def _refusal(tmp_path, name):
    pdf = PRIVATE / f"{name}.pdf"
    assert pdf.is_file(), "REQUIRED_GROUP_03_SOURCE_MISSING"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab",
                                     "--out", str(tmp_path / "o.gp"), "--work-dir", str(tmp_path / "build")])
    assert result.exit_code == 4, f"GROUP_03_EXIT_{result.exit_code}"
    assert not (tmp_path / "o.gp").exists(), "UNSETTLED_SOURCE_WRITTEN"
    diagnostics = json.loads((tmp_path / "build/diagnostics.json").read_bytes())
    assert diagnostics["category"] == "pdf_only_tab_grouping_unsafe"
    return diagnostics["details"]


def _check_ascii(tmp_path):
    details = _refusal(tmp_path, ASCII_SOURCE)
    assert details["refusal_warning_code"] == "pdf_no_systems_detected"
    assert details["located_reason"] == "ascii_tab_rows_without_barlines_or_rhythm", "ASCII_REFUSAL_NOT_LOCATED"
    # three six-row blocks printed (viewed page); no '|' separator and no rhythm mark anywhere
    assert details["ascii_block_count"] == 3
    assert details["ascii_bar_separator_count"] == 0
    assert details["ascii_timing_statuses"] == ["timing_unavailable"]


def _check_text(tmp_path):
    details = _refusal(tmp_path, TEXT_SOURCE)
    assert details["located_reason"] == "text_without_tab_rows", "TEXT_REFUSAL_NOT_LOCATED"


def test_ascii_rows_without_barlines_or_rhythm_stay_refused_and_located(tmp_path):
    """Rejects: writing the ASCII page with invented bars/durations, or refusing it without saying why."""
    _check_ascii(tmp_path)


def test_hand_drawn_page_without_tab_rows_stays_refused_and_located(tmp_path):
    """Rejects: writing the hand-drawn page, or refusing it without saying why."""
    _check_text(tmp_path)


def test_mutant_drop_ungrouped_location_fails_real_sources(tmp_path, monkeypatch):
    """DROP_UNGROUPED_LOCATION must fail both located-cause checks on the real sources."""
    monkeypatch.setattr(build_ir, "_ungrouped_source_details", lambda tabraw: {})
    with pytest.raises(KeyError):
        _check_ascii(tmp_path / "a")
    with pytest.raises(KeyError):
        _check_text(tmp_path / "b")


def _ascii_candidate(block, separators):
    from types import SimpleNamespace
    return SimpleNamespace(kind="fret", raw={
        "ascii_tab": True, "ascii_block_id": block, "ascii_bar_separator_count": separators,
        "ascii_timing_status": "timing_unavailable"})


def test_separator_count_is_taken_once_per_block_not_per_candidate():
    """Rejects: summing the block-level separator count over every fret candidate (3 separators x 54 candidates
    reported 162). Infrastructure test of the diagnostic arithmetic: the extractor stores the block's count on
    each of its candidates, which the real ASCII source (0 separators) cannot exercise; no acceptance weight."""
    from types import SimpleNamespace
    candidates = ([_ascii_candidate("ascii-p000-s000", 3) for _ in range(54)]
                  + [_ascii_candidate("ascii-p000-s001", 2) for _ in range(10)])
    details = build_ir._ungrouped_source_details(SimpleNamespace(candidates=candidates))
    assert details["located_reason"] == "ascii_tab_rows_without_rhythm"
    assert details["ascii_block_count"] == 2
    assert details["ascii_bar_separator_count"] == 5
    assert details["ascii_fret_candidates"] == 64
