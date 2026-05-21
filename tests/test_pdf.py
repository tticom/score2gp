from __future__ import annotations

import json
from pathlib import Path

import pytest

from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_files
from score2gp.ir import validate_score_ir_file
from score2gp.pdf import extract_tab, inspect_pdf
from score2gp.tabraw import TabRaw

GENERATED_PDF = Path("tests/fixtures/pdf/generated_tiny_tab.pdf")
GENERATED_MUSICXML = Path("tests/fixtures/musicxml/generated_tiny_tab.musicxml")
SCORELIKE_PDF = Path("tests/fixtures/pdf/generated_scorelike_tab.pdf")
SCORELIKE_MUSICXML = Path("tests/fixtures/musicxml/generated_scorelike_tab.musicxml")
UNEVEN_PDF = Path("tests/fixtures/pdf/generated_uneven_spacing_tab.pdf")
UNEVEN_MUSICXML = Path("tests/fixtures/musicxml/generated_uneven_spacing_tab.musicxml")
UNSTRUCTURED_PDF = Path("tests/fixtures/pdf/generated_unstructured_tab_text.pdf")
PARTIAL_MISSING_BARLINES_PDF = Path("tests/fixtures/pdf/generated_partial_missing_barlines_tab.pdf")
PARTIAL_INCOMPLETE_STAFF_PDF = Path("tests/fixtures/pdf/generated_partial_incomplete_staff_tab.pdf")
PARTIAL_AMBIGUOUS_STRING_PDF = Path("tests/fixtures/pdf/generated_partial_ambiguous_string_tab.pdf")
PARTIAL_AMBIGUOUS_BAR_PDF = Path("tests/fixtures/pdf/generated_partial_ambiguous_bar_tab.pdf")
ASCII_SIMPLE_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_simple.pdf")
ASCII_TECHNIQUES_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_techniques.pdf")
ASCII_MALFORMED_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_malformed.pdf")


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
    assert all(candidate.raw.get("grouping_version") == "pdf-grouping.v0.1" for candidate in fret_candidates)
    assert all(len(candidate.raw.get("tab_line_ys", [])) == 6 for candidate in fret_candidates)
    assert all(len(candidate.raw.get("bar_boxes", [])) == 2 for candidate in fret_candidates)
    assert (first_path.parent / "grouping-diagnostics.html").exists()
    assert sorted((first_path.parent / "overlays").glob("*-grouping.png"))


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
    assert diagnostics["tabraw_candidates_with_bar"] == 8
    assert diagnostics["matched_candidate_count"] == 6
    assert diagnostics["unmatched_musicxml_event_count"] == 0
    assert diagnostics["unmatched_tabraw_candidate_count"] == 0
    assert diagnostics["ignored_non_playable_candidate_count"] == 2
    assert "one or more TabRaw candidates have low confidence" in diagnostics["extraction_quality_flags"]

    warning_codes = [warning.code for warning in score.warnings]
    assert "tabraw-chord-symbol-not-aligned" in warning_codes
    assert "tabraw-technique-text-not-aligned" in warning_codes


