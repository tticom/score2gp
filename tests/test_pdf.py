from __future__ import annotations

import json
from pathlib import Path

from score2gp.build_ir import build_ir_from_files
from score2gp.ir import validate_score_ir_file
from score2gp.pdf import extract_tab, inspect_pdf
from score2gp.tabraw import TabRaw

GENERATED_PDF = Path("tests/fixtures/pdf/generated_tiny_tab.pdf")
GENERATED_MUSICXML = Path("tests/fixtures/musicxml/generated_tiny_tab.musicxml")
SCORELIKE_PDF = Path("tests/fixtures/pdf/generated_scorelike_tab.pdf")
SCORELIKE_MUSICXML = Path("tests/fixtures/musicxml/generated_scorelike_tab.musicxml")
UNEVEN_PDF = Path("tests/fixtures/pdf/generated_uneven_spacing_tab.pdf")
UNEVEN_MUSICXML = Path("tests/fixtures/musicxml/generated_uneven_spacing_tab.musicxml")


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
