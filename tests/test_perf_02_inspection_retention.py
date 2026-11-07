"""PERF-02: inspection releases per-page geometry no later stage reads.

Acceptance rests on the private real sources (counts only). Mutants rejected:
  * M1 "retain the released structure again": inspect_pdf(retain_geometry_detail=False)
    keeps pdf_staff_notation_diagnostics / geometry lists -> the node-count and
    key assertions fail, and the 34-page source hits the unchanged budget.
  * M2 "release but do not rebuild": extract_tab stops reading staff diagnostics
    -> tab_raw candidates differ from the fully retained run.
  * M3 "raise or bypass the budget": the fully retained 34-page inspection must
    still raise pdf_resource_inspection_page_nodes_exceeded.
"""

from pathlib import Path

import pytest

from score2gp.pdf import extract_tab, inspect_pdf
from score2gp.pdf_resource_budget import (
    INSPECTION_PAGE_NODE_LIMIT,
    PdfInspectionResourceLimit,
    inspection_page_nodes,
)

PRIVATE = Path(__file__).resolve().parent.parent / "fixtures" / "private"


def _source(name: str) -> Path:
    path = PRIVATE / name
    if not path.exists():
        pytest.fail(f"mandatory real-source test: mount score2gp-private-fixtures ({name} missing)")
    return path


def test_lean_inspection_retains_far_fewer_nodes_on_real_source(tmp_path):
    pdf = _source("Lesson-6.pdf")
    full = inspect_pdf(pdf, tmp_path / "full")
    lean = inspect_pdf(pdf, tmp_path / "lean", retain_geometry_detail=False)
    assert len(lean["pages"]) == len(full["pages"]) > 0
    for page in lean["pages"]:
        assert "pdf_staff_notation_diagnostics" not in page
        for cand in page["geometry_candidates"]:
            assert "x_aligned_clusters" not in cand and "left_margin_primitives" not in cand
    full_nodes = inspection_page_nodes(full["pages"])
    lean_nodes = inspection_page_nodes(lean["pages"])
    assert lean_nodes * 3 < full_nodes


def test_released_inspection_leaves_tabraw_unchanged_on_real_source(tmp_path):
    pdf = _source("Lesson-6.pdf")
    full_inspection = inspect_pdf(pdf, tmp_path / "i")
    full = extract_tab(pdf, tmp_path / "a", inspection=full_inspection, diagnostic_artifacts=False)
    lean = extract_tab(pdf, tmp_path / "b", diagnostic_artifacts=False)
    assert full["candidates"] == lean["candidates"]
    assert full["structural_signals"] == lean["structural_signals"]
    assert any(
        (c.get("raw") or {}).get("duration_evidence") for c in lean["candidates"]
    ), "source must exercise the rhythm stage that needs the released diagnostics"


def test_34_page_source_fits_unchanged_budget_and_full_retention_still_refused(tmp_path):
    pdf = _source("Melodic_Expressions.pdf")
    assert INSPECTION_PAGE_NODE_LIMIT == 2_000_000
    with pytest.raises(PdfInspectionResourceLimit):
        inspect_pdf(pdf, tmp_path / "full")
    lean = inspect_pdf(pdf, tmp_path / "lean", retain_geometry_detail=False)
    assert len(lean["pages"]) == 34
    assert inspection_page_nodes(lean["pages"]) <= INSPECTION_PAGE_NODE_LIMIT


def test_fully_retained_node_count_is_unchanged_on_real_source(tmp_path):
    # Mutant: changing what the default inspection retains (or how nodes are
    # counted) moves this pinned count, so the budget basis cannot drift.
    full = inspect_pdf(_source("Lesson-6.pdf"), tmp_path)
    assert inspection_page_nodes(full["pages"]) - 1 == 676202
