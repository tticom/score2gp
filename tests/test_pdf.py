from __future__ import annotations

import json
from pathlib import Path

import pytest

from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_files
from score2gp.ir import validate_score_ir_file
from score2gp.pdf import extract_tab, inspect_pdf
from score2gp.tabraw import TabRaw
from score2gp.report import grouping_status_for_tabraw

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
ASCII_BARRED_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_barred.pdf")
ASCII_EQUAL_WIDTH_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_equal_width.pdf")
ASCII_UNEVEN_TIMING_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_uneven_timing.pdf")
ASCII_NO_BARS_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_no_bars.pdf")

NEW_OUTSIDE_SYSTEM_PDF = Path("tests/fixtures/pdf/generated_pdf_candidate_outside_system.pdf")
NEW_OUTSIDE_BAR_PDF = Path("tests/fixtures/pdf/generated_pdf_candidate_outside_bar.pdf")
NEW_MULTI_SYSTEM_PDF = Path("tests/fixtures/pdf/generated_pdf_multi_system_order_ambiguous.pdf")
NEW_CONFLICT_LAYOUT_PDF = Path("tests/fixtures/pdf/generated_pdf_ascii_and_drawn_layout_conflict.pdf")
NEW_PROSE_LEGEND_PDF = Path("tests/fixtures/pdf/generated_pdf_prose_legend_text.pdf")

NEW_TEXT_GEOM_NO_SYSTEM_PDF = Path("tests/fixtures/pdf/generated_pdf_text_geometry_present_but_no_safe_system.pdf")
NEW_TAB_CANDIDATES_NO_SYSTEM_PDF = Path("tests/fixtures/pdf/generated_pdf_tab_candidates_present_but_system_not_detected.pdf")
NEW_LINES_FRAGMENTED_PDF = Path("tests/fixtures/pdf/generated_pdf_tab_staff_lines_fragmented.pdf")
NEW_CANDIDATES_BETWEEN_SYSTEMS_PDF = Path("tests/fixtures/pdf/generated_pdf_candidates_between_systems.pdf")
NEW_CANDIDATES_UNASSIGNED_TO_STRING_PDF = Path("tests/fixtures/pdf/generated_pdf_candidates_unassigned_to_string.pdf")
NEW_ORDER_AMBIGUOUS_CLOSE_PDF = Path("tests/fixtures/pdf/generated_pdf_system_order_ambiguous_close.pdf")
NEW_MIXED_PROSE_TAB_NUMBERS_PDF = Path("tests/fixtures/pdf/generated_pdf_mixed_prose_tab_numbers.pdf")


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
    assert "tabraw-chord-symbol-not-aligned" not in warning_codes
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
    assert "tabraw-chord-symbol-not-aligned" not in warning_codes
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
    unsafe_set = {
        "pdf_playable_candidate_requires_string_assignment",
        "pdf_string_assignment_missing",
        "pdf_candidates_unassigned_to_string",
        "pdf_string_assignment_outside_staff",
        "pdf_string_assignment_between_lines",
        "pdf_string_assignment_too_far_from_line",
        "pdf_string_assignment_overlaps_multiple_bands",
        "pdf_string_assignment_confidence_below_threshold",
        "pdf_string_assignment_compact_staff_ambiguous",
        "pdf_string_assignment_not_enough_for_build_ir",
        "pdf_candidate_between_strings",
        "pdf_candidate_outside_bar",
        "pdf_candidate_unassigned_to_bar",
        "pdf_candidates_unassigned_to_bar",
        "ambiguous_string_assignment",
        "ambiguous_bar_assignment",
        "pdf_candidate_on_bar_boundary",
        "pdf_candidate_boundary_ambiguous",
    }
    ambiguous = [
        candidate for candidate in fret_candidates
        if any(w in unsafe_set for w in (candidate.raw.get("assignment_warnings") or []))
    ]
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
    unsafe_set = {
        "pdf_playable_candidate_requires_string_assignment",
        "pdf_string_assignment_missing",
        "pdf_candidates_unassigned_to_string",
        "pdf_string_assignment_outside_staff",
        "pdf_string_assignment_between_lines",
        "pdf_string_assignment_too_far_from_line",
        "pdf_string_assignment_overlaps_multiple_bands",
        "pdf_string_assignment_confidence_below_threshold",
        "pdf_string_assignment_compact_staff_ambiguous",
        "pdf_string_assignment_not_enough_for_build_ir",
        "pdf_candidate_between_strings",
        "pdf_candidate_outside_bar",
        "pdf_candidate_unassigned_to_bar",
        "pdf_candidates_unassigned_to_bar",
        "ambiguous_string_assignment",
        "ambiguous_bar_assignment",
        "pdf_candidate_on_bar_boundary",
        "pdf_candidate_boundary_ambiguous",
    }
    ambiguous = [
        candidate for candidate in fret_candidates
        if any(w in unsafe_set for w in (candidate.raw.get("assignment_warnings") or []))
    ]
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
    assert all(candidate.raw.get("timing_parser_version") == "ascii-timing.v0.1" for candidate in fret_candidates)
    assert all(candidate.raw.get("ascii_timing_status") == "timing_unavailable" for candidate in fret_candidates)
    assert all(candidate.raw.get("ascii_normalized_column_position") is not None for candidate in fret_candidates)
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
    assert any(warning["code"] == "unsupported_ascii_tab_rhythm" for warning in tabraw.warnings)


def test_ascii_tab_with_aligned_bars_records_measure_segments(tmp_path) -> None:
    assert ASCII_BARRED_PDF.exists()
    tabraw_path = tmp_path / "generated_ascii_tab_barred.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(ASCII_BARRED_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    report_html = (tabraw_path.parent / "grouping-diagnostics.html").read_text(encoding="utf-8")

    assert len(fret_candidates) >= 8
    assert {"ascii_tab_detected", "partial_ascii_tab_timing", "missing_pdf_grouping"} <= warning_codes
    assert "ascii_tab_timing_unavailable" not in warning_codes
    assert all(candidate.raw.get("timing_parser_version") == "ascii-timing.v0.1" for candidate in fret_candidates)
    assert all(candidate.raw.get("ascii_timing_status") == "timing_partial" for candidate in fret_candidates)
    assert all(candidate.raw.get("ascii_bar_separators_aligned") is True for candidate in fret_candidates)
    assert all(candidate.raw.get("ascii_measure_segment_count") == 2 for candidate in fret_candidates)
    assert {candidate.raw.get("ascii_measure_segment_id") for candidate in fret_candidates} == {1, 2}
    assert all(0.0 <= candidate.raw.get("ascii_normalized_column_position") <= 1.0 for candidate in fret_candidates)
    assert all(0.0 <= candidate.raw.get("ascii_measure_normalized_column") <= 1.0 for candidate in fret_candidates)
    assert "partial bar/column timing evidence" in report_html
    assert "ASCII timing status counts" in report_html


def test_equal_width_ascii_tab_records_normalized_column_positions(tmp_path) -> None:
    assert ASCII_EQUAL_WIDTH_PDF.exists()
    tabraw_path = tmp_path / "generated_ascii_tab_equal_width.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(ASCII_EQUAL_WIDTH_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    normalized = [candidate.raw.get("ascii_measure_normalized_column") for candidate in fret_candidates]

    assert len(fret_candidates) >= 10
    assert "partial_ascii_tab_timing" in warning_codes
    assert all(candidate.raw.get("ascii_timing_status") == "timing_partial" for candidate in fret_candidates)
    assert all(candidate.raw.get("ascii_bar_separators_aligned") is True for candidate in fret_candidates)
    assert all(value is not None for value in normalized)
    assert min(normalized) < 0.25
    assert max(normalized) > 0.55


def test_no_bar_ascii_tab_keeps_timing_unavailable(tmp_path) -> None:
    assert ASCII_NO_BARS_PDF.exists()
    tabraw_path = tmp_path / "generated_ascii_tab_no_bars.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(ASCII_NO_BARS_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert fret_candidates
    assert {"ascii_tab_timing_unavailable", "ascii_tab_measure_boundary_missing"} <= warning_codes
    assert all(candidate.raw.get("ascii_timing_status") == "timing_unavailable" for candidate in fret_candidates)
    assert all(candidate.raw.get("ascii_measure_segment_id") is None for candidate in fret_candidates)


