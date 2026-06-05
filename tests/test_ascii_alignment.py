from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.ascii_alignment import align_ascii_musicxml_files
from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_files
from score2gp.cli import app
from score2gp.pdf import extract_tab

ASCII_BARRED_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_barred.pdf")
ASCII_UNEVEN_TIMING_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_uneven_timing.pdf")
ASCII_NO_BARS_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_no_bars.pdf")
ASCII_MALFORMED_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_malformed.pdf")
COMPATIBLE_MUSICXML = Path("tests/fixtures/musicxml/ascii_alignment_compatible.musicxml")
AMBIGUOUS_MUSICXML = Path("tests/fixtures/musicxml/ascii_alignment_ambiguous.musicxml")
INCOMPATIBLE_MUSICXML = Path("tests/fixtures/musicxml/ascii_alignment_incompatible.musicxml")
OVERFULL_MUSICXML = Path("tests/fixtures/musicxml/audiveris_like_overfull_bar.musicxml")


def _extract(pdf_path: Path, tmp_path: Path) -> Path:
    tabraw_path = tmp_path / f"{pdf_path.stem}.tabraw.json"
    extract_tab(pdf_path, tabraw_path)
    return tabraw_path


def _align(tabraw_path: Path, musicxml_path: Path, tmp_path: Path):
    return align_ascii_musicxml_files(
        tabraw_path=tabraw_path,
        musicxml_path=musicxml_path,
        out_dir=tmp_path / f"{tabraw_path.stem}.alignment",
    )


def test_compatible_ascii_musicxml_pair_produces_alignment_diagnostics(tmp_path) -> None:
    tabraw_path = _extract(ASCII_BARRED_PDF, tmp_path)

    alignment = _align(tabraw_path, COMPATIBLE_MUSICXML, tmp_path)

    assert alignment.schema_version == "ascii-musicxml-alignment.v0.1"
    assert alignment.overall_status == "compatible"
    assert alignment.alignment_attempted is True
    assert alignment.scoreir_written is False
    assert alignment.summary_counts["ascii_candidates"] == 8
    assert alignment.summary_counts["musicxml_events"] == 8
    assert alignment.summary_counts["compatible_mappings"] == 8
    assert alignment.summary_counts["ambiguous_mappings"] == 0
    assert alignment.summary_counts["incompatible_mappings"] == 0
    assert {mapping.ascii_measure_segment_id for mapping in alignment.candidate_mappings} == {1, 2}
    assert all(mapping.onset_distance is not None for mapping in alignment.candidate_mappings)
    assert all(mapping.onset_distance <= alignment.tolerance for mapping in alignment.candidate_mappings)
    assert (tmp_path / f"{tabraw_path.stem}.alignment" / "ascii_musicxml_alignment.json").exists()
    assert (tmp_path / f"{tabraw_path.stem}.alignment" / "alignment-diagnostics.html").exists()


def test_ambiguous_ascii_musicxml_pair_reports_ambiguous_status(tmp_path) -> None:
    tabraw_path = _extract(ASCII_UNEVEN_TIMING_PDF, tmp_path)

    alignment = _align(tabraw_path, AMBIGUOUS_MUSICXML, tmp_path)

    assert alignment.overall_status == "ambiguous"
    assert alignment.summary_counts["ambiguous_mappings"] > 0
    assert any(
        "ambiguous_ascii_tab_timing" in mapping.warning_codes
        for mapping in alignment.candidate_mappings
    )


def test_incompatible_ascii_musicxml_pair_reports_incompatible_status(tmp_path) -> None:
    tabraw_path = _extract(ASCII_BARRED_PDF, tmp_path)

    alignment = _align(tabraw_path, INCOMPATIBLE_MUSICXML, tmp_path)

    assert alignment.overall_status == "incompatible"
    assert alignment.summary_counts["incompatible_mappings"] > 0
    assert any(
        "ascii_musicxml_onset_distance_exceeds_tolerance" in mapping.warning_codes
        for mapping in alignment.candidate_mappings
    )


def test_no_bar_ascii_pair_reports_unavailable_alignment(tmp_path) -> None:
    tabraw_path = _extract(ASCII_NO_BARS_PDF, tmp_path)

    alignment = _align(tabraw_path, COMPATIBLE_MUSICXML, tmp_path)

    assert alignment.overall_status == "unavailable"
    assert alignment.alignment_attempted is False
    assert alignment.summary_counts["unavailable_mappings"] == alignment.summary_counts["ascii_candidates"]
    assert "ascii_tab_timing_unavailable" in {warning.code for warning in alignment.warnings}


