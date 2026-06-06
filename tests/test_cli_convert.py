from __future__ import annotations

import json
from pathlib import Path
from typer.testing import CliRunner
import pytest

from score2gp.cli import app, _convert_exit_code_for_error
from score2gp.build_ir import BuildIrInputRiskError

# Paths
TINY_PDF = Path("tests/fixtures/pdf/generated_tiny_tab.pdf")
TINY_MUSICXML = Path("tests/fixtures/musicxml/generated_tiny_tab.musicxml")

OVERFULL_MUSICXML = Path("tests/fixtures/musicxml/audiveris_like_overfull_bar.musicxml")
UNSTRUCTURED_PDF = Path("tests/fixtures/pdf/generated_unstructured_tab_text.pdf")


def test_cli_help() -> None:
    # 1. CLI help includes convert
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "convert" in result.output

    # 2. convert --help includes all required options
    result = CliRunner().invoke(app, ["convert", "--help"])
    assert result.exit_code == 0
    assert "--pdf" in result.output
    assert "--musicxml" in result.output
    assert "--out" in result.output
    assert "--work-dir" in result.output
    assert "--json-report" in result.output
    assert "--strict" in result.output


def test_cli_convert_missing_pdf(tmp_path) -> None:
    # 3. Missing PDF path exits 1
    workdir = tmp_path / "workdir"
    out_gp = tmp_path / "output.gp"
    non_existent_pdf = tmp_path / "non_existent.pdf"
    
    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(non_existent_pdf),
            "--musicxml",
            str(TINY_MUSICXML),
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
        ],
    )
    assert result.exit_code == 1
    assert "Input PDF file not found" in result.stderr


def test_cli_convert_missing_musicxml(tmp_path) -> None:
    # 4. Missing MusicXML path exits 1
    workdir = tmp_path / "workdir"
    out_gp = tmp_path / "output.gp"
    
    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(TINY_PDF),
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
        ],
    )
    assert result.exit_code == 1
    assert "MusicXML sidecar path must be provided" in result.stderr


def test_cli_convert_layout_refusal(tmp_path) -> None:
    # 5. Known PDF layout/grouping refusal exits 2 (using unstructured PDF)
    workdir = tmp_path / "workdir"
    out_gp = tmp_path / "output.gp"
    json_report = tmp_path / "report.json"
    
    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(UNSTRUCTURED_PDF),
            "--musicxml",
            str(TINY_MUSICXML),
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(json_report),
            "--strict",
        ],
    )
    assert result.exit_code == 2, result.output
    assert not out_gp.exists()
    
    # 10. Failure path writes JSON report but does not write GP
    assert json_report.exists()
    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert report["status"] == "refused"
    assert report["exit_code"] == 2
    assert report["refusal_code"] is not None


def test_cli_convert_timing_refusal(tmp_path) -> None:
    # 6. Known MusicXML timing/preflight refusal exits 3
    workdir = tmp_path / "workdir"
    out_gp = tmp_path / "output.gp"
    json_report = tmp_path / "report.json"
    
    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(TINY_PDF),
            "--musicxml",
            str(OVERFULL_MUSICXML),
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(json_report),
            "--strict",
        ],
    )
    assert result.exit_code == 3, result.output
    assert not out_gp.exists()
    
    assert json_report.exists()
    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert report["status"] == "refused"
    assert report["exit_code"] == 3
    assert "timing" in report["refusal_code"] or "timing" in report["stage"]


def test_cli_convert_success(tmp_path) -> None:
    # 9. Success path writes output GP and JSON report
    workdir = tmp_path / "workdir"
    out_gp = tmp_path / "output.gp"
    json_report = tmp_path / "report.json"
    
    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(TINY_PDF),
            "--musicxml",
            str(TINY_MUSICXML),
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(json_report),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_gp.exists()
    assert json_report.exists()
    
    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert report["status"] == "success"
    assert report["exit_code"] == 0
    assert report["summary_counts"]["bar_count"] > 0


def test_exit_code_mapping_helpers() -> None:
    # Test unit-level exit code mapping helper directly
    e1 = BuildIrInputRiskError(category="pdf_input_class_scanned_pdf_unsupported", stage="layout-gating", message="Scanned PDF")
    assert _convert_exit_code_for_error(e1) == 2

    e2 = BuildIrInputRiskError(category="missing_pdf_grouping", stage="layout-gating", message="Grouping missing")
    assert _convert_exit_code_for_error(e2) == 2

    e3 = BuildIrInputRiskError(category="musicxml_timing_risk", stage="musicxml-import", message="Timing risk")
    assert _convert_exit_code_for_error(e3) == 3

    e4 = BuildIrInputRiskError(category="ascii_alignment_status_unavailable", stage="ascii-scoreir-gate", message="ASCII gate")
    assert _convert_exit_code_for_error(e4) == 4

    e_other = ValueError("Some other error")
    assert _convert_exit_code_for_error(e_other) == 1


def test_existing_subcommands_still_work() -> None:
    # 11. Existing CLI subcommands still work (e.g. export-schema or validate)
    result = CliRunner().invoke(app, ["export-schema", "--help"])
    assert result.exit_code == 0
    assert "--out" in result.output