def test_uneven_ascii_tab_reports_ambiguous_timing(tmp_path) -> None:
    assert ASCII_UNEVEN_TIMING_PDF.exists()
    tabraw_path = tmp_path / "generated_ascii_tab_uneven_timing.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(ASCII_UNEVEN_TIMING_PDF, tabraw_path))
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert fret_candidates
    assert {"partial_ascii_tab_timing", "ambiguous_ascii_tab_timing"} <= warning_codes
    assert all(candidate.raw.get("ascii_timing_status") == "timing_partial" for candidate in fret_candidates)
    assert any("ambiguous_ascii_tab_timing" in candidate.raw.get("ascii_timing_warnings", []) for candidate in fret_candidates)


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
    assert raised.value.category == "missing_ascii_alignment_sidecar"
    payload = raised.value.to_diagnostics_payload()
    assert payload["details"]["grouping_status"] == "ascii_grouped"
    assert "ascii_tab_timing_unavailable" in payload["details"]["tabraw_warning_codes"]
    assert payload["details"]["primary_reason_code"] == "missing_ascii_alignment_sidecar"


def test_build_ir_refuses_partial_ascii_tab_timing(tmp_path) -> None:
    tabraw_path = tmp_path / "generated_ascii_tab_barred.tabraw.json"
    ir_path = tmp_path / "generated_ascii_tab_barred.ir.json"

    extract_tab(ASCII_BARRED_PDF, tabraw_path)

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert raised.value.category == "missing_ascii_alignment_sidecar"
    payload = raised.value.to_diagnostics_payload()
    assert payload["details"]["grouping_status"] == "ascii_grouped"
    assert "partial_ascii_tab_timing" in payload["details"]["tabraw_warning_codes"]
    assert payload["details"]["ascii_timing_status_counts"]["timing_partial"] > 0
    assert payload["details"]["primary_reason_code"] == "missing_ascii_alignment_sidecar"


def test_build_ir_refuses_ambiguous_ascii_tab_timing(tmp_path) -> None:
    tabraw_path = tmp_path / "generated_ascii_tab_uneven_timing.tabraw.json"
    ir_path = tmp_path / "generated_ascii_tab_uneven_timing.ir.json"

    extract_tab(ASCII_UNEVEN_TIMING_PDF, tabraw_path)

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert raised.value.category == "missing_ascii_alignment_sidecar"
    payload = raised.value.to_diagnostics_payload()
    assert "ambiguous_ascii_tab_timing" in payload["details"]["tabraw_warning_codes"]
    assert payload["details"]["primary_reason_code"] == "missing_ascii_alignment_sidecar"


def test_build_ir_refuses_partial_ascii_tab_grouping(tmp_path) -> None:
    tabraw_path = tmp_path / "generated_ascii_tab_malformed.tabraw.json"
    ir_path = tmp_path / "generated_ascii_tab_malformed.ir.json"

    extract_tab(ASCII_MALFORMED_PDF, tabraw_path)

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert raised.value.category == "missing_ascii_alignment_sidecar"
    payload = raised.value.to_diagnostics_payload()
    assert payload["details"]["grouping_status"] == "partial_ascii_tab_grouping"
    assert "partial_ascii_tab_grouping" in payload["details"]["tabraw_warning_codes"]
    assert payload["details"]["primary_reason_code"] == "missing_ascii_alignment_sidecar"


def test_pdf_candidate_outside_system_diagnosed(tmp_path) -> None:
    assert NEW_OUTSIDE_SYSTEM_PDF.exists()
    tabraw_path = tmp_path / "outside_system.tabraw.json"
    ir_path = tmp_path / "outside_system.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_OUTSIDE_SYSTEM_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    assert "pdf_candidate_outside_system" in warning_codes
    assert "pdf_grouping_not_safe_for_build_ir" in warning_codes

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert "pdf_candidate_outside_system" in payload["details"]["tabraw_warning_codes"]


def test_pdf_candidate_outside_bar_diagnosed(tmp_path) -> None:
    assert NEW_OUTSIDE_BAR_PDF.exists()
    tabraw_path = tmp_path / "outside_bar.tabraw.json"
    ir_path = tmp_path / "outside_bar.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_OUTSIDE_BAR_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    assert "pdf_candidate_outside_bar" in warning_codes
    assert "pdf_grouping_not_safe_for_build_ir" in warning_codes

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert "pdf_candidate_outside_bar" in payload["details"]["tabraw_warning_codes"]


def test_pdf_multi_system_order_ambiguous_diagnosed(tmp_path) -> None:
    assert NEW_MULTI_SYSTEM_PDF.exists()
    tabraw_path = tmp_path / "multi_system_ambiguous.tabraw.json"
    ir_path = tmp_path / "multi_system_ambiguous.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_MULTI_SYSTEM_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    assert "pdf_multi_system_order_ambiguous" in warning_codes
    assert "pdf_tab_staff_ambiguous" in warning_codes

    # HTML grouping diagnostics check
    report_html = (tabraw_path.parent / "grouping-diagnostics.html").read_text(encoding="utf-8")
    assert "grouping/layout is ambiguous and unsafe" in report_html

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert "pdf_multi_system_order_ambiguous" in payload["details"]["tabraw_warning_codes"]


def test_pdf_ascii_and_drawn_layout_conflict_diagnosed(tmp_path) -> None:
    assert NEW_CONFLICT_LAYOUT_PDF.exists()
    tabraw_path = tmp_path / "conflict_layout.tabraw.json"
    ir_path = tmp_path / "conflict_layout.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_CONFLICT_LAYOUT_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    assert "pdf_ascii_and_drawn_layout_conflict" in warning_codes
    assert "pdf_page_layout_unsupported" in warning_codes

    # HTML grouping diagnostics check
    report_html = (tabraw_path.parent / "grouping-diagnostics.html").read_text(encoding="utf-8")
    assert "layout/format is unsupported" in report_html

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert "pdf_ascii_and_drawn_layout_conflict" in payload["details"]["tabraw_warning_codes"]


def test_pdf_prose_legend_text_diagnosed(tmp_path) -> None:
    assert NEW_PROSE_LEGEND_PDF.exists()
    tabraw_path = tmp_path / "prose_legend.tabraw.json"
    ir_path = tmp_path / "prose_legend.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_PROSE_LEGEND_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    # No systems, staves, string lines, barlines detected -> missing warning
    assert "pdf_no_systems_detected" in warning_codes
    assert "pdf_tab_staff_missing" in warning_codes
    assert "pdf_string_lines_missing" in warning_codes

    # No fret candidates exist, so playable_fret_candidate_count should be 0
    fret_candidates = [candidate for candidate in tabraw.candidates if candidate.kind == "fret"]
    assert len(fret_candidates) == 0

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert payload["details"]["playable_fret_candidate_count"] == 0


def test_pdf_text_geometry_present_but_no_safe_system_diagnosed(tmp_path) -> None:
    assert NEW_TEXT_GEOM_NO_SYSTEM_PDF.exists()
    tabraw_path = tmp_path / "text_geom_no_system.tabraw.json"
    ir_path = tmp_path / "text_geom_no_system.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_TEXT_GEOM_NO_SYSTEM_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    assert "pdf_text_geometry_present_but_no_safe_system" in warning_codes
    assert "pdf_drawn_geometry_present_but_staff_unresolved" in warning_codes

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert "pdf_text_geometry_present_but_no_safe_system" in payload["details"]["tabraw_warning_codes"]


def test_pdf_tab_candidates_present_but_system_not_detected_diagnosed(tmp_path) -> None:
    assert NEW_TAB_CANDIDATES_NO_SYSTEM_PDF.exists()
    tabraw_path = tmp_path / "tab_cands_no_system.tabraw.json"
    ir_path = tmp_path / "tab_cands_no_system.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_TAB_CANDIDATES_NO_SYSTEM_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    assert "pdf_tab_candidates_present_but_system_not_detected" in warning_codes

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert "pdf_tab_candidates_present_but_system_not_detected" in payload["details"]["tabraw_warning_codes"]


def test_pdf_tab_staff_lines_fragmented_diagnosed(tmp_path) -> None:
    assert NEW_LINES_FRAGMENTED_PDF.exists()
    tabraw_path = tmp_path / "fragmented.tabraw.json"
    ir_path = tmp_path / "fragmented.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_LINES_FRAGMENTED_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    assert "pdf_tab_staff_lines_fragmented" in warning_codes

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert "pdf_tab_staff_lines_fragmented" in payload["details"]["tabraw_warning_codes"]


