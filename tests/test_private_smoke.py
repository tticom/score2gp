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
    # Use public synthetic fixtures
    pdf_path = Path("tests/fixtures/pdf/generated_ascii_tab_scoreir_gate.pdf")
    musicxml_path = Path("tests/fixtures/musicxml/ascii_scoreir_gate_simple.musicxml")

    # Run the private E2E runner for this input targeting the temp directory
    summary = run_pipeline_for_input(
        pdf_path=pdf_path,
        musicxml_path=musicxml_path,
        output_base=tmp_path,
    )

    # Assert expected metadata keys exist and are safe
    assert summary["input_label"] == "private_input_custom"
    assert summary["input_type_classification"] == "pdf-tab-musicxml"
    assert summary["page_count"] > 0
    assert summary["whether_text_extraction_succeeded"] is True
    assert summary["whether_ascii_tab_detected"] is True
    assert summary["whether_scoreir_written"] is False
    assert summary["whether_gp_written"] is False
    assert summary["primary_failure_refusal_reason"] == "missing_ascii_alignment_sidecar"

    # Redaction checks: verify no raw file path or title containing actual filenames exists in summary values
    summary_str = str(summary)
    assert "derek" not in summary_str.lower()
    assert "bb king" not in summary_str.lower()
    assert "caged" not in summary_str.lower()
    assert str(pdf_path.name) not in summary_str

    # Candidate counts checks
    counts = summary["candidate_counts"]
    assert counts["total_candidates"] > 0
    assert counts["playable_candidates"] > 0
    assert counts["non_playable_candidates"] >= 0

    # Ensure output files were written under correct subdirectory
    out_dir = tmp_path / "private_input_custom"
    assert out_dir.exists()
    assert (out_dir / "extracted.tabraw.json").exists()
    assert (out_dir / "build_error.json").exists()
    assert not (out_dir / "score.ir.json").exists()
    assert not (out_dir / "diagnostics.json").exists()
    assert not (out_dir / "smoke.gp").exists()


def test_private_smoke_cli(tmp_path, monkeypatch) -> None:
    from private_e2e_smoke import main

    pdf_path = Path("tests/fixtures/pdf/generated_ascii_tab_scoreir_gate.pdf")
    musicxml_path = Path("tests/fixtures/musicxml/ascii_scoreir_gate_simple.musicxml")

    # Mock command line arguments
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "private_e2e_smoke.py",
            "--pdf",
            str(pdf_path),
            "--musicxml",
            str(musicxml_path),
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
    out_dir = tmp_path / "private_input_custom"
    assert out_dir.exists()
    assert (out_dir / "extracted.tabraw.json").exists()
    assert (out_dir / "build_error.json").exists()

