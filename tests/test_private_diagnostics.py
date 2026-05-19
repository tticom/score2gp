from __future__ import annotations

import json
from pathlib import Path

from score2gp.private_diagnostics import SUMMARY_SCHEMA_VERSION, run_private_diagnostic_smoke


SCORELIKE_PDF = Path("tests/fixtures/pdf/generated_scorelike_tab.pdf")
SCORELIKE_MUSICXML = Path("tests/fixtures/musicxml/generated_scorelike_tab.musicxml")
OVERFULL_MUSICXML = Path("tests/fixtures/musicxml/audiveris_like_overfull_bar.musicxml")
UNSTRUCTURED_PDF = Path("tests/fixtures/pdf/generated_unstructured_tab_text.pdf")


def test_private_diagnostic_runner_writes_sanitized_public_fixture_summary(tmp_path) -> None:
    out_dir = tmp_path / "private_diagnostics" / "scorelike"

    summary = run_private_diagnostic_smoke(pdf_path=SCORELIKE_PDF, musicxml_path=SCORELIKE_MUSICXML, out_dir=out_dir)

    assert summary["schema_version"] == SUMMARY_SCHEMA_VERSION
    assert (out_dir / "extracted.tabraw.json").exists()
    assert (out_dir / "score.ir.json").exists()
    assert (out_dir / "diagnostics.json").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "summary.md").exists()

    assert summary["input"]["pdf_basename"] == SCORELIKE_PDF.name
    assert summary["musicxml"]["basename"] == SCORELIKE_MUSICXML.name
    assert summary["extraction"]["total_candidates"] == 22
    assert summary["extraction"]["playable_candidates"] == 11
    assert summary["extraction"]["non_playable_candidates"] == 11
    assert summary["extraction"]["inferred_system_count"] == 2
    assert summary["extraction"]["inferred_bar_count"] == 4
    assert summary["build_ir"]["ran"] is True
    assert summary["build_ir"]["matched_playable_candidate_count"] == 11
    assert summary["build_ir"]["ignored_non_playable_candidate_count"] == 11
    assert summary["build_ir"]["per_bar_quality_counts"] == {"good": 4, "poor": 0, "unknown": 0, "warning": 0}
    assert summary["validation"] == {"ran": True, "valid": True, "error_count": 0}

    serialized = json.dumps(summary, sort_keys=True)
    assert "raw_text" not in serialized
    assert "candidate_ids" not in serialized
    assert "pdf-p001" not in serialized
    assert "slide" not in serialized
    assert "Am" not in serialized


def test_private_diagnostic_runner_stops_after_extraction_without_musicxml(tmp_path) -> None:
    out_dir = tmp_path / "private_diagnostics" / "pdf_only"

    summary = run_private_diagnostic_smoke(pdf_path=SCORELIKE_PDF, musicxml_path=None, out_dir=out_dir)

    assert (out_dir / "extracted.tabraw.json").exists()
    assert not (out_dir / "score.ir.json").exists()
    assert not (out_dir / "diagnostics.json").exists()
    assert summary["build_ir"]["ran"] is False
    assert summary["build_ir"]["blocking_reason"] == "matching MusicXML timing input is missing; build-ir was not run"
    assert summary["validation"] == {"ran": False, "valid": False, "error_count": None}
    assert summary["suitability"]["recommended_next_action"] == "provide-matching-musicxml-before-build-ir"


def test_private_diagnostic_runner_summarizes_timing_risk_without_private_content(tmp_path) -> None:
    out_dir = tmp_path / "private_diagnostics" / "timing_risk"

    summary = run_private_diagnostic_smoke(pdf_path=SCORELIKE_PDF, musicxml_path=OVERFULL_MUSICXML, out_dir=out_dir)

    assert (out_dir / "extracted.tabraw.json").exists()
    assert not (out_dir / "score.ir.json").exists()
    assert not (out_dir / "diagnostics.json").exists()
    assert (out_dir / "build_error.json").exists()

    assert summary["build_ir"]["ran"] is False
    assert summary["build_ir"]["failed"] is True
    assert summary["build_ir"]["stage"] == "musicxml-import"
    assert summary["build_ir"]["error_category"] == "musicxml_timing_risk"
    assert summary["build_ir"]["musicxml_timing_issue_counts"] == {"musicxml-overfull-bar": 1}
    assert summary["build_ir"]["output_files_produced"] == {"tabraw": True, "score_ir": False, "diagnostics": False}
    assert "musicxml_timing_risk" in summary["suitability"]["recommendation_categories"]
    assert "alignment_not_attempted" in summary["suitability"]["recommendation_categories"]

    serialized = json.dumps(summary, sort_keys=True)
    assert "raw_text" not in serialized
    assert "candidate_ids" not in serialized
    assert "pdf-p001" not in serialized


def test_private_diagnostic_runner_distinguishes_pdf_grouping_failure(tmp_path) -> None:
    out_dir = tmp_path / "private_diagnostics" / "missing_grouping"

    summary = run_private_diagnostic_smoke(pdf_path=UNSTRUCTURED_PDF, musicxml_path=None, out_dir=out_dir)

    assert summary["extraction"]["total_candidates"] == 8
    assert summary["extraction"]["playable_candidates"] == 6
    assert summary["extraction"]["inferred_system_count"] == 0
    assert summary["extraction"]["inferred_bar_count"] == 0
    assert summary["extraction"]["candidates_with_string"] == 0
    assert summary["build_ir"]["ran"] is False
    assert "missing_pdf_grouping" in summary["suitability"]["recommendation_categories"]
    assert "alignment_not_attempted" in summary["suitability"]["recommendation_categories"]