def test_scorelike_generated_pdf_extract_tab_groups_multiple_systems_and_preserves_non_frets(tmp_path) -> None:
    assert SCORELIKE_PDF.exists()
    first_path = tmp_path / "generated_scorelike_tab.tabraw.json"
    second_path = tmp_path / "generated_scorelike_tab_again.tabraw.json"

    first = TabRaw.model_validate(extract_tab(SCORELIKE_PDF, first_path))
    second = TabRaw.model_validate(extract_tab(SCORELIKE_PDF, second_path))

    assert first.inspection_kind == "born-digital"
    report_path = first_path.parent / "grouping-diagnostics.html"
    overlay_paths = sorted((first_path.parent / "overlays").glob("*-grouping.png"))
    report_html = report_path.read_text(encoding="utf-8")
    assert report_path.exists()
    assert overlay_paths
    assert "grouped" in report_html
    assert "Tab staff bbox" in report_html
    assert "bar boxes" in report_html
    assert [candidate.id for candidate in first.candidates] == [candidate.id for candidate in second.candidates]
    assert [candidate.raw_text for candidate in first.candidates] == [candidate.raw_text for candidate in second.candidates]

    fret_candidates = [candidate for candidate in first.candidates if candidate.kind == "fret"]
    chord_candidates = [candidate for candidate in first.candidates if candidate.kind == "chord-symbol"]
    technique_candidates = [candidate for candidate in first.candidates if candidate.kind == "technique-text"]
    text_candidates = [candidate for candidate in first.candidates if candidate.kind == "candidate-text"]

    assert len(first.candidates) == 22
    assert len(fret_candidates) == 11
    assert len(chord_candidates) == 4
    assert len(technique_candidates) == 5
    assert len(text_candidates) == 2
    assert {candidate.system_index for candidate in fret_candidates} == {1, 2}
    assert {candidate.bar_index for candidate in fret_candidates} == {1, 2, 3, 4}
    assert 10 in [candidate.parsed_fret for candidate in fret_candidates]
    assert 12 in [candidate.parsed_fret for candidate in fret_candidates]
    assert {"Am", "G", "D7"} <= {candidate.raw_text for candidate in chord_candidates}
    assert {"h", "slide", "PM", "let", "ring"} <= {candidate.raw_text for candidate in technique_candidates}
    assert {"cue", "note"} == {candidate.raw_text for candidate in text_candidates}

    assert all(candidate.page_index == 1 for candidate in fret_candidates)
    assert all(candidate.bbox is not None for candidate in fret_candidates)
    assert all(candidate.x is not None and candidate.y is not None for candidate in fret_candidates)
    assert all(candidate.confidence >= 0.8 for candidate in fret_candidates)
    assert all(candidate.staff_index == 1 for candidate in fret_candidates)
    assert all(candidate.string is not None for candidate in fret_candidates)
    assert all(candidate.raw.get("grouping_version") == "pdf-grouping.v0.1" for candidate in fret_candidates)
    assert all(len(candidate.raw.get("tab_line_ys", [])) == 6 for candidate in fret_candidates)
    assert all(len(candidate.raw.get("bar_boxes", [])) == 2 for candidate in fret_candidates)
    assert all(candidate.raw.get("system_relation") == "on-tab-line" for candidate in fret_candidates)
    assert all(candidate.parsed_fret is None for candidate in chord_candidates + technique_candidates + text_candidates)


