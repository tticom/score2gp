from __future__ import annotations

import json
from pathlib import Path

from score2gp.build_ir import build_ir_from_files
from score2gp.ir import validate_score_ir_file
from score2gp.pdf import extract_tab, inspect_pdf
from score2gp.tabraw import TabRaw

GENERATED_PDF = Path("tests/fixtures/pdf/generated_tiny_tab.pdf")
GENERATED_MUSICXML = Path("tests/fixtures/musicxml/generated_tiny_tab.musicxml")


def test_pdf_inspection_reports_missing_pymupdf_or_empty_pdf(tmp_path) -> None:
    pdf = tmp_path / "not-really.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    out = tmp_path / "inspect"
    try:
        summary = inspect_pdf(pdf, out)
    except Exception as exc:  # PyMuPDF may reject the intentionally tiny file.
        assert "document" in str(exc).lower() or "pdf" in str(exc).lower()
        return

    assert (out / "inspect_pdf.json").exists()
    assert json.loads((out / "inspect_pdf.json").read_text())["path"] == str(pdf)
    assert "warnings" in summary


def test_generated_pdf_extract_tab_emits_stable_spatial_tabraw(tmp_path) -> None:
    assert GENERATED_PDF.exists()
    first_path = tmp_path / "generated_tiny_tab.tabraw.json"
    second_path = tmp_path / "generated_tiny_tab_again.tabraw.json"

    first = TabRaw.model_validate(extract_tab(GENERATED_PDF, first_path))
    second = TabRaw.model_validate(extract_tab(GENERATED_PDF, second_path))

    assert first_path.exists()
    assert first.inspection_kind == "born-digital"
    assert [candidate.id for candidate in first.candidates] == [candidate.id for candidate in second.candidates]
    assert [candidate.raw_text for candidate in first.candidates] == [candidate.raw_text for candidate in second.candidates]

    fret_candidates = [candidate for candidate in first.candidates if candidate.kind == "fret"]
    assert [candidate.parsed_fret for candidate in fret_candidates] == [0, 12, 3, 1, 3, 2]
    assert 12 in [candidate.parsed_fret for candidate in fret_candidates]
    assert all(candidate.page_index == 1 for candidate in fret_candidates)
    assert all(candidate.bbox is not None for candidate in fret_candidates)
    assert all(candidate.x is not None and candidate.y is not None for candidate in fret_candidates)
    assert all(candidate.confidence >= 0.8 for candidate in fret_candidates)
    assert all(candidate.system_index == 1 for candidate in fret_candidates)
    assert all(candidate.staff_index == 1 for candidate in fret_candidates)
    assert all(candidate.string is not None for candidate in fret_candidates)
    assert {candidate.bar_index for candidate in fret_candidates} == {1, 2}


def test_generated_pdf_extracted_tabraw_feeds_build_ir_with_diagnostics(tmp_path) -> None:
    tabraw_path = tmp_path / "generated_tiny_tab.tabraw.json"
    ir_path = tmp_path / "generated_tiny_tab.ir.json"
    diagnostics_path = tmp_path / "generated_tiny_tab.diagnostics.json"

    extract_tab(GENERATED_PDF, tabraw_path)
    score = build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path, diagnostics_path)
    validated, errors = validate_score_ir_file(ir_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))

    assert errors == []
    assert validated is not None
    assert score.metadata.title == "Generated Tiny Tab"
    assert len(score.bars) == 2
    assert sum(len(bar.events) for bar in score.bars) == 8
    assert [event.notes[0].fret for event in score.bars[0].events if event.notes] == [0, 1, 12]
    assert [event.notes[0].fret for event in score.bars[1].events if event.notes] == [2, 3, 3]

    assert diagnostics["tabraw_candidates_loaded"] == 8
    assert diagnostics["tabraw_fret_candidate_count"] == 6
    assert diagnostics["tabraw_non_fret_candidate_count"] == 2
    assert diagnostics["tabraw_candidates_with_bbox"] == 8
    assert diagnostics["tabraw_candidates_with_x"] == 8
    assert diagnostics["tabraw_candidates_with_string"] == 6
    assert diagnostics["tabraw_candidates_with_bar"] == 6
    assert diagnostics["matched_candidate_count"] == 6
    assert diagnostics["unmatched_musicxml_event_count"] == 0
    assert diagnostics["unmatched_tabraw_candidate_count"] == 0
    assert "one or more TabRaw candidates have low confidence" in diagnostics["extraction_quality_flags"]

    warning_codes = [warning.code for warning in score.warnings]
    assert "tabraw-chord-symbol-not-aligned" in warning_codes
    assert "tabraw-technique-text-not-aligned" in warning_codes
