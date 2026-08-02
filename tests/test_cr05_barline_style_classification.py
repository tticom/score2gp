from __future__ import annotations

from typing import Any
import fitz
import pytest

from score2gp.pdf import filter_tab_barline_candidates
from score2gp.pdf_geometry import _LineSegment, _drawing_segments
from score2gp.report import _grouping_system_html


def test_cr05a_same_drawing_multiple_lines_double_barline() -> None:
    """Two independent line items in the same drawing dictionary produce barline_style='double'."""
    line_ys = [154.0, 160.4, 166.8, 173.2, 179.6, 186.0]
    seg1 = _LineSegment(100.0, 150.0, 100.0, 190.0, primitive_kind="line", primitive_id="drawing_0_item_0", stroke_width=1.0)
    seg2 = _LineSegment(103.0, 150.0, 103.0, 190.0, primitive_kind="line", primitive_id="drawing_0_item_1", stroke_width=1.0)

    res = filter_tab_barline_candidates([seg1, seg2], 154.0, 186.0, line_ys, 36.0, 575.0)
    details = res["barline_candidates_details"]

    assert len(details) == 2
    assert details[0]["barline_style"] == "double"
    assert details[0]["cluster_size"] == 2
    assert details[1]["barline_style"] == "double"
    assert details[1]["cluster_size"] == 2


def test_cr05a_filled_rect_canonicalization_pipeline() -> None:
    """Single narrow filled rectangle item produces barline_style='regular' and canonical representative x."""
    doc = fitz.open()
    page = doc.new_page()
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(100.0, 150.0, 102.0, 190.0))
    shape.finish(fill=(0, 0, 0))
    shape.commit()

    segments = _drawing_segments(page.get_drawings())
    vertical_segments = [s for s in segments if s.is_vertical]

    line_ys = [154.0, 160.4, 166.8, 173.2, 179.6, 186.0]
    res = filter_tab_barline_candidates(vertical_segments, 154.0, 186.0, line_ys, 36.0, 575.0)

    assert res["valid_barlines"] == [102.0]
    details = res["barline_candidates_details"]
    assert len(details) == 2
    assert any(d["final_decision"] == "accepted" and d["barline_style"] == "regular" and d["cluster_size"] == 1 for d in details)
    assert any(d["final_decision"] == "rejected" and d["rejection_reason"] == "pdf_barline_rect_secondary" and d["barline_style"] == "regular" for d in details)


def test_cr05a_rectangle_width_threshold_rejections() -> None:
    """Exact inclusive boundaries at 4.0 - eps, 4.0, 4.0 + eps, 12.0 - eps, 12.0, and 12.0 + eps."""
    line_ys = [154.0, 160.4, 166.8, 173.2, 179.6, 186.0]
    eps = 0.01

    widths_and_expected = [
        (4.0 - eps, "accepted", "regular", None),
        (4.0, "accepted", "regular", None),
        (4.0 + eps, "rejected", "ambiguous", "pdf_barline_ambiguous_rect_width"),
        (12.0 - eps, "rejected", "ambiguous", "pdf_barline_ambiguous_rect_width"),
        (12.0, "rejected", "ambiguous", "pdf_barline_ambiguous_rect_width"),
        (12.0 + eps, "rejected", "ambiguous", "pdf_barline_decorative_fill_or_wide_rect"),
    ]

    for rect_w, expected_decision, expected_style, expected_reason in widths_and_expected:
        seg1 = _LineSegment(100.0, 150.0, 100.0, 190.0, primitive_kind="rect_edge", primitive_id="d0_i0", stroke_width=1.0, source_rect_width=rect_w)
        seg2 = _LineSegment(100.0 + rect_w, 150.0, 100.0 + rect_w, 190.0, primitive_kind="rect_edge", primitive_id="d0_i0", stroke_width=1.0, source_rect_width=rect_w)

        res = filter_tab_barline_candidates([seg1, seg2], 154.0, 186.0, line_ys, 36.0, 575.0)
        details = res["barline_candidates_details"]

        if expected_decision == "accepted":
            assert any(d["final_decision"] == "accepted" and d["barline_style"] == expected_style for d in details), f"Failed for w={rect_w}"
        else:
            for d in details:
                assert d["final_decision"] == "rejected", f"Failed decision for w={rect_w}"
                assert d["barline_style"] == expected_style, f"Failed style for w={rect_w}"
                assert d["rejection_reason"] == expected_reason, f"Failed reason for w={rect_w}"


def test_cr05a_mixed_primitive_merge_fail_closed() -> None:
    """Single merged 'mixed' candidates fail closed to barline_style='ambiguous'."""
    line_ys = [154.0, 160.4, 166.8, 173.2, 179.6, 186.0]
    mixed_seg = _LineSegment(100.0, 150.0, 100.0, 190.0, primitive_kind="mixed", primitive_id=None, stroke_width=1.0, source_rect_width=2.0)

    res = filter_tab_barline_candidates([mixed_seg], 154.0, 186.0, line_ys, 36.0, 575.0)
    details = res["barline_candidates_details"]

    assert len(details) == 1
    assert details[0]["final_decision"] == "rejected"
    assert details[0]["barline_style"] == "ambiguous"
    assert details[0]["rejection_reason"] == "pdf_barline_mixed_primitive_provenance"