def test_scorelike_generated_pdf_extracted_tabraw_feeds_build_ir_with_system_diagnostics(tmp_path) -> None:
    tabraw_path = tmp_path / "generated_scorelike_tab.tabraw.json"
    ir_path = tmp_path / "generated_scorelike_tab.ir.json"
    diagnostics_path = tmp_path / "generated_scorelike_tab.diagnostics.json"

    extract_tab(SCORELIKE_PDF, tabraw_path)
    score = build_ir_from_files(SCORELIKE_MUSICXML, tabraw_path, ir_path, diagnostics_path)
    validated, errors = validate_score_ir_file(ir_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))

    assert errors == []
    assert validated is not None
    assert score.metadata.title == "Generated Scorelike Tab"
    assert len(score.bars) == 4
    assert sum(len(bar.events) for bar in score.bars) == 12

    assert [[note.fret for note in event.notes] for event in score.bars[0].events if event.notes] == [[0, 1], [2]]
    assert [[note.fret for note in event.notes] for event in score.bars[1].events if event.notes] == [[3], [5], [10]]
    assert [[note.fret for note in event.notes] for event in score.bars[2].events if event.notes] == [[2], [0]]
    assert [[note.fret for note in event.notes] for event in score.bars[3].events if event.notes] == [[3, 4], [12]]

    assert diagnostics["tabraw_candidates_loaded"] == 22
    assert diagnostics["tabraw_fret_candidate_count"] == 11
    assert diagnostics["tabraw_non_fret_candidate_count"] == 11
    assert diagnostics["tabraw_chord_symbol_candidate_count"] == 4
    assert diagnostics["tabraw_technique_text_candidate_count"] == 5
    assert diagnostics["tabraw_unknown_candidate_count"] == 2
    assert diagnostics["tabraw_candidates_with_bbox"] == 22
    assert diagnostics["tabraw_candidates_with_x"] == 22
    assert diagnostics["tabraw_candidates_with_y"] == 22
    assert diagnostics["tabraw_candidates_with_system"] == 22
    assert diagnostics["tabraw_candidates_with_string"] == 11
    assert diagnostics["tabraw_candidates_with_bar"] == 22
    assert diagnostics["matched_candidate_count"] == 11
    assert diagnostics["unmatched_musicxml_event_count"] == 0
    assert diagnostics["unmatched_tabraw_candidate_count"] == 0
    assert diagnostics["ignored_non_playable_candidate_count"] == 11
    assert "multiple inferred tab systems present" in diagnostics["extraction_quality_flags"]

    assert len(diagnostics["per_system"]) == 2
    assert [system["matched_playable_candidate_count"] for system in diagnostics["per_system"]] == [6, 5]
    assert [system["ignored_non_playable_candidate_count"] for system in diagnostics["per_system"]] == [5, 6]
    assert len(diagnostics["per_bar"]) == 4
    assert diagnostics["per_bar"][0]["matched_candidate_count"] == 3
    assert diagnostics["per_bar"][3]["matched_candidate_count"] == 3
    assert "repeated x-position candidates treated as a chord or stacked notes" in diagnostics["per_bar"][0]["ambiguity_flags"]
    assert "repeated x-position candidates treated as a chord or stacked notes" in diagnostics["per_bar"][3]["ambiguity_flags"]
    assert all(bar["quality"] == "good" for bar in diagnostics["per_bar"])
    assert diagnostics["per_bar"][0]["has_chord_stack"] is True
    assert diagnostics["per_bar"][0]["playable_candidate_onset_group_count"] == 2
    assert diagnostics["per_bar"][0]["musicxml_pitched_onset_group_count"] == 2
    assert diagnostics["per_bar"][1]["playable_candidate_onset_group_count"] == 3
    assert diagnostics["per_bar"][1]["musicxml_pitched_onset_group_count"] == 3
    assert diagnostics["per_bar"][1]["max_relative_error"] < 0.05
    assert diagnostics["per_bar"][0]["candidate_x_groups"][0]["candidate_count"] == 2
    assert diagnostics["per_bar"][0]["candidate_x_groups"][0]["is_chord_stack"] is True
    assert all("pdf-p001-c0001" not in group["candidate_ids"] for group in diagnostics["per_bar"][0]["candidate_x_groups"])

    warning_codes = [warning.code for warning in score.warnings]
    assert "tabraw-chord-symbol-not-aligned" in warning_codes
    assert "tabraw-technique-text-not-aligned" in warning_codes
    assert "tabraw-candidate-text-not-aligned" in warning_codes


