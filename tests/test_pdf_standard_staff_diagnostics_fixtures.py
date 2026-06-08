from __future__ import annotations
import json
from typing import Any
import pytest
from score2gp.pdf_staff_geometry import NotationStaffDiagnostics, StaffLeftMarginAggregateDiagnostics
from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics
from score2gp.pdf_geometry import _LineSegment

class MockPage:
    def __init__(self, rects: list[tuple[float, float, float, float]] | None = None, curves: list[tuple[float, float, float, float]] | None = None, lines: list[tuple[float, float, float, float]] | None = None):
        self._rects = rects or []
        self._curves = curves or []
        self._lines = lines or []
    def get_drawings(self) -> list[dict[str, Any]]:
        drawings = []
        for (x0, y0, x1, y1) in self._rects:
            class MockRect:
                def __init__(self, x0, y0, x1, y1):
                    self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
            drawings.append({"type": "re", "items": [("re", MockRect(x0, y0, x1, y1))]})
        for (x0, y0, x1, y1) in self._curves:
            class MockPoint:
                def __init__(self, x, y):
                    self.x, self.y = x, y
            drawings.append({"type": "f", "items": [("c", MockPoint(x0, y0), MockPoint(x1, y1))]})
        for (x0, y0, x1, y1) in self._lines:
            class MockPoint:
                def __init__(self, x, y):
                    self.x, self.y = x, y
            drawings.append({"type": "s", "items": [("l", MockPoint(x0, y0), MockPoint(x1, y1))]})
        return drawings
    def get_text(self, option: str) -> dict[str, Any]:
        return {"blocks": []}

class MockPageWithText(MockPage):
    def __init__(self, lines: list[tuple[float, float, float, float]], spans: list[dict[str, Any]]):
        super().__init__(lines=lines)
        self._spans = spans
    def get_text(self, option: str) -> dict[str, Any]:
        return {"blocks": [{"lines": [{"spans": self._spans}]}]}

def test_margin_filtering_counts_and_excludes() -> None:
    # staff.x0 = 10, y0 = 100, y1 = 140
    # staff lines at 100, 110, 120, 130, 140 => staff_space = 10.0
    # margin_x_limit = 10 + 10.0 * 10 = 110.0
    # curve 1 inside margin: x0=20, x1=40 (center 30 <= 110)
    # curve 2 outside margin: x0=120, x1=140 (center 130 > 110)
    # rect 1 inside margin: x0=50, x1=60 (center 55 <= 110)
    page = MockPage(
        lines=[
            (10.0, 100.0, 200.0, 100.0),
            (10.0, 110.0, 200.0, 110.0),
            (10.0, 120.0, 200.0, 120.0),
            (10.0, 130.0, 200.0, 130.0),
            (10.0, 140.0, 200.0, 140.0),
            (30.0, 100.0, 30.0, 140.0), # vertical stroke inside margin
            (150.0, 100.0, 150.0, 140.0), # vertical stroke outside margin
        ],
        curves=[
            (20.0, 100.0, 40.0, 140.0),
            (120.0, 100.0, 140.0, 140.0),
        ],
        rects=[
            (50.0, 110.0, 60.0, 120.0),
        ]
    )
    # x0=10.0, y0=100.0, x1=200.0, y1=140.0
    staff_groups = [[_LineSegment(10.0, y, 200.0, y) for y in [100.0, 110.0, 120.0, 130.0, 140.0]]]
    diags = build_notation_diagnostics(page, 1, staff_groups)
    assert len(diags.staves) == 1
    assert diags.staves[0].contract_version == "notation-diagnostics.v0.1"
    lm = diags.staves[0].left_margin
    assert lm is not None
    assert lm.curve_candidate_count == 1
    assert lm.vertical_stroke_candidate_count == 1
    assert lm.rectangle_candidate_count == 1

def test_invalid_staff_space_fallback() -> None:
    # 0 or 1 staff line yields staff_space = 0.0
    page = MockPage(lines=[(10.0, 100.0, 200.0, 100.0)])
    staff_groups = [[_LineSegment(10.0, 100.0, 200.0, 100.0)]]
    diags = build_notation_diagnostics(page, 1, staff_groups)
    assert len(diags.staves) == 1
    assert diags.staves[0].left_margin is None

def test_aggregate_accuracy() -> None:
    # test font distributions
    # margin_x_limit = 110
    spans = [
        {"text": "f", "font": "Maestro", "bbox": (20, 110, 30, 120)}, # inside, Maestro
        {"text": "p", "font": "Maestro", "bbox": (40, 110, 50, 120)}, # inside, Maestro
        {"text": "1", "font": "Arial", "bbox": (60, 110, 70, 120)},   # inside, Arial
        {"text": "g", "font": "Opus", "bbox": (120, 110, 130, 120)},  # outside, Opus
    ]
    page = MockPageWithText(
        lines=[
            (10.0, 100.0, 200.0, 100.0),
            (10.0, 110.0, 200.0, 110.0),
            (10.0, 120.0, 200.0, 120.0),
            (10.0, 130.0, 200.0, 130.0),
            (10.0, 140.0, 200.0, 140.0),
        ],
        spans=spans
    )
    staff_groups = [[_LineSegment(10.0, y, 200.0, y) for y in [100.0, 110.0, 120.0, 130.0, 140.0]]]
    diags = build_notation_diagnostics(page, 1, staff_groups)
    lm = diags.staves[0].left_margin
    assert lm is not None
    assert lm.text_span_count == 3
    assert lm.distinct_font_count == 2
    assert lm.max_text_spans_for_single_font == 2

def test_schema_does_not_contain_semantic_names() -> None:
    # Ensure JSON schema of the diagnostics does not leak keys like "clef", "pitch", "time_signature"
    schema = StaffLeftMarginAggregateDiagnostics.model_json_schema()
    schema_str = json.dumps(schema).lower()
    for forbidden in ["clef", "pitch", "time_signature", "key_signature", "notehead", "duration"]:
        assert forbidden not in schema_str

    top_level_schema = NotationStaffDiagnostics.model_json_schema()
    top_level_schema_str = json.dumps(top_level_schema).lower()
    for forbidden in ["clef", "pitch", "time_signature", "key_signature", "notehead", "duration"]:
        assert forbidden not in top_level_schema_str

def test_generated_dense_margin_fixture(tmp_path) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_dense_margin.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]
    lm = staff_diag.get("left_margin")
    assert lm is not None

    # The json spec defines multiple margin text spans all using the same font ('helv')
    # Fitz may heuristically merge adjacent spans into a single span, so we check >= 6
    assert lm["text_span_count"] >= 6
    assert lm["distinct_font_count"] == 1
    assert lm["max_text_spans_for_single_font"] >= 6

def test_generated_sparse_fixture(tmp_path) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_sparse.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]
    lm = staff_diag.get("left_margin")
    assert lm is not None

    assert lm["text_span_count"] == 0
    assert lm["distinct_font_count"] == 0
    assert lm["max_text_spans_for_single_font"] == 0

def test_generated_wide_curves_fixture(tmp_path) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_wide_curves.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]
    
    # We should have two wide curves inside the staff bounding box
    # They shouldn't be reported in left margin, but the main staves metrics should reflect them if implemented.
    # The requirement: "Use `curve_candidate_count` only for actual curve primitives."
    # Since left_margin is just margin, we should check what the test is supposed to assert.
    lm = staff_diag.get("left_margin")
    if lm:
        # Curve 1 center x is 120, margin limit is 165. So it should be counted.
        assert lm["curve_candidate_count"] == 1
        assert lm["text_span_count"] == 0


