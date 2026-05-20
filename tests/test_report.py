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
    assert report["playable_fret_candidate_count"] == 1
    assert "missing_pdf_grouping" in html
    assert "Extraction succeeded, but grouping failed" in html
    assert "ScoreIR was not written" in html