def test_uneven_generated_pdf_reports_x_to_onset_quality_without_breaking_scoreir(tmp_path) -> None:
    assert UNEVEN_PDF.exists()
    first_path = tmp_path / "generated_uneven_spacing_tab.tabraw.json"
    second_path = tmp_path / "generated_uneven_spacing_tab_again.tabraw.json"
    ir_path = tmp_path / "generated_uneven_spacing_tab.ir.json"
    diagnostics_path = tmp_path / "generated_uneven_spacing_tab.diagnostics.json"

    first = TabRaw.model_validate(extract_tab(UNEVEN_PDF, first_path))
    second = TabRaw.model_validate(extract_tab(UNEVEN_PDF, second_path))

    assert [candidate.id for candidate in first.candidates] == [candidate.id for candidate in second.candidates]
    assert [candidate.raw_text for candidate in first.candidates] == [candidate.raw_text for candidate in second.candidates]

    fret_candidates = [candidate for candidate in first.candidates if candidate.kind == "fret"]
    chord_candidates = [candidate for candidate in first.candidates if candidate.kind == "chord-symbol"]
    technique_candidates = [candidate for candidate in first.candidates if candidate.kind == "technique-text"]

    assert len(first.candidates) == 12
    assert len(fret_candidates) == 8
    assert len(chord_candidates) == 2
    assert len(technique_candidates) == 2
    assert {10, 12} <= {candidate.parsed_fret for candidate in fret_candidates}
    assert all(candidate.bbox is not None for candidate in fret_candidates)
    assert all(candidate.x is not None and candidate.y is not None for candidate in fret_candidates)
    assert all(candidate.system_index == 1 for candidate in fret_candidates)
    assert {candidate.bar_index for candidate in fret_candidates} == {1, 2}
    assert (first_path.parent / "grouping-diagnostics.html").exists()
    assert sorted((first_path.parent / "overlays").glob("*-grouping.png"))

    score = build_ir_from_files(UNEVEN_MUSICXML, first_path, ir_path, diagnostics_path)
    validated, errors = validate_score_ir_file(ir_path)
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))

    assert errors == []
    assert validated is not None
    assert score.metadata.title == "Generated Uneven Spacing Tab"
    assert len(score.bars) == 2
    assert sum(len(bar.events) for bar in score.bars) == 8
    assert diagnostics["matched_candidate_count"] == 8
    assert diagnostics["ignored_non_playable_candidate_count"] == 4
    assert diagnostics["unmatched_tabraw_candidate_count"] == 0
    assert diagnostics["tabraw_chord_symbol_candidate_count"] == 2
    assert diagnostics["tabraw_technique_text_candidate_count"] == 2

    first_bar = diagnostics["per_bar"][0]
    second_bar = diagnostics["per_bar"][1]
    assert first_bar["playable_candidate_onset_group_count"] == 3
    assert first_bar["musicxml_pitched_onset_group_count"] == 3
    assert first_bar["has_chord_stack"] is True
    assert first_bar["candidate_x_groups"][0]["candidate_count"] == 2
    assert first_bar["candidate_x_groups"][0]["is_chord_stack"] is True
    assert first_bar["quality"] == "good"
    assert first_bar["max_relative_error"] == 0.0

    assert second_bar["playable_candidate_onset_group_count"] == 4
    assert second_bar["musicxml_pitched_onset_group_count"] == 4
    assert second_bar["has_chord_stack"] is False
    assert second_bar["ambiguous_x_group_count"] == 1
    assert second_bar["quality"] in {"warning", "poor"}
    assert second_bar["max_relative_error"] > 0.3
    assert "one or more playable x groups are too close to distinguish confidently" in second_bar["x_to_onset_warnings"]
    assert "visual x positions drift strongly from MusicXML onset spacing" in second_bar["x_to_onset_warnings"]
    assert "one or more bars have poor x-to-onset quality" in diagnostics["extraction_quality_flags"]


def test_unstructured_pdf_preserves_candidates_but_reports_missing_grouping(tmp_path) -> None:
    assert UNSTRUCTURED_PDF.exists()
    first_path = tmp_path / "generated_unstructured_tab_text.tabraw.json"
    second_path = tmp_path / "generated_unstructured_tab_text_again.tabraw.json"

    first = TabRaw.model_validate(extract_tab(UNSTRUCTURED_PDF, first_path))
    second = TabRaw.model_validate(extract_tab(UNSTRUCTURED_PDF, second_path))

    assert first.inspection_kind == "born-digital"
    assert [candidate.id for candidate in first.candidates] == [candidate.id for candidate in second.candidates]
    assert [candidate.raw_text for candidate in first.candidates] == [candidate.raw_text for candidate in second.candidates]

    fret_candidates = [candidate for candidate in first.candidates if candidate.kind == "fret"]
    non_fret_candidates = [candidate for candidate in first.candidates if candidate.kind != "fret"]

    assert len(first.candidates) == 8
    assert [candidate.parsed_fret for candidate in fret_candidates] == [0, 12, 3, 7, 5, 10]
    assert {candidate.raw_text for candidate in non_fret_candidates} == {"Am", "slide"}
    assert all(candidate.bbox is not None for candidate in first.candidates)
    assert all(candidate.x is not None and candidate.y is not None for candidate in first.candidates)
    assert all(candidate.system_index is None for candidate in first.candidates)
    assert all(candidate.bar_index is None for candidate in first.candidates)
    assert all(candidate.string is None for candidate in fret_candidates)
    assert any(warning["code"] == "pdf-tab-system-not-detected" for warning in first.warnings)
    grouping_warnings = [warning for warning in first.warnings if warning["code"] == "missing_pdf_grouping"]
    assert len(grouping_warnings) == 1
    assert grouping_warnings[0]["grouping_status"] == "missing_pdf_grouping"
    assert set(grouping_warnings[0]["missing_grouping_dimensions"]) == {"system", "bar", "string"}

    warnings_path = first_path.parent / "warnings.json"
    report_path = first_path.parent / "grouping-diagnostics.html"
    overlay_paths = sorted((first_path.parent / "overlays").glob("*-grouping.png"))
    report_html = report_path.read_text(encoding="utf-8")

    assert warnings_path.exists()
    assert report_path.exists()
    assert overlay_paths
    assert "missing_pdf_grouping" in report_html
    assert "Candidate count" in report_html
    assert "Grouping status" in report_html
    assert "ScoreIR was not written" in report_html
    assert "Alignment/build-ir was not attempted" in report_html


