from __future__ import annotations

import json

from score2gp.report import build_grouping_diagnostics, write_conversion_report, write_grouping_diagnostics_html, write_warnings


def test_warning_and_report_files(tmp_path) -> None:
    warnings = [{"code": "unsupported-technique", "message": "Bend shape was not recognised."}]
    warnings_path = tmp_path / "warnings.json"
    report_path = tmp_path / "report.html"

    write_warnings(warnings_path, warnings)
    write_conversion_report(report_path, "Report", warnings, {"note_count": 2})

    assert json.loads(warnings_path.read_text()) == warnings
    report = report_path.read_text()
    assert "unsupported-technique" in report
    assert "note_count" in report


def test_grouping_diagnostics_report_describes_blocked_alignment(tmp_path) -> None:
    tabraw = {
        "source_pdf": "public.pdf",
        "inspection_kind": "born-digital",
        "candidates": [
            {
                "id": "pdf-p001-c0001",
                "kind": "fret",
                "raw_text": "12",
                "parsed_fret": 12,
                "page_index": 1,
                "bbox": {"page": 1, "x0": 10, "y0": 20, "x1": 18, "y1": 30},
            }
        ],
        "warnings": [{"code": "missing_pdf_grouping"}],
    }
    report = build_grouping_diagnostics(
        source_pdf="public.pdf",
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw,
        artifacts={
            "tab_raw": "tab_raw.json",
            "warnings": "warnings.json",
            "diagnostic_html": "grouping-diagnostics.html",
            "overlay_images": ["overlays/page-001-grouping.png"],
        },
    )
    report_path = tmp_path / "grouping-diagnostics.html"

    write_grouping_diagnostics_html(report_path, report)

    html = report_path.read_text(encoding="utf-8")
    assert report["grouping_status"] == "missing"
    assert report["grouping"]["schema_version"] == "pdf-grouping.v0.1"
    assert report["grouping"]["system_count"] == 0
    assert report["playable_fret_candidate_count"] == 1
    assert "missing_pdf_grouping" in html
    assert "Extraction succeeded, but grouping failed" in html
    assert "ScoreIR was not written" in html


def test_grouping_diagnostics_premium_html_styling(tmp_path) -> None:
    tabraw = {
        "source_pdf": "public_synthetic_tiny.pdf",
        "inspection_kind": "born-digital",
        "candidates": [
            {
                "id": "pdf-p001-c0001",
                "kind": "fret",
                "raw_text": "7",
                "parsed_fret": 7,
                "page_index": 1,
                "system_index": 1,
                "bar_index": 1,
                "string": 1,
                "bbox": {"page": 1, "x0": 10, "y0": 20, "x1": 18, "y1": 30},
                "raw": {
                    "tab_staff_bbox": {"page": 1, "x0": 5, "y0": 10, "x1": 100, "y1": 50},
                    "tab_line_ys": [12, 18, 24, 30, 36, 42],
                    "barline_xs": [15, 80],
                    "bar_boxes": [{"bar_index": 1, "x0": 15, "y0": 10, "x1": 80, "y1": 50}],
                    "grouping_warnings": ["pdf_bar_box_one_boundary_rejected"],
                    "assignment_warnings": ["pdf_string_assignment_outside_staff"]
                }
            }
        ],
        "warnings": [
            {"code": "partial_pdf_grouping"},
            {"code": "pdf_bar_box_one_boundary_rejected"}
        ],
    }

    report = build_grouping_diagnostics(
        source_pdf="public_synthetic_tiny.pdf",
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw,
        artifacts={
            "tab_raw": "tab_raw.json",
            "warnings": "warnings.json",
            "diagnostic_html": "grouping-diagnostics.html",
            "overlay_images": ["overlays/page-001-grouping.png"],
        },
    )
    report_path = tmp_path / "grouping-diagnostics.html"

    write_grouping_diagnostics_html(report_path, report)

    html_content = report_path.read_text(encoding="utf-8")

    # 1. Assert Verdict banner and badges exist
    assert "verdict-banner" in html_content
    assert "badge status-partial" in html_content
    assert "PARTIAL" in html_content

    # 2. Assert Metrics section exists and displays correct counts
    assert "Playable Fret Candidates" in html_content
    assert "Candidates Outside Staff" in html_content
    assert "1" in html_content  # playable candidate count

    # 3. Assert Taxonomy/Warning table is scannable and present
    assert "warning-table" in html_content
    assert "pdf_bar_box_one_boundary_rejected" in html_content
    assert "One accepted and one rejected boundary detected" in html_content

    # 4. Assert compact thumbnail grid with overlay image is present
    assert "thumbnail-grid" in html_content
    assert "thumbnail-card" in html_content
    assert "overlays/page-001-grouping.png" in html_content
    assert "PAGE 1 OVERLAY" in html_content

    # 5. Assert private safety: no private content leaks
    assert "derek" not in html_content.lower()
    assert "trucks" not in html_content.lower()
    assert "caged" not in html_content.lower()