def test_cr05a_rejection_precedence_survival() -> None:
    """Special mixed/width rejection reasons survive final candidate detail construction."""
    line_ys = [154.0, 160.4, 166.8, 173.2, 179.6, 186.0]
    # Short segment that would also fail height/gap check
    short_wide_rect = _LineSegment(100.0, 160.0, 100.0, 165.0, primitive_kind="rect_edge", primitive_id="d0_i0", stroke_width=1.0, source_rect_width=15.0)

    res = filter_tab_barline_candidates([short_wide_rect], 154.0, 186.0, line_ys, 36.0, 575.0)
    details = res["barline_candidates_details"]

    assert len(details) == 1
    assert details[0]["final_decision"] == "rejected"
    assert details[0]["barline_style"] == "ambiguous"
    assert details[0]["rejection_reason"] == "pdf_barline_decorative_fill_or_wide_rect"


def test_cr05a_null_primitive_id_fail_closed() -> None:
    """Legacy _LineSegment candidates with primitive_id=None evaluate safely."""
    line_ys = [154.0, 160.4, 166.8, 173.2, 179.6, 186.0]
    seg1 = _LineSegment(100.0, 150.0, 100.0, 190.0, primitive_kind="line", primitive_id=None)
    seg2 = _LineSegment(103.0, 150.0, 103.0, 190.0, primitive_kind="line", primitive_id=None)

    res = filter_tab_barline_candidates([seg1, seg2], 154.0, 186.0, line_ys, 36.0, 575.0)
    details = res["barline_candidates_details"]

    assert len(details) == 2
    assert details[0]["barline_style"] == "double"
    assert details[0]["cluster_size"] == 2
    assert details[1]["barline_style"] == "double"
    assert details[1]["cluster_size"] == 2


def test_cr05a_edge_triple_cluster_style_ambiguous() -> None:
    """3 strokes at right edge retain edge representative in valid_barlines but mark barline_style='ambiguous'."""
    line_ys = [154.0, 160.4, 166.8, 173.2, 179.6, 186.0]
    seg1 = _LineSegment(88.0, 150.0, 88.0, 190.0, primitive_kind="line", primitive_id="d0_i0")
    seg2 = _LineSegment(94.0, 150.0, 94.0, 190.0, primitive_kind="line", primitive_id="d0_i1")
    seg3 = _LineSegment(100.0, 150.0, 100.0, 190.0, primitive_kind="line", primitive_id="d0_i2")

    res = filter_tab_barline_candidates([seg1, seg2, seg3], 154.0, 186.0, line_ys, 36.0, 100.0)

    assert res["valid_barlines"] == [100.0]
    details = res["barline_candidates_details"]
    assert len(details) == 3
    for d in details:
        assert d["barline_style"] == "ambiguous"
        assert d["cluster_size"] == 3


def test_cr05a_report_html_rendering_barline_style() -> None:
    """HTML report rendering displays barline_style and cluster_size when populated and handles legacy details cleanly."""
    populated_system: dict[str, Any] = {
        "page_index": 1,
        "system_index": 1,
        "staff_index": 1,
        "system_inference": "test",
        "tab_staff_bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 100},
        "tab_line_ys": [10, 20, 30, 40, 50, 60],
        "bar_boxes": [],
        "candidate_ids": [],
        "barline_candidates_count": 1,
        "valid_barline_count": 1,
        "rejected_barline_count": 0,
        "rejection_reasons": {},
        "barline_candidates_details": [
            {
                "x": 100.0,
                "height": 40.0,
                "gaps_crossed": 5,
                "staff_height": 32.0,
                "coverage_ratio": 1.0,
                "final_decision": "accepted",
                "absolute_height_decision": "accepted",
                "relative_staff_crossing_decision": "accepted",
                "rejection_reason": None,
                "barline_style": "double",
                "cluster_size": 2,
            }
        ],
        "grouping_confidence": 1.0,
        "grouping_warnings": [],
    }

    legacy_system: dict[str, Any] = {
        "page_index": 1,
        "system_index": 2,
        "staff_index": 1,
        "system_inference": "test",
        "tab_staff_bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 100},
        "tab_line_ys": [10, 20, 30, 40, 50, 60],
        "bar_boxes": [],
        "candidate_ids": [],
        "barline_candidates_count": 1,
        "valid_barline_count": 1,
        "rejected_barline_count": 0,
        "rejection_reasons": {},
        "barline_candidates_details": [
            {
                "x": 100.0,
                "height": 40.0,
                "gaps_crossed": 5,
                "staff_height": 32.0,
                "coverage_ratio": 1.0,
                "final_decision": "accepted",
                "absolute_height_decision": "accepted",
                "relative_staff_crossing_decision": "accepted",
                "rejection_reason": None,
            }
        ],
        "grouping_confidence": 1.0,
        "grouping_warnings": [],
    }

    pop_html = _grouping_system_html(populated_system)
    assert "style=double" in pop_html
    assert "cluster_size=2" in pop_html

    leg_html = _grouping_system_html(legacy_system)
    assert "Candidate at x=100.0" in leg_html


def test_cr05a_filled_rect_sub_pt_canonical_right_edge() -> None:
    """End-to-end PyMuPDF pipeline test verifying 0.8pt rectangle preserves canonical right edge (100.8)."""
    from score2gp.pdf import _detect_tab_systems

    doc = fitz.open()
    page = doc.new_page()
    shape = page.new_shape()
    for y in [154.0, 160.4, 166.8, 173.2, 179.6, 186.0]:
        shape.draw_line(fitz.Point(36.0, y), fitz.Point(575.0, y))
    shape.draw_rect(fitz.Rect(100.0, 150.0, 100.8, 190.0))
    shape.finish(fill=(0, 0, 0))
    shape.commit()

    systems = _detect_tab_systems(page, 1)
    assert len(systems) == 1
    assert systems[0].barlines == [100.8]
    details = systems[0].barline_candidates_details
    assert len(details) == 1
    assert details[0]["x"] == 100.8
    assert details[0]["final_decision"] == "accepted"
    assert details[0]["barline_style"] == "regular"
    assert details[0]["cluster_size"] == 1