def test_partial_pdf_missing_barlines_reports_partial_grouping(tmp_path) -> None:
    assert PARTIAL_MISSING_BARLINES_PDF.exists()
    tabraw_path = tmp_path / "generated_partial_missing_barlines_tab.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(PARTIAL_MISSING_BARLINES_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    report_html = (tabraw_path.parent / "grouping-diagnostics.html").read_text(encoding="utf-8")

    assert len(fret_candidates) == 4
    assert {"partial_pdf_grouping", "missing_pdf_barlines", "missing_pdf_grouping"} <= warning_codes
    assert all(candidate.system_index == 1 for candidate in fret_candidates)
    assert all(candidate.string is not None for candidate in fret_candidates)
    assert all(candidate.bar_index is None for candidate in fret_candidates)
    assert all(candidate.confidence < 0.8 for candidate in fret_candidates)
    assert "partial" in report_html
    assert "missing_pdf_barlines" in report_html
    assert sorted((tabraw_path.parent / "overlays").glob("*-grouping.png"))


def test_partial_pdf_incomplete_staff_reports_specific_warning(tmp_path) -> None:
    assert PARTIAL_INCOMPLETE_STAFF_PDF.exists()
    tabraw_path = tmp_path / "generated_partial_incomplete_staff_tab.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(PARTIAL_INCOMPLETE_STAFF_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    report_html = (tabraw_path.parent / "grouping-diagnostics.html").read_text(encoding="utf-8")

    assert len(fret_candidates) == 4
    assert {"partial_pdf_grouping", "incomplete_tab_staff"} <= warning_codes
    assert "missing_pdf_grouping" not in warning_codes
    assert all(candidate.system_index == 1 for candidate in fret_candidates)
    assert all(candidate.bar_index is not None for candidate in fret_candidates)
    assert all(candidate.string is not None for candidate in fret_candidates)
    assert all(len(candidate.raw.get("tab_line_ys", [])) == 5 for candidate in fret_candidates)
    assert all(candidate.confidence < 0.8 for candidate in fret_candidates)
    assert "partial" in report_html
    assert "incomplete_tab_staff" in report_html
    assert sorted((tabraw_path.parent / "overlays").glob("*-grouping.png"))


def test_partial_pdf_ambiguous_string_assignment_is_not_high_confidence(tmp_path) -> None:
    assert PARTIAL_AMBIGUOUS_STRING_PDF.exists()
    tabraw_path = tmp_path / "generated_partial_ambiguous_string_tab.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(PARTIAL_AMBIGUOUS_STRING_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    ambiguous = [candidate for candidate in fret_candidates if candidate.raw.get("assignment_warnings")]
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    report_html = (tabraw_path.parent / "grouping-diagnostics.html").read_text(encoding="utf-8")

    assert {"partial_pdf_grouping", "ambiguous_string_assignment", "missing_pdf_grouping"} <= warning_codes
    assert len(ambiguous) == 1
    assert ambiguous[0].string is None
    assert ambiguous[0].confidence <= 0.65
    assert "ambiguous_string_assignment" in report_html
    assert sorted((tabraw_path.parent / "overlays").glob("*-grouping.png"))