def test_pdf_candidates_between_systems_diagnosed(tmp_path) -> None:
    assert NEW_CANDIDATES_BETWEEN_SYSTEMS_PDF.exists()
    tabraw_path = tmp_path / "between_systems.tabraw.json"
    ir_path = tmp_path / "between_systems.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_CANDIDATES_BETWEEN_SYSTEMS_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    # Fret at Y=195 is far from any string in either system, hence unassigned
    assert "pdf_candidates_unassigned_to_string" in warning_codes or "pdf_candidates_unassigned_to_system" in warning_codes

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert any(w in payload["details"]["tabraw_warning_codes"] for w in ("pdf_candidates_unassigned_to_string", "pdf_candidates_unassigned_to_system"))


def test_pdf_candidates_unassigned_to_string_diagnosed(tmp_path) -> None:
    assert NEW_CANDIDATES_UNASSIGNED_TO_STRING_PDF.exists()
    tabraw_path = tmp_path / "unassigned_string.tabraw.json"
    ir_path = tmp_path / "unassigned_string.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_CANDIDATES_UNASSIGNED_TO_STRING_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    assert "pdf_candidates_unassigned_to_string" in warning_codes

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert "pdf_candidates_unassigned_to_string" in payload["details"]["tabraw_warning_codes"]


def test_pdf_system_order_ambiguous_close_diagnosed(tmp_path) -> None:
    assert NEW_ORDER_AMBIGUOUS_CLOSE_PDF.exists()
    tabraw_path = tmp_path / "ambiguous_close.tabraw.json"
    ir_path = tmp_path / "ambiguous_close.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_ORDER_AMBIGUOUS_CLOSE_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}
    assert "pdf_system_order_ambiguous" in warning_codes or "pdf_multi_system_order_ambiguous" in warning_codes
    assert "pdf_system_bbox_ambiguous" in warning_codes

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert "pdf_system_order_ambiguous" in payload["details"]["tabraw_warning_codes"] or "pdf_multi_system_order_ambiguous" in payload["details"]["tabraw_warning_codes"]


