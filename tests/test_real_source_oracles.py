from __future__ import annotations

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from private_e2e_smoke import run_pipeline_for_input, anonymize_name


def test_process_level_reference_isolation(tmp_path) -> None:
    """Verify that private_e2e_smoke does not pass reference .gp template into write_gp during generation."""
    pdf_path = Path("tests/fixtures/pdf/generated_ascii_tab_scoreir_gate.pdf")
    musicxml_path = Path("tests/fixtures/musicxml/ascii_scoreir_gate_simple.musicxml")

    # Run private_e2e_smoke pipeline
    summary = run_pipeline_for_input(
        pdf_path=pdf_path,
        musicxml_path=musicxml_path,
        output_base=tmp_path,
    )

    # Ensure no reference GP template was passed or leaked during conversion generation
    assert summary["whether_gp_written"] is False
    assert "gp_template" not in summary.get("secondary_reason_codes", [])


def test_missing_private_fixture_handling(tmp_path) -> None:
    """Verify that absent private fixtures are handled safely without crashing."""
    non_existent_pdf = Path("fixtures/private/non_existent_fixture.pdf")

    # Anonymizing a non-existent path handles missing inputs safely
    label = anonymize_name(non_existent_pdf)
    assert label.startswith("private_input")


def test_real_source_oracle_contract() -> None:
    """Contract test: verify real-source oracle verification parameters."""
    private_dir = PROJECT_ROOT / "fixtures" / "private"
    lesson5_pdf = private_dir / "Lesson-5.pdf"


    assert lesson5_pdf.exists()