def test_partial_pdf_ambiguous_bar_assignment_is_not_high_confidence(tmp_path) -> None:
    assert PARTIAL_AMBIGUOUS_BAR_PDF.exists()
    tabraw_path = tmp_path / "generated_partial_ambiguous_bar_tab.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(PARTIAL_AMBIGUOUS_BAR_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    ambiguous = [candidate for candidate in fret_candidates if candidate.raw.get("assignment_warnings")]
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    report_html = (tabraw_path.parent / "grouping-diagnostics.html").read_text(encoding="utf-8")

    assert {"partial_pdf_grouping", "ambiguous_bar_assignment", "missing_pdf_grouping"} <= warning_codes
    assert len(ambiguous) == 1
    assert ambiguous[0].bar_index is None
    assert ambiguous[0].confidence <= 0.65
    assert "ambiguous_bar_assignment" in report_html
    assert sorted((tabraw_path.parent / "overlays").glob("*-grouping.png"))


def test_build_ir_refuses_unstructured_pdf_tabraw_before_scoreir_output(tmp_path) -> None:
    tabraw_path = tmp_path / "generated_unstructured_tab_text.tabraw.json"
    ir_path = tmp_path / "generated_unstructured_tab_text.ir.json"

    extract_tab(UNSTRUCTURED_PDF, tabraw_path)

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert (tabraw_path.parent / "grouping-diagnostics.html").exists()
    assert raised.value.category == "missing_pdf_grouping"
    payload = raised.value.to_diagnostics_payload()
    assert payload["stage"] == "tabraw-import"
    assert payload["details"]["playable_candidate_count"] == 6
    assert set(payload["details"]["missing_grouping_dimensions"]) == {"system", "bar", "string"}


@pytest.mark.parametrize(
    ("pdf_path", "expected_warning"),
    [
        (PARTIAL_MISSING_BARLINES_PDF, "missing_pdf_barlines"),
        (PARTIAL_INCOMPLETE_STAFF_PDF, "incomplete_tab_staff"),
        (PARTIAL_AMBIGUOUS_STRING_PDF, "ambiguous_string_assignment"),
        (PARTIAL_AMBIGUOUS_BAR_PDF, "ambiguous_bar_assignment"),
    ],
)
def test_build_ir_refuses_public_partial_grouping_fixtures(tmp_path, pdf_path: Path, expected_warning: str) -> None:
    tabraw_path = tmp_path / f"{pdf_path.stem}.tabraw.json"
    ir_path = tmp_path / f"{pdf_path.stem}.ir.json"

    extract_tab(pdf_path, tabraw_path)

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert raised.value.category == "partial_pdf_grouping"
    payload = raised.value.to_diagnostics_payload()
    assert payload["details"]["grouping_status"] == "partial"
    assert expected_warning in payload["details"]["warning_codes"]


def test_ascii_tab_pdf_detects_six_row_block_and_fret_candidates(tmp_path) -> None:
    assert ASCII_SIMPLE_PDF.exists()
    tabraw_path = tmp_path / "generated_ascii_tab_simple.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(ASCII_SIMPLE_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    report_html = (tabraw_path.parent / "grouping-diagnostics.html").read_text(encoding="utf-8")

    assert len(fret_candidates) == 6
    assert [candidate.parsed_fret for candidate in fret_candidates] == [0, 3, 1, 3, 0, 2]
    assert {candidate.string for candidate in fret_candidates} == {1, 2, 3, 4}
    assert all(candidate.system_index == 1 for candidate in fret_candidates)
    assert all(candidate.staff_index == 1 for candidate in fret_candidates)
    assert all(candidate.bar_index is None for candidate in fret_candidates)
    assert all(candidate.raw.get("parser_version") == "ascii-tab.v0.1" for candidate in fret_candidates)
    assert all(candidate.raw.get("grouping_status") == "ascii_grouped" for candidate in fret_candidates)
    assert all(candidate.raw.get("row_label") in {"e", "B", "G", "D"} for candidate in fret_candidates)
    assert all(candidate.raw.get("character_span") for candidate in fret_candidates)
    assert {"ascii_tab_detected", "ascii_tab_timing_unavailable", "missing_pdf_grouping"} <= warning_codes
    assert "ASCII tab rows were grouped" in report_html
    assert "ascii_grouped" in report_html
    assert sorted((tabraw_path.parent / "overlays").glob("*-grouping.png"))