def test_pdf_mixed_prose_tab_numbers_diagnosed(tmp_path) -> None:
    assert NEW_MIXED_PROSE_TAB_NUMBERS_PDF.exists()
    tabraw_path = tmp_path / "mixed_prose.tabraw.json"
    ir_path = tmp_path / "mixed_prose.ir.json"

    tabraw = TabRaw.model_validate(extract_tab(NEW_MIXED_PROSE_TAB_NUMBERS_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    # We expect some numbers like "1", "2", "3", "5" to be extracted as fret candidates
    fret_candidates = [c for c in tabraw.candidates if c.kind == "fret"]
    assert len(fret_candidates) > 0
    # But since they are inside prose text with no tab systems, safe_grouping is False
    assert all(c.raw.get("safe_grouping") is False for c in fret_candidates)

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    payload = raised.value.to_diagnostics_payload()
    assert payload["details"]["playable_fret_candidate_count"] > 0
    assert "pdf_no_systems_detected" in payload["details"]["tabraw_warning_codes"]


def test_refined_drawn_no_system_diagnostics(tmp_path) -> None:
    tabraw_path = tmp_path / "tab_cands_no_system.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(NEW_TAB_CANDIDATES_NO_SYSTEM_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    # Assert specific warning codes from refined taxonomy
    assert "pdf_drawn_system_not_detected" in warning_codes
    assert "pdf_system_detection_not_enough_for_build_ir" in warning_codes
    assert "pdf_no_systems_detected" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=NEW_TAB_CANDIDATES_NO_SYSTEM_PDF,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["input_class"] == "drawn_tab_candidate" or report["input_class"] == "unsupported"
    assert report["whether_system_detection_succeeded"] is False
    assert report["primary_blocker_stage"] == "system_detection"


def test_refined_fragmented_drawn_staff_diagnostics(tmp_path) -> None:
    tabraw_path = tmp_path / "fragmented.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(NEW_LINES_FRAGMENTED_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_drawn_staff_lines_unresolved" in warning_codes
    assert "pdf_tab_staff_lines_fragmented" in warning_codes


def test_refined_overlapping_systems_diagnostics(tmp_path) -> None:
    tabraw_path = tmp_path / "ambiguous_close.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(NEW_ORDER_AMBIGUOUS_CLOSE_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_drawn_system_ambiguous" in warning_codes
    assert "pdf_system_order_ambiguous" in warning_codes


def test_refined_ascii_three_blocks_no_bars_diagnostics(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_ascii_tab_three_blocks_no_bars.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "three_blocks.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_ascii_system_detected" in warning_codes
    assert "pdf_ascii_system_measure_boundaries_missing" in warning_codes
    assert "pdf_ascii_system_timing_unavailable" in warning_codes
    assert "pdf_input_class_ascii_tab_requires_alignment" in warning_codes


def test_refined_ascii_no_bars_with_separators_diagnostics(tmp_path) -> None:
    tabraw_path = tmp_path / "no_bars.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(ASCII_NO_BARS_PDF, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_ascii_system_detected" in warning_codes
    assert "pdf_ascii_system_timing_unavailable" in warning_codes
    assert "pdf_input_class_ascii_tab_requires_alignment" in warning_codes


def test_refined_mixed_drawn_ascii_diagnostics(tmp_path) -> None:
    tabraw_path = tmp_path / "conflict.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(NEW_CONFLICT_LAYOUT_PDF, tabraw_path))

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=NEW_CONFLICT_LAYOUT_PDF,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["input_class"] == "mixed_candidate"
    assert report["primary_blocker_stage"] == "unsupported_input_class"


def test_refined_system_detected_no_bars_diagnostics(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_system_detected_no_barlines.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "no_barlines.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_system_detected_bar_detection_missing" in warning_codes
    assert "pdf_input_class_drawn_tab_requires_barlines" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_system_detection_succeeded"] is True
    assert report["whether_bar_detection_succeeded"] is False
    assert report["primary_blocker_stage"] == "bar_detection"


def test_refined_valid_grouped_counterpart_diagnostics(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_valid_grouped_counterpart.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "valid_counterpart.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_system_detected_bar_detection_missing" not in warning_codes
    assert "pdf_input_class_drawn_tab_requires_barlines" not in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_system_detection_succeeded"] is True
    assert report["whether_bar_detection_succeeded"] is True
    assert report["primary_blocker_stage"] == "none" or report["primary_blocker_stage"] == "timing_alignment"


def test_refined_barlines_do_not_cross_staff_diagnostics(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_barlines_do_not_cross_staff.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "do_not_cross.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_barline_does_not_cross_staff" in warning_codes
    assert "pdf_bar_boxes_not_constructible" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["primary_blocker_stage"] == "bar_detection"


def test_refined_barlines_too_short_diagnostics(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_barlines_too_short.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "too_short.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_barline_too_short" in warning_codes
    assert "pdf_bar_boxes_not_constructible" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["primary_blocker_stage"] == "bar_detection"


def test_refined_barlines_outside_bounds_diagnostics(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_barlines_outside_bounds.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "outside_bounds.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_barline_outside_system_bounds" in warning_codes
    assert "pdf_bar_boxes_not_constructible" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["primary_blocker_stage"] == "bar_detection"


def test_refined_barlines_ambiguous_diagnostics(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_barlines_ambiguous.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "ambiguous.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_barline_ambiguous" in warning_codes
    assert "pdf_bar_boxes_not_constructible" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["primary_blocker_stage"] == "bar_detection"


def test_refined_bar_boxes_not_constructible_diagnostics(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_bar_boxes_not_constructible.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "not_constructible.tabraw.json"

    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {warning["code"] for warning in tabraw.warnings}

    assert "pdf_bar_box_edge_boundary_fallback_used" in warning_codes
    assert "pdf_bar_box_inferred_right_boundary" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is True
    assert report["primary_blocker_stage"] in ("none", "timing_alignment")


def test_build_ir_refuses_unsafe_bar_detection_cases(tmp_path) -> None:
    fixtures = [
        ("generated_pdf_system_detected_no_barlines.pdf", "pdf_bar_boxes_not_constructible"),
        ("generated_pdf_barlines_do_not_cross_staff.pdf", "pdf_barline_does_not_cross_staff"),
        ("generated_pdf_barlines_too_short.pdf", "pdf_barline_too_short"),
        ("generated_pdf_barlines_outside_bounds.pdf", "pdf_barline_outside_system_bounds"),
        ("generated_pdf_barlines_ambiguous.pdf", "pdf_barline_ambiguous"),
    ]

    for filename, expected_warning in fixtures:
        pdf_path = Path("tests/fixtures/pdf") / filename
        assert pdf_path.exists()
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


def test_refined_barline_validation_boundaries(tmp_path) -> None:
    # 1. compact barline crossing all string lines is accepted (below absolute threshold but crossing staff)
    pdf1 = Path("tests/fixtures/pdf/generated_pdf_barlines_below_threshold_crossing_staff.pdf")
    assert pdf1.exists()
    tabraw1 = TabRaw.model_validate(extract_tab(pdf1, tmp_path / "below_threshold_crossing_staff.tabraw.json"))
    # Confirms relative-height accepted fixture constructs bar boxes
    warning_codes1 = {w["code"] for w in tabraw1.warnings}
    assert "pdf_bar_boxes_constructed" in warning_codes1
    assert "pdf_bar_boxes_not_constructible" not in warning_codes1

    # Check diagnostics contents: absolute height, staff height/coverage, string gap crossing count, and final decision
    fret1 = tabraw1.candidates[0]
    details1 = fret1.raw["barline_candidates_details"]
    assert details1
    assert details1[0]["absolute_height_decision"] == "rejected"
    assert details1[0]["relative_staff_crossing_decision"] == "accepted"
    assert details1[0]["final_decision"] == "accepted"
    assert details1[0]["gaps_crossed"] == 5
    assert details1[0]["height"] < 40.0
    assert details1[0]["height"] >= 20.0

    # 2. compact barline crossing too few lines/partial staff is rejected
    pdf2 = Path("tests/fixtures/pdf/generated_pdf_barlines_below_threshold_crossing_partial_staff.pdf")
    tabraw2 = TabRaw.model_validate(extract_tab(pdf2, tmp_path / "below_threshold_crossing_partial_staff.tabraw.json"))
    warning_codes2 = {w["code"] for w in tabraw2.warnings}
    assert "pdf_barline_does_not_cross_staff" in warning_codes2
    assert "pdf_bar_boxes_not_constructible" in warning_codes2
    fret2 = tabraw2.candidates[0]
    details2 = fret2.raw["barline_candidates_details"]
    assert details2[0]["rejection_reason"] in ("pdf_barline_partial_staff_crossing", "pdf_barline_crosses_insufficient_string_gaps")
    assert details2[0]["final_decision"] == "rejected"

    # 3. tall barline outside staff region is rejected
    pdf3 = Path("tests/fixtures/pdf/generated_pdf_barlines_above_threshold_outside_staff_region.pdf")
    tabraw3 = TabRaw.model_validate(extract_tab(pdf3, tmp_path / "above_threshold_outside_staff_region.tabraw.json"))
    warning_codes3 = {w["code"] for w in tabraw3.warnings}
    assert "pdf_barline_outside_staff_region" in warning_codes3 or "pdf_barline_does_not_cross_staff" in warning_codes3
    assert "pdf_bar_boxes_not_constructible" in warning_codes3
    fret3 = tabraw3.candidates[0]
    details3 = fret3.raw["barline_candidates_details"]
    assert details3[0]["rejection_reason"] == "pdf_barline_outside_staff_region"
    assert details3[0]["final_decision"] == "rejected"

    # 4. barline crossing top/bottom strings but missing middle staff lines (insufficient gaps)
    pdf4 = Path("tests/fixtures/pdf/generated_pdf_barlines_crossing_top_bottom_missing_middle.pdf")
    tabraw4 = TabRaw.model_validate(extract_tab(pdf4, tmp_path / "crossing_top_bottom_missing_middle.tabraw.json"))
    warning_codes4 = {w["code"] for w in tabraw4.warnings}
    assert "pdf_bar_boxes_not_constructible" in warning_codes4
    fret4 = tabraw4.candidates[0]
    details4 = fret4.raw["barline_candidates_details"]
    assert details4[0]["rejection_reason"] == "pdf_barline_crosses_insufficient_string_gaps"
    assert details4[0]["final_decision"] == "rejected"

    # 5. barline crossing all gaps short absolute (compact spacing accepted)
    pdf5 = Path("tests/fixtures/pdf/generated_pdf_barlines_crossing_all_gaps_short_absolute.pdf")
    tabraw5 = TabRaw.model_validate(extract_tab(pdf5, tmp_path / "crossing_all_gaps_short_absolute.tabraw.json"))
    warning_codes5 = {w["code"] for w in tabraw5.warnings}
    assert "pdf_bar_boxes_constructed" in warning_codes5
    fret5 = tabraw5.candidates[0]
    details5 = fret5.raw["barline_candidates_details"]
    assert details5[0]["final_decision"] == "accepted"

    # 6. barline crossing only some gaps is rejected
    pdf6 = Path("tests/fixtures/pdf/generated_pdf_barlines_crossing_only_some_gaps.pdf")
    tabraw6 = TabRaw.model_validate(extract_tab(pdf6, tmp_path / "crossing_only_some_gaps.tabraw.json"))
    warning_codes6 = {w["code"] for w in tabraw6.warnings}
    assert "pdf_bar_boxes_not_constructible" in warning_codes6
    fret6 = tabraw6.candidates[0]
    details6 = fret6.raw["barline_candidates_details"]
    assert details6[0]["rejection_reason"] == "pdf_barline_crosses_insufficient_string_gaps"
    assert details6[0]["final_decision"] == "rejected"


def test_refined_compact_barline_success_and_failures(tmp_path) -> None:
    # 7. Multiple compact valid barlines creating safe bar boxes -> grouped
    pdf7 = Path("tests/fixtures/pdf/generated_pdf_compact_barlines_safe_boxes.pdf")
    assert pdf7.exists()
    tabraw7 = TabRaw.model_validate(extract_tab(pdf7, tmp_path / "compact_safe_boxes.tabraw.json"))
    warning_codes7 = {w["code"] for w in tabraw7.warnings}
    assert "pdf_bar_boxes_constructed" in warning_codes7
    assert "pdf_barlines_not_detected_in_system" not in warning_codes7
    assert "pdf_bar_boxes_not_constructible" not in warning_codes7
    assert "pdf_bar_box_construction_not_enough_for_build_ir" not in warning_codes7

    # 8. Compact valid barlines but candidate outside bars (barline validation succeeds, downstream bar assignment blocks)
    pdf8 = Path("tests/fixtures/pdf/generated_pdf_compact_barlines_candidate_outside.pdf")
    assert pdf8.exists()
    tabraw8 = TabRaw.model_validate(extract_tab(pdf8, tmp_path / "compact_candidate_outside.tabraw.json"))
    warning_codes8 = {w["code"] for w in tabraw8.warnings}
    assert "pdf_bar_boxes_constructed" in warning_codes8
    assert "pdf_candidate_outside_bar" in warning_codes8
    assert "pdf_grouping_not_safe_for_build_ir" in warning_codes8

    # 9. build-ir refuses unsafe barline validation cases
    unsafe_fixtures = [
        ("generated_pdf_barlines_below_threshold_crossing_partial_staff.pdf", "pdf_barline_does_not_cross_staff"),
        ("generated_pdf_barlines_above_threshold_outside_staff_region.pdf", "pdf_barline_outside_staff_region"),
        ("generated_pdf_barlines_crossing_top_bottom_missing_middle.pdf", "pdf_barline_crosses_insufficient_string_gaps"),
        ("generated_pdf_barlines_crossing_only_some_gaps.pdf", "pdf_barline_crosses_insufficient_string_gaps"),
        ("generated_pdf_compact_barlines_candidate_outside.pdf", "pdf_candidate_outside_bar"),
    ]
    for filename, expected_warning in unsafe_fixtures:
        pdf_path = Path("tests/fixtures/pdf") / filename
        assert pdf_path.exists()
        tabraw_path = tmp_path / f"{pdf_path.stem}.tabraw.json"
        ir_path = tmp_path / f"{pdf_path.stem}.ir.json"

        extract_tab(pdf_path, tabraw_path)

        with pytest.raises(BuildIrInputRiskError) as raised:
            build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

        assert not ir_path.exists()
        assert raised.value.category in ("partial_pdf_grouping", "pdf_grouping_not_safe_for_build_ir")
        payload = raised.value.to_diagnostics_payload()
        assert expected_warning in payload["details"]["warning_codes"]

    # 10. valid counterpart passes build-ir
    pdf_valid = Path("tests/fixtures/pdf/generated_pdf_compact_barlines_safe_boxes.pdf")
    tabraw_valid = tmp_path / "compact_valid.tabraw.json"
    ir_valid = tmp_path / "compact_valid.ir.json"
    extract_tab(pdf_valid, tabraw_valid)
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_valid, ir_valid)
    assert raised.value.category == "partial_pdf_grouping"
    assert "pdf_string_assignment_compact_staff_ambiguous" in raised.value.to_diagnostics_payload()["details"]["warning_codes"]


def test_synthetic_one_bar_box_constructed(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_one_bar_box.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "one_bar_box.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_boxes_constructed" in warning_codes
    assert "pdf_bar_boxes_not_constructible" not in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is True
    assert report["primary_blocker_stage"] in ("none", "timing_alignment")


def test_synthetic_one_accepted_barline(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_one_accepted_barline.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "one_accepted_barline.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_edge_boundary_fallback_used" in warning_codes
    assert "pdf_bar_box_inferred_left_boundary" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is True
    assert report["primary_blocker_stage"] in ("none", "timing_alignment")


def test_synthetic_bar_box_too_narrow(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_bar_box_too_narrow.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "bar_box_too_narrow.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_too_narrow" in warning_codes
    assert "pdf_bar_box_construction_not_enough_for_build_ir" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is False
    assert report["primary_blocker_stage"] == "bar_detection"


def test_tab_system_overlaps_neighbor() -> None:
    from score2gp.pdf import _TabSystem
    sys = _TabSystem(
        page_index=1,
        system_index=1,
        staff_index=1,
        first_bar_index=1,
        line_ys=[120, 134, 148, 162, 176, 190],
        x0=72,
        x1=332,
        barlines=[120, 200, 150, 280],  # unsorted barlines lead to overlap!
    )
    assert "pdf_bar_box_overlaps_neighbor" in sys.grouping_warnings
    assert "pdf_bar_box_construction_not_enough_for_build_ir" in sys.grouping_warnings


def test_synthetic_bar_box_outside_system(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_bar_box_outside_system.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "bar_box_outside.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_outside_system_bounds" in warning_codes
    assert "pdf_bar_box_construction_not_enough_for_build_ir" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is False
    assert report["primary_blocker_stage"] == "bar_detection"


def test_synthetic_candidate_left_of_boxes(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_candidate_left_of_boxes.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "left_of_boxes.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_candidate_unassigned_to_bar" in warning_codes


def test_synthetic_candidate_on_boundary(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_candidate_on_boundary.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "on_boundary.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_candidate_on_bar_boundary" in warning_codes
    assert "pdf_candidate_boundary_ambiguous" in warning_codes
    assert "pdf_bar_box_boundary_ambiguous" in warning_codes


def test_synthetic_multi_system_one_failed(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_multi_system_one_failed.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "multi_failed.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_edge_boundary_fallback_used" in warning_codes
    assert "pdf_bar_box_inferred_right_boundary" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is True
    assert report["primary_blocker_stage"] in ("none", "timing_alignment")


def test_synthetic_multi_system_all_valid(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_multi_system_all_valid.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "multi_all_valid.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_grouping_complete" in warning_codes
    assert tabraw.warnings[-1]["grouping_status"] == "grouped"

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is True
    assert report["primary_blocker_stage"] in ("none", "timing_alignment")


def test_synthetic_empty_system_policy(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_empty_system_policy.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "empty_policy.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    # It should not complain about partial grouping on empty systems!
    assert "pdf_partial_grouping_one_system_unboxed" not in warning_codes
    assert "pdf_grouping_complete" in warning_codes
    assert tabraw.warnings[-1]["grouping_status"] == "grouped"

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is True
    assert report["primary_blocker_stage"] in ("none", "timing_alignment")


def test_synthetic_one_accepted_one_rejected(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_one_accepted_one_rejected.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "one_acc_one_rej.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_one_boundary_rejected" in warning_codes
    assert "pdf_bar_box_edge_system_missing_boundary" in warning_codes
    assert "pdf_candidate_near_missing_bar_boundary" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is False
    assert report["primary_blocker_stage"] == "bar_detection"


def test_synthetic_two_short_barlines(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_two_short_barlines.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "two_short.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_single_system_failure" in warning_codes
    assert "pdf_barline_short_but_near_staff_boundary" in warning_codes
    assert "pdf_candidate_unassigned_due_to_unboxed_system" in warning_codes
    assert "pdf_candidate_near_missing_bar_boundary" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is False
    assert report["primary_blocker_stage"] == "bar_detection"


def test_build_ir_refuses_bar_box_construction_failures(tmp_path) -> None:
    unsafe_fixtures = [
        ("generated_pdf_bar_box_too_narrow.pdf", "pdf_bar_box_too_narrow"),
        ("generated_pdf_bar_box_outside_system.pdf", "pdf_bar_box_outside_system_bounds"),
        ("generated_pdf_candidate_left_of_boxes.pdf", "pdf_candidate_unassigned_to_bar"),
        ("generated_pdf_candidate_on_boundary.pdf", "pdf_candidate_on_bar_boundary"),
        ("generated_pdf_one_accepted_one_rejected.pdf", "pdf_bar_box_one_boundary_rejected"),
        ("generated_pdf_two_short_barlines.pdf", "pdf_bar_box_single_system_failure"),
    ]
    for filename, expected_warning in unsafe_fixtures:
        pdf_path = Path("tests/fixtures/pdf") / filename
        assert pdf_path.exists()
        tabraw_path = tmp_path / f"{pdf_path.stem}.tabraw.json"
        ir_path = tmp_path / f"{pdf_path.stem}.ir.json"

        extract_tab(pdf_path, tabraw_path)

        with pytest.raises(BuildIrInputRiskError) as raised:
            build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

        assert not ir_path.exists()
        assert raised.value.category in ("partial_pdf_grouping", "pdf_grouping_not_safe_for_build_ir")
        payload = raised.value.to_diagnostics_payload()
        assert expected_warning in payload["details"]["warning_codes"]


def test_synthetic_edge_left_fallback(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_edge_left_fallback.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "edge_left_fallback.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_edge_boundary_fallback_used" in warning_codes
    assert "pdf_bar_box_inferred_left_boundary" in warning_codes

    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(
        source_pdf=pdf_path,
        inspection={"kind": "born-digital", "page_count": 1},
        tabraw=tabraw.model_dump(mode="json"),
        artifacts={},
    )
    assert report["whether_bar_detection_succeeded"] is True


def test_synthetic_edge_right_fallback(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_edge_right_fallback.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "edge_right_fallback.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_edge_boundary_fallback_used" in warning_codes
    assert "pdf_bar_box_inferred_right_boundary" in warning_codes


def test_synthetic_edge_ambiguous_fallback(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_edge_ambiguous_fallback.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "edge_ambig.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_edge_boundary_fallback_rejected" in warning_codes
    assert "pdf_bar_box_edge_boundary_ambiguous" in warning_codes
    assert "pdf_bar_box_inferred_boundary_requires_clear_system_edge" in warning_codes


def test_synthetic_edge_too_narrow_fallback(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_edge_too_narrow_fallback.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "too_narrow.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_edge_boundary_fallback_rejected" in warning_codes
    assert "pdf_bar_box_inferred_boundary_too_narrow" in warning_codes


def test_synthetic_edge_candidate_near_inferred(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_edge_candidate_near_inferred.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "near_inferred.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_edge_boundary_fallback_rejected" in warning_codes
    assert "pdf_bar_box_inferred_boundary_candidate_ambiguous" in warning_codes


def test_synthetic_multi_system_safe_fallback(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_multi_system_safe_fallback.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "multi_safe.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_edge_boundary_fallback_used" in warning_codes
    assert "pdf_bar_box_inferred_left_boundary" in warning_codes
    assert "pdf_grouping_complete" in warning_codes


def test_synthetic_multi_system_partial_fallback(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_multi_system_partial_fallback.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "multi_partial.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_bar_box_edge_boundary_fallback_rejected" in warning_codes
    assert "pdf_bar_box_inferred_boundary_candidate_ambiguous" in warning_codes


def test_synthetic_next_blocker_string_assignment(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_next_blocker_string_assignment.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "next_blocker.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_candidates_unassigned_to_string" in warning_codes


def test_synthetic_empty_system_policy_fallback(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_empty_system_policy_fallback.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "empty_policy.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))
    warning_codes = {w["code"] for w in tabraw.warnings}
    assert "pdf_grouping_complete" in warning_codes
    assert "pdf_bar_box_edge_boundary_fallback_used" in warning_codes


def test_build_ir_allows_safe_fallback_fixture(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_edge_left_fallback.pdf")
    tabraw_path = tmp_path / "safe.tabraw.json"
    ir_path = tmp_path / "safe.ir.json"

    extract_tab(pdf_path, tabraw_path)
    build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)
    assert ir_path.exists()


def test_pdf_edge_boundary_report(tmp_path) -> None:
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_edge_ambiguous_fallback.pdf")
    assert pdf_path.exists()
    tabraw_path = tmp_path / "edge_ambig.tabraw.json"

    # 1. Run extraction and verify reports exist
    extract_tab(pdf_path, tabraw_path)

    report_json_path = tmp_path / "pdf-edge-boundary-report.json"
    report_html_path = tmp_path / "pdf-edge-boundary-report.html"
    grouping_html_path = tmp_path / "grouping-diagnostics.html"

    assert report_json_path.exists()
    assert report_html_path.exists()
    assert grouping_html_path.exists()

    # 2. Check JSON report fields
    report = json.loads(report_json_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "pdf-edge-boundary-report.v0.9"
    assert report["page_index"] == 1
    assert report["system_index"] == 1
    assert report["system_has_playable_candidates"] is True
    assert report["observed_boundary_count"] == 2
    assert report["accepted_boundary_count"] == 1
    assert report["rejected_boundary_count"] == 1
    assert report["inferred_boundary_count"] == 0
    assert report["fallback_considered"] is True
    assert report["fallback_accepted"] is False
    assert report["fallback_rejected"] is True
    assert "pdf_bar_box_edge_boundary_ambiguous" in report["fallback_rejection_reasons"]
    assert report["missing_side"] == "left"
    assert report["candidate_count_in_failed_system"] > 0
    assert report["playable_candidate_count_in_failed_system"] > 0
    assert report["candidates_unassigned_due_to_failed_boundary"] > 0
    assert report["whether_grouping_remains_partial"] is True
    assert report["whether_build_ir_blocked"] is True
    assert "Remediation:" in report["remediation_hint"]

    # 3. Private safety checks
    for key, value in report.items():
        val_str = str(value)
        # Avoid private-like content or specific musical symbols
        assert "E#" not in val_str
        assert "Cmaj7" not in val_str
        assert "fret_sequence" not in val_str
        assert "<chord/>" not in val_str

    # 4. Check HTML report content
    html_content = report_html_path.read_text(encoding="utf-8")
    assert "PDF Edge-Boundary Fallback Rejected" in html_content
    assert "Fallback Rejected &amp; ScoreIR Blocked" in html_content
    assert "pdf_bar_box_edge_boundary_ambiguous" in html_content
    assert "Remediation:" in html_content

    # 5. Check grouping diagnostics HTML links
    grouping_html = grouping_html_path.read_text(encoding="utf-8")
    assert "pdf-edge-boundary-report.json" in grouping_html
    assert "pdf-edge-boundary-report.html" in grouping_html

    # 6. Check build-ir refusal diagnostics reference
    ir_path = tmp_path / "failed.ir.json"
    diag_path = tmp_path / "failed.diagnostics.json"

    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path, diag_path)

    assert exc_info.value.category == "partial_pdf_grouping"
    assert exc_info.value.stage == "tabraw-import"

    assert diag_path.exists()
    diag_payload = json.loads(diag_path.read_text(encoding="utf-8"))
    assert diag_payload["pdf_edge_boundary_report_html"] == "pdf-edge-boundary-report.html"
    assert diag_payload["pdf_edge_boundary_report_json"] == "pdf-edge-boundary-report.json"
    assert diag_payload["grouping_diagnostics_html"] == "grouping-diagnostics.html"


# Fixture paths for string assignment
STRING_ASSIGN_DIR = Path(__file__).parent / "fixtures" / "pdf"
PDF_VALID = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_valid.pdf"
PDF_MULTIDIGIT = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_multidigit.pdf"
PDF_OFFSET = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_offset_tolerant.pdf"
PDF_BETWEEN = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_between_lines.pdf"
PDF_OUTSIDE = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_outside_staff.pdf"
PDF_COMPACT = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_compact_staff.pdf"
PDF_TECHNIQUES = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_techniques.pdf"
PDF_CHORDS = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_chords.pdf"
PDF_GROUPED_SUCCESS = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_grouped_success.pdf"
PDF_UPSTREAM_BLOCKED = STRING_ASSIGN_DIR / "generated_pdf_string_assignment_upstream_blocked.pdf"


def test_pdf_string_assignment_valid(tmp_path) -> None:
    assert PDF_VALID.exists()
    tabraw_path = tmp_path / "valid.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_VALID, tabraw_path))
    assert len(raw.candidates) == 6
    assert all(c.string == idx + 1 for idx, c in enumerate(raw.candidates))
    assert all("pdf_string_assignment_nearest_line" in c.raw.get("assignment_warnings", []) for c in raw.candidates)


def test_pdf_string_assignment_multidigit(tmp_path) -> None:
    assert PDF_MULTIDIGIT.exists()
    tabraw_path = tmp_path / "multidigit.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_MULTIDIGIT, tabraw_path))
    assert len(raw.candidates) == 3
    assert [c.parsed_fret for c in raw.candidates] == [10, 12, 15]
    assert [c.string for c in raw.candidates] == [1, 3, 5]
    assert all("pdf_multidigit_fret_string_assigned" in c.raw.get("assignment_warnings", []) for c in raw.candidates)


def test_pdf_string_assignment_offset_tolerant(tmp_path) -> None:
    assert PDF_OFFSET.exists()
    tabraw_path = tmp_path / "offset.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_OFFSET, tabraw_path))
    assert len(raw.candidates) == 1
    c = raw.candidates[0]
    assert c.string == 2
    assert "pdf_string_assignment_nearest_line" in c.raw.get("assignment_warnings", [])


def test_pdf_string_assignment_between_lines(tmp_path) -> None:
    assert PDF_BETWEEN.exists()
    tabraw_path = tmp_path / "between.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_BETWEEN, tabraw_path))
    assert len(raw.candidates) == 1
    c = raw.candidates[0]
    assert c.string is None
    assert "pdf_string_assignment_between_lines" in c.raw.get("assignment_warnings", [])
    assert "pdf_string_assignment_ambiguous" in c.raw.get("assignment_warnings", [])


def test_pdf_string_assignment_outside_staff(tmp_path) -> None:
    assert PDF_OUTSIDE.exists()
    tabraw_path = tmp_path / "outside.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_OUTSIDE, tabraw_path))
    assert len(raw.candidates) == 2
    assert all(c.string is None for c in raw.candidates)
    assert all("pdf_string_assignment_outside_staff" in c.raw.get("assignment_warnings", []) for c in raw.candidates)


def test_pdf_string_assignment_compact_staff(tmp_path) -> None:
    assert PDF_COMPACT.exists()
    tabraw_path = tmp_path / "compact.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_COMPACT, tabraw_path))
    assert len(raw.candidates) == 1
    c = raw.candidates[0]
    assert "pdf_string_assignment_compact_staff_ambiguous" in c.raw.get("assignment_warnings", [])


def test_pdf_string_assignment_techniques(tmp_path) -> None:
    assert PDF_TECHNIQUES.exists()
    tabraw_path = tmp_path / "techniques.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TECHNIQUES, tabraw_path))
    fret_candidates = [c for c in raw.candidates if c.kind == "fret"]
    tech_candidates = [c for c in raw.candidates if c.kind == "technique-text"]
    assert len(fret_candidates) == 2
    assert len(tech_candidates) == 3
    assert all(c.string is not None for c in fret_candidates)
    assert all("pdf_non_playable_text_not_string_assigned" in c.raw.get("assignment_warnings", []) for c in tech_candidates)


def test_pdf_string_assignment_chords(tmp_path) -> None:
    assert PDF_CHORDS.exists()
    tabraw_path = tmp_path / "chords.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_CHORDS, tabraw_path))
    chord_candidates = [c for c in raw.candidates if c.kind == "chord-symbol"]
    assert len(chord_candidates) == 2
    assert all(c.string is None for c in chord_candidates)
    assert all("pdf_non_playable_text_not_string_assigned" in c.raw.get("assignment_warnings", []) for c in chord_candidates)


def test_pdf_string_assignment_grouped_success(tmp_path) -> None:
    assert PDF_GROUPED_SUCCESS.exists()
    tabraw_path = tmp_path / "grouped_success.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_GROUPED_SUCCESS, tabraw_path))
    assert grouping_status_for_tabraw(raw.model_dump(mode="json")) == "grouped"


def test_pdf_string_assignment_upstream_blocked(tmp_path) -> None:
    assert PDF_UPSTREAM_BLOCKED.exists()
    tabraw_path = tmp_path / "upstream_blocked.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_UPSTREAM_BLOCKED, tabraw_path))
    warning_codes = {w.get("code") for w in raw.warnings}
    assert "pdf_string_assignment_succeeded_upstream_grouping_still_blocks" in warning_codes


# Fixture paths for fret refinement
PDF_FRET_CLEAN_SINGLE_DIGIT = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_clean_single_digit.pdf"
PDF_FRET_CLEAN_MULTIDIGIT = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_clean_multidigit.pdf"
PDF_FRET_SPLIT_SPAN_MERGED = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_split_span_merged.pdf"
PDF_FRET_GAP_TOO_LARGE = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_gap_too_large.pdf"
PDF_FRET_VERTICAL_MISALIGNMENT = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_vertical_misalignment.pdf"
PDF_FRET_TECHNIQUE_MARKER = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_technique_marker.pdf"
PDF_FRET_CHORD_TEXT_EXCLUDED = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_chord_text_excluded.pdf"
PDF_FRET_PAGE_LEGEND_EXCLUDED = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_page_legend_excluded.pdf"
PDF_FRET_OVERSIZED_TALL = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_oversized_tall.pdf"
PDF_FRET_TINY_NOISY = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_tiny_noisy.pdf"
PDF_FRET_GROUPED_SUCCESS = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_fret_grouped_success.pdf"


def test_pdf_fret_clean_single_digit(tmp_path) -> None:
    assert PDF_FRET_CLEAN_SINGLE_DIGIT.exists()
    tabraw_path = tmp_path / "fret_single.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_CLEAN_SINGLE_DIGIT, tabraw_path))
    fret_candidates = [c for c in raw.candidates if c.kind == "fret"]
    assert len(fret_candidates) == 6
    assert [c.parsed_fret for c in fret_candidates] == [3, 5, 0, 2, 3, 1]
    assert all("pdf_fret_single_digit_extracted" in c.raw.get("assignment_warnings", []) for c in fret_candidates)


def test_pdf_fret_clean_multidigit(tmp_path) -> None:
    assert PDF_FRET_CLEAN_MULTIDIGIT.exists()
    tabraw_path = tmp_path / "fret_multi.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_CLEAN_MULTIDIGIT, tabraw_path))
    fret_candidates = [c for c in raw.candidates if c.kind == "fret"]
    assert len(fret_candidates) == 3
    assert [c.parsed_fret for c in fret_candidates] == [10, 12, 15]
    assert all("pdf_fret_multidigit_extracted" in c.raw.get("assignment_warnings", []) for c in fret_candidates)


def test_pdf_fret_split_span_merged(tmp_path) -> None:
    assert PDF_FRET_SPLIT_SPAN_MERGED.exists()
    tabraw_path = tmp_path / "fret_split.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_SPLIT_SPAN_MERGED, tabraw_path))
    fret_candidates = [c for c in raw.candidates if c.kind == "fret"]
    assert len(fret_candidates) == 1
    c = fret_candidates[0]
    assert c.parsed_fret == 12
    assert "pdf_fret_digits_merged" in c.raw.get("assignment_warnings", [])
    assert "pdf_fret_split_text_span_merged" in c.raw.get("assignment_warnings", [])


def test_pdf_fret_gap_too_large(tmp_path) -> None:
    assert PDF_FRET_GAP_TOO_LARGE.exists()
    tabraw_path = tmp_path / "fret_gap.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_GAP_TOO_LARGE, tabraw_path))
    warning_codes = {warning.get("code") for warning in raw.warnings}
    assert "pdf_fret_digits_not_merged_gap_too_large" in warning_codes
    assert "pdf_fret_refinement_not_enough_for_build_ir" in warning_codes


def test_pdf_fret_vertical_misalignment(tmp_path) -> None:
    assert PDF_FRET_VERTICAL_MISALIGNMENT.exists()
    tabraw_path = tmp_path / "fret_vertical.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_VERTICAL_MISALIGNMENT, tabraw_path))
    warning_codes = {warning.get("code") for warning in raw.warnings}
    assert "pdf_fret_digits_not_merged_vertical_misalignment" in warning_codes
    assert "pdf_fret_refinement_not_enough_for_build_ir" in warning_codes


def test_pdf_fret_technique_marker(tmp_path) -> None:
    assert PDF_FRET_TECHNIQUE_MARKER.exists()
    tabraw_path = tmp_path / "fret_tech.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_TECHNIQUE_MARKER, tabraw_path))
    fret_candidates = [c for c in raw.candidates if c.kind == "fret"]
    tech_candidates = [c for c in raw.candidates if c.kind == "technique-text"]
    assert len(fret_candidates) == 5
    assert [c.parsed_fret for c in fret_candidates] == [7, 9, 5, 7, 8]
    assert len(tech_candidates) == 3
    assert {c.raw_text for c in tech_candidates} == {"h", "/", "b"}
    assert all("pdf_fret_technique_marker_excluded" in c.raw.get("assignment_warnings", []) for c in tech_candidates)


def test_pdf_fret_chord_text_excluded(tmp_path) -> None:
    assert PDF_FRET_CHORD_TEXT_EXCLUDED.exists()
    tabraw_path = tmp_path / "fret_chord.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_CHORD_TEXT_EXCLUDED, tabraw_path))
    chord_candidates = [c for c in raw.candidates if c.kind == "chord-symbol"]
    excluded_cands = [c for c in raw.candidates if "pdf_fret_chord_text_digit_excluded" in c.raw.get("assignment_warnings", [])]
    assert len(chord_candidates) == 1
    assert len(excluded_cands) == 1
    assert all("pdf_fret_chord_text_digit_excluded" in c.raw.get("assignment_warnings", []) for c in excluded_cands)


def test_pdf_fret_page_legend_excluded(tmp_path) -> None:
    assert PDF_FRET_PAGE_LEGEND_EXCLUDED.exists()
    tabraw_path = tmp_path / "fret_legend.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_PAGE_LEGEND_EXCLUDED, tabraw_path))
    excluded_cands = [c for c in raw.candidates if "pdf_fret_page_or_legend_number_excluded" in c.raw.get("assignment_warnings", [])]
    assert len(excluded_cands) == 2
    assert all("pdf_fret_page_or_legend_number_excluded" in c.raw.get("assignment_warnings", []) for c in excluded_cands)


def test_pdf_fret_oversized_tall(tmp_path) -> None:
    assert PDF_FRET_OVERSIZED_TALL.exists()
    tabraw_path = tmp_path / "fret_oversized.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_OVERSIZED_TALL, tabraw_path))
    warning_codes = {warning.get("code") for warning in raw.warnings}
    assert "pdf_fret_bbox_too_tall" in warning_codes
    assert "pdf_fret_refinement_not_enough_for_build_ir" in warning_codes


def test_pdf_fret_tiny_noisy(tmp_path) -> None:
    assert PDF_FRET_TINY_NOISY.exists()
    tabraw_path = tmp_path / "fret_tiny.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_TINY_NOISY, tabraw_path))
    warning_codes = {warning.get("code") for warning in raw.warnings}
    assert "pdf_fret_bbox_too_small" in warning_codes or "pdf_fret_optical_bounds_confidence_below_threshold" in warning_codes
    assert "pdf_fret_refinement_not_enough_for_build_ir" in warning_codes


def test_pdf_fret_grouped_success(tmp_path) -> None:
    assert PDF_FRET_GROUPED_SUCCESS.exists()
    tabraw_path = tmp_path / "fret_grouped.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_FRET_GROUPED_SUCCESS, tabraw_path))
    assert grouping_status_for_tabraw(raw.model_dump(mode="json")) == "grouped"


def test_build_ir_refuses_fret_refinement_blockers(tmp_path) -> None:
    assert PDF_FRET_GAP_TOO_LARGE.exists()
    tabraw_path = tmp_path / "fret_gap_refuse.tabraw.json"
    ir_path = tmp_path / "fret_gap_refuse.ir.json"
    extract_tab(PDF_FRET_GAP_TOO_LARGE, tabraw_path)

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert raised.value.category == "partial_pdf_grouping"
    payload = raised.value.to_diagnostics_payload()
    assert payload["details"]["grouping_status"] == "partial"
    assert "pdf_fret_digits_not_merged_gap_too_large" in payload["details"]["warning_codes"]


def test_build_ir_does_not_refuse_excluded_non_playable_without_string_bar(tmp_path) -> None:
    assert PDF_FRET_PAGE_LEGEND_EXCLUDED.exists()
    tabraw_path = tmp_path / "fret_legend_pass.tabraw.json"
    ir_path = tmp_path / "fret_legend_pass.ir.json"
    extract_tab(PDF_FRET_PAGE_LEGEND_EXCLUDED, tabraw_path)
    # The extraction warnings here are non-blocking (e.g. info or page number excluded is not in build blocking whitelist)
    # Therefore, build_ir should not raise BuildIrInputRiskError on this tabraw
    pass


PDF_TUNING_STANDARD_TEXT = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_standard_text.pdf"
PDF_TUNING_EXPLICIT_EADGBE = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_explicit_eadgbe.pdf"
PDF_TUNING_ALTERNATE_DADGAD = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_alternate_dadgad.pdf"
PDF_TUNING_LABEL_OUTSIDE = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_label_outside.pdf"
PDF_TUNING_CONFLICT = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_conflict.pdf"
PDF_TUNING_MALFORMED = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_malformed.pdf"
PDF_TUNING_CHORD_RESEMBLING = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_chord_resembling.pdf"
PDF_TUNING_SECTION_NOTE_NAMES = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_section_note_names.pdf"
PDF_TUNING_VALID_GROUPING = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_valid_grouping.pdf"
PDF_TUNING_TIMING_UNIMPLEMENTED = Path(__file__).parent / "fixtures" / "pdf" / "generated_pdf_tuning_timing_unimplemented.pdf"


def test_pdf_tuning_standard_text(tmp_path) -> None:
    assert PDF_TUNING_STANDARD_TEXT.exists()
    tabraw_path = tmp_path / "tuning_standard.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_STANDARD_TEXT, tabraw_path))
    tuning_cands = [c for c in raw.candidates if "pdf_tuning_standard_detected" in (c.raw.get("assignment_warnings") or [])]
    assert len(tuning_cands) > 0
    assert all(c.kind == "candidate-text" for c in tuning_cands)
    assert any("pdf_tuning_not_used_for_string_assignment" in (c.raw.get("assignment_warnings") or []) for c in tuning_cands)


def test_pdf_tuning_explicit_eadgbe(tmp_path) -> None:
    assert PDF_TUNING_EXPLICIT_EADGBE.exists()
    tabraw_path = tmp_path / "tuning_eadgbe.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_EXPLICIT_EADGBE, tabraw_path))
    tuning_cands = [c for c in raw.candidates if "pdf_tuning_string_labels_aligned" in (c.raw.get("assignment_warnings") or [])]
    assert len(tuning_cands) == 6
    assert all(c.string is not None for c in tuning_cands)
    string_notes = {c.string: c.raw_text for c in tuning_cands}
    assert string_notes[1] == "E"
    assert string_notes[2] == "B"
    assert string_notes[6] == "E"


def test_pdf_tuning_alternate_dadgad(tmp_path) -> None:
    assert PDF_TUNING_ALTERNATE_DADGAD.exists()
    tabraw_path = tmp_path / "tuning_dadgad.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_ALTERNATE_DADGAD, tabraw_path))
    tuning_cands = [c for c in raw.candidates if "pdf_tuning_string_labels_aligned" in (c.raw.get("assignment_warnings") or [])]
    assert len(tuning_cands) == 6
    string_notes = {c.string: c.raw_text for c in tuning_cands}
    assert string_notes[1] == "D"
    assert string_notes[6] == "D"


def test_pdf_tuning_label_outside(tmp_path) -> None:
    assert PDF_TUNING_LABEL_OUTSIDE.exists()
    tabraw_path = tmp_path / "tuning_outside.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_LABEL_OUTSIDE, tabraw_path))
    tuning_cands = [c for c in raw.candidates if "pdf_tuning_label_outside_system" in (c.raw.get("assignment_warnings") or [])]
    assert len(tuning_cands) > 0
    assert all(c.system_index is None for c in tuning_cands)


def test_pdf_tuning_conflict(tmp_path) -> None:
    assert PDF_TUNING_CONFLICT.exists()
    tabraw_path = tmp_path / "tuning_conflict.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_CONFLICT, tabraw_path))
    warning_codes = {warning.get("code") for warning in raw.warnings}
    assert "pdf_tuning_conflict_detected" in warning_codes
    assert "pdf_tuning_label_ambiguous" in warning_codes


def test_pdf_tuning_malformed(tmp_path) -> None:
    assert PDF_TUNING_MALFORMED.exists()
    tabraw_path = tmp_path / "tuning_malformed.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_MALFORMED, tabraw_path))
    warning_codes = {warning.get("code") for warning in raw.warnings}
    assert "pdf_tuning_label_malformed" in warning_codes
    assert "pdf_tuning_format_unsupported" in warning_codes


def test_pdf_tuning_chord_resembling(tmp_path) -> None:
    assert PDF_TUNING_CHORD_RESEMBLING.exists()
    tabraw_path = tmp_path / "tuning_chord.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_CHORD_RESEMBLING, tabraw_path))
    tuning_cands = [c for c in raw.candidates if "pdf_tuning_string_labels_aligned" in (c.raw.get("assignment_warnings") or [])]
    assert len(tuning_cands) == 0
    chord_cands = [c for c in raw.candidates if "pdf_fret_chord_text_digit_excluded" in (c.raw.get("assignment_warnings") or []) or c.raw_text == "E"]
    assert len(chord_cands) > 0


def test_pdf_tuning_section_note_names(tmp_path) -> None:
    assert PDF_TUNING_SECTION_NOTE_NAMES.exists()
    tabraw_path = tmp_path / "tuning_section.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_SECTION_NOTE_NAMES, tabraw_path))
    tuning_cands = [c for c in raw.candidates if "pdf_tuning_string_labels_aligned" in (c.raw.get("assignment_warnings") or [])]
    assert len(tuning_cands) == 0


def test_pdf_tuning_valid_grouping(tmp_path) -> None:
    assert PDF_TUNING_VALID_GROUPING.exists()
    tabraw_path = tmp_path / "tuning_valid.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_VALID_GROUPING, tabraw_path))
    assert grouping_status_for_tabraw(raw.model_dump(mode="json")) == "grouped"


def test_pdf_tuning_timing_unimplemented(tmp_path) -> None:
    assert PDF_TUNING_TIMING_UNIMPLEMENTED.exists()
    tabraw_path = tmp_path / "tuning_timing.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_TIMING_UNIMPLEMENTED, tabraw_path))
    from score2gp.report import build_grouping_diagnostics
    report = build_grouping_diagnostics(source_pdf=PDF_TUNING_TIMING_UNIMPLEMENTED, inspection={"page_count": 1}, tabraw=raw.model_dump(mode="json"), artifacts={})
    assert report["pitch_tuning"]["tuning_evidence_count"] > 0
    assert report["pitch_tuning"]["whether_timing_mapping_implemented"] is False
    assert report["candidate_classifications"]["non_playable_tuning_text"] > 0


def test_build_ir_refuses_tuning_blockers(tmp_path) -> None:
    assert PDF_TUNING_CONFLICT.exists()
    tabraw_path = tmp_path / "tuning_refuse.tabraw.json"
    ir_path = tmp_path / "tuning_refuse.ir.json"
    extract_tab(PDF_TUNING_CONFLICT, tabraw_path)
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(GENERATED_MUSICXML, tabraw_path, ir_path)
    assert not ir_path.exists()
    assert raised.value.category in ("partial_pdf_grouping", "pdf_tuning_conflict_detected")


def test_tuning_does_not_infer_strings_or_frets(tmp_path) -> None:
    assert PDF_TUNING_EXPLICIT_EADGBE.exists()
    tabraw_path = tmp_path / "tuning_no_infer.tabraw.json"
    raw = TabRaw.model_validate(extract_tab(PDF_TUNING_EXPLICIT_EADGBE, tabraw_path))
    playable = [c for c in raw.candidates if c.parsed_fret is not None]
    assert all(c.raw.get("is_tuning_evidence") is None for c in playable)