def test_musicxml_timing_risk_blocks_ascii_alignment_before_matching(tmp_path) -> None:
    tabraw_path = _extract(ASCII_BARRED_PDF, tmp_path)

    alignment = _align(tabraw_path, OVERFULL_MUSICXML, tmp_path)

    assert alignment.overall_status == "unavailable"
    assert alignment.alignment_attempted is False
    assert alignment.candidate_mappings == []
    assert "musicxml_timing_risk" in {warning.code for warning in alignment.warnings}
    assert alignment.musicxml_timing_issues[0]["code"] == "musicxml-overfull-bar"


def test_cli_writes_ascii_musicxml_alignment_sidecar(tmp_path) -> None:
    tabraw_path = _extract(ASCII_BARRED_PDF, tmp_path)
    out_dir = tmp_path / "cli-alignment"

    result = CliRunner().invoke(
        app,
        [
            "align-ascii-musicxml",
            "--tab",
            str(tabraw_path),
            "--musicxml",
            str(COMPATIBLE_MUSICXML),
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads((out_dir / "ascii_musicxml_alignment.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "ascii-musicxml-alignment.v0.1"
    assert payload["overall_status"] == "compatible"
    assert (out_dir / "alignment-diagnostics.html").exists()


def test_build_ir_still_refuses_ascii_without_alignment_sidecar(tmp_path) -> None:
    tabraw_path = _extract(ASCII_BARRED_PDF, tmp_path)
    ir_path = tmp_path / "ascii.ir.json"

    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(COMPATIBLE_MUSICXML, tabraw_path, ir_path)

    assert not ir_path.exists()
    assert raised.value.category == "pdf_input_class_ascii_tab_requires_alignment"


@pytest.mark.parametrize(
    ("pdf_path", "musicxml_path", "expected_status", "expected_category"),
    [
        (ASCII_NO_BARS_PDF, COMPATIBLE_MUSICXML, "unavailable", "ascii_alignment_status_unavailable"),
        (ASCII_UNEVEN_TIMING_PDF, AMBIGUOUS_MUSICXML, "ambiguous", "ascii_alignment_status_ambiguous"),
        (ASCII_BARRED_PDF, INCOMPATIBLE_MUSICXML, "incompatible", "ascii_alignment_status_incompatible"),
    ],
)
def test_build_ir_refuses_unsafe_ascii_alignment_sidecars(
    tmp_path,
    pdf_path: Path,
    musicxml_path: Path,
    expected_status: str,
    expected_category: str,
) -> None:
    tabraw_path = _extract(pdf_path, tmp_path)
    alignment = _align(tabraw_path, musicxml_path, tmp_path)
    alignment_path = tmp_path / f"{tabraw_path.stem}.alignment" / "ascii_musicxml_alignment.json"
    ir_path = tmp_path / "ascii.ir.json"

    assert alignment.overall_status == expected_status
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(musicxml_path, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    assert raised.value.category == expected_category


def test_build_ir_refuses_broad_compatible_ascii_alignment_proof_outside_tiny_gate(tmp_path) -> None:
    tabraw_path = _extract(ASCII_BARRED_PDF, tmp_path)
    alignment = _align(tabraw_path, COMPATIBLE_MUSICXML, tmp_path)
    alignment_path = tmp_path / f"{tabraw_path.stem}.alignment" / "ascii_musicxml_alignment.json"
    ir_path = tmp_path / "ascii.ir.json"

    assert alignment.overall_status == "compatible"
    with pytest.raises(BuildIrInputRiskError) as raised:
        build_ir_from_files(COMPATIBLE_MUSICXML, tabraw_path, ir_path, ascii_alignment_path=alignment_path)

    assert not ir_path.exists()
    assert raised.value.category == "ascii_polyphony_not_supported"
    assert "ascii_polyphony_not_supported" in raised.value.details["reason_codes"]


def test_malformed_ascii_grouping_remains_unavailable_for_alignment(tmp_path) -> None:
    tabraw_path = _extract(ASCII_MALFORMED_PDF, tmp_path)

    alignment = _align(tabraw_path, COMPATIBLE_MUSICXML, tmp_path)

    assert alignment.overall_status == "unavailable"
    assert "partial_ascii_tab_grouping" in {warning.code for warning in alignment.warnings}