def test_ascii_tab_pdf_preserves_inline_technique_markers_and_legend_text(tmp_path) -> None:
    assert ASCII_TECHNIQUES_PDF.exists()
    tabraw_path = tmp_path / "generated_ascii_tab_techniques.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(ASCII_TECHNIQUES_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    technique_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "technique-text"]
    ascii_techniques = [
        candidate
        for candidate in technique_candidates
        if candidate.raw.get("parser_version") == "ascii-tab.v0.1"
    ]
    legend_techniques = [
        candidate
        for candidate in technique_candidates
        if candidate.raw.get("parser_version") != "ascii-tab.v0.1"
    ]

    assert len(fret_candidates) == 12
    assert {3, 5, 7, 2, 4, 8, 9} <= {candidate.parsed_fret for candidate in fret_candidates}
    assert {"/", "\\", "h", "p", "b", "r", "v"} <= {candidate.raw_text for candidate in ascii_techniques}
    assert all(candidate.parsed_fret is None for candidate in technique_candidates)
    assert all(candidate.string is None for candidate in ascii_techniques)
    assert all(candidate.raw.get("technique_context") == "ascii-inline-marker" for candidate in ascii_techniques)
    assert legend_techniques
    assert all(candidate.kind != "fret" for candidate in legend_techniques)
    assert any(warning["code"] == "ascii_tab_timing_unavailable" for warning in tabraw.warnings)


def test_malformed_ascii_tab_pdf_reports_partial_grouping(tmp_path) -> None:
    assert ASCII_MALFORMED_PDF.exists()
    tabraw_path = tmp_path / "generated_ascii_tab_malformed.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(ASCII_MALFORMED_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    report_html = (tabraw_path.parent / "grouping-diagnostics.html").read_text(encoding="utf-8")

    assert len(fret_candidates) == 6
    assert all(candidate.raw.get("parser_version") == "ascii-tab.v0.1" for candidate in fret_candidates)
    assert all(candidate.raw.get("grouping_status") == "partial_ascii_tab_grouping" for candidate in fret_candidates)
    assert all(candidate.string is None for candidate in fret_candidates)
    assert {"ascii_tab_detected", "partial_ascii_tab_grouping", "missing_pdf_grouping"} <= warning_codes
    assert "partial_ascii" in report_html
    assert "ASCII grouping is partial" in report_html
    assert sorted((tabraw_path.parent / "overlays").glob("*-grouping.png"))


def test_build_ir_refuses_ascii_tab_without_timing_alignment(tmp_path) -> None:
    tabraw_path = tmp_path / "generated_ascii_tab_simple.tabraw.json"
    ir_path = tmp_path / "generated_ascii_tab_simple.ir.json"

    extract_tab(ASCII_SIMPLE_PDF, tabraw_path)

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert raised.value.category == "ascii_tab_timing_unavailable"
    payload = raised.value.to_diagnostics_payload()
    assert payload["details"]["grouping_status"] == "ascii_grouped"
    assert "ascii_tab_timing_unavailable" in payload["details"]["warning_codes"]


def test_build_ir_refuses_partial_ascii_tab_grouping(tmp_path) -> None:
    tabraw_path = tmp_path / "generated_ascii_tab_malformed.tabraw.json"
    ir_path = tmp_path / "generated_ascii_tab_malformed.ir.json"

    extract_tab(ASCII_MALFORMED_PDF, tabraw_path)

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert raised.value.category == "partial_ascii_tab_grouping"
    payload = raised.value.to_diagnostics_payload()
    assert payload["details"]["grouping_status"] == "partial_ascii_tab_grouping"
    assert "partial_ascii_tab_grouping" in payload["details"]["warning_codes"]
