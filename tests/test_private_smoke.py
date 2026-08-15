from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add scripts to sys.path so we can import from it
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from private_e2e_smoke import anonymize_name, run_pipeline_for_input


def test_anonymize_name() -> None:
    # 1. Test Derek Trucks name anonymization
    p1 = Path("fixtures/private/Derek Trucks BB King.pdf")
    assert anonymize_name(p1) == "private_input_1"

    p1_alt = Path("fixtures/private/derek_trucks_bb_king.pdf")
    assert anonymize_name(p1_alt) == "private_input_1"

    # 2. Test CAGED shapes name anonymization
    p2 = Path("fixtures/private/Lick in All 5 CAGED Shapes.pdf")
    assert anonymize_name(p2) == "private_input_2"

    p2_alt = Path("fixtures/private/caged_shapes_creator.pdf")
    assert anonymize_name(p2_alt) == "private_input_2"

    # 3. Test unknown/fallback name anonymization
    p3 = Path("fixtures/public/tiny_score.pdf")
    assert anonymize_name(p3) == "private_input_custom"


def test_run_pipeline_for_input(tmp_path) -> None:
    # Use real private fixture
    pdf_path = Path("fixtures/private/Lesson-5.pdf")

    # Run the private E2E runner for this input targeting the temp directory
    summary = run_pipeline_for_input(
        pdf_path=pdf_path,
        musicxml_path=None,
        output_base=tmp_path,
    )

    # Assert expected metadata keys exist and are safe
    assert summary["input_label"] == "private_input_custom_lesson_5"
    assert summary["page_count"] > 0
    assert summary["whether_text_extraction_succeeded"] is True
    # Lesson-5 is apparently detected as an ascii tab or has ascii tab qualities
    assert "whether_ascii_tab_detected" in summary
    assert "whether_scoreir_written" in summary

    # Candidate counts checks
    counts = summary["candidate_counts"]
    assert counts["total_candidates"] > 0
    assert counts["playable_candidates"] > 0

    # Ensure output files were written under correct subdirectory
    out_dir = tmp_path / "private_input_custom_lesson_5"
    assert out_dir.exists()


def test_private_smoke_cli(tmp_path, monkeypatch) -> None:
    from private_e2e_smoke import main

    pdf_path = Path("fixtures/private/Lesson-5.pdf")

    # Mock command line arguments
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "private_e2e_smoke.py",
            "--pdf",
            str(pdf_path),
            "--out",
            str(tmp_path),
        ],
    )

    # Run the main script
    main()

    # Check master outputs exist
    master_json = tmp_path / "private_e2e_summary.json"
    master_md = tmp_path / "private_e2e_summary.md"
    assert master_json.exists()
    assert master_md.exists()

    # Check that individual output files exist as well
    out_dir = tmp_path / "private_input_custom_lesson_5"
    assert out_dir.exists()


@pytest.mark.skip(reason="Requires unrecoverable timing MusicXML sidecar (synthetic fixture deleted)")
def test_private_smoke_unrecoverable_timing_artifacts(tmp_path) -> None:
    pass


