from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.sidecar_evaluator import (
    SidecarProvenanceManifest,
    validate_sidecar_manifest,
    _compute_sha256,
)

runner = CliRunner()

GOOD_SIDECAR = Path("tests/fixtures/musicxml/generated_tiny_tab.musicxml")


def test_mxs10_manifest_validation_success(tmp_path: Path) -> None:
    sha = _compute_sha256(GOOD_SIDECAR)
    assert sha is not None

    manifest_data = {
        "generator_tool": "musescore_manual",
        "generator_version": "4.2.1",
        "operator_id": "op_test_01",
        "operator_labor_minutes": 15.5,
        "sidecar_sha256": sha,
        "pdf_sha256": None,
        "eval_status": "passed",
    }
    manifest_path = tmp_path / "valid_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    result = validate_sidecar_manifest(manifest_path, GOOD_SIDECAR)
    assert isinstance(result, SidecarProvenanceManifest)
    assert result.generator_tool == "musescore_manual"
    assert result.generator_version == "4.2.1"
    assert result.operator_id == "op_test_01"
    assert result.operator_labor_minutes == 15.5
    assert result.sidecar_sha256 == sha
    assert result.eval_status == "passed"


def test_mxs10_manifest_rejection_mismatched_sha(tmp_path: Path) -> None:
    manifest_data = {
        "generator_tool": "photoscore_ultimate",
        "generator_version": "2024.1",
        "operator_id": "op_test_02",
        "operator_labor_minutes": 5.0,
        "sidecar_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "pdf_sha256": None,
        "eval_status": "passed",
    }
    manifest_path = tmp_path / "mismatched_sha_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(ValueError, match="Sidecar SHA-256 mismatch"):
        validate_sidecar_manifest(manifest_path, GOOD_SIDECAR)


def test_mxs10_manifest_rejection_unpassed_status(tmp_path: Path) -> None:
    sha = _compute_sha256(GOOD_SIDECAR)
    assert sha is not None

    manifest_data = {
        "generator_tool": "scanscore",
        "generator_version": "3.0",
        "operator_id": "op_test_03",
        "operator_labor_minutes": 10.0,
        "sidecar_sha256": sha,
        "pdf_sha256": None,
        "eval_status": "timing_invalid",
    }
    manifest_path = tmp_path / "unpassed_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(ValueError, match="Sidecar evaluation status is 'timing_invalid'"):
        validate_sidecar_manifest(manifest_path, GOOD_SIDECAR)


def test_mxs10_cli_convert_with_sidecar_manifest(tmp_path: Path) -> None:
    sha = _compute_sha256(GOOD_SIDECAR)
    assert sha is not None

    manifest_data = {
        "generator_tool": "pdftomusic_pro",
        "generator_version": "1.7.5",
        "operator_id": "op_cli_01",
        "operator_labor_minutes": 8.0,
        "sidecar_sha256": sha,
        "pdf_sha256": None,
        "eval_status": "passed",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    pdf_fixture = Path("tests/fixtures/pdf/generated_tiny_tab.pdf")
    out_gp = tmp_path / "output.gp"
    work_dir = tmp_path / "work"

    res = runner.invoke(
        app,
        [
            "convert",
            "--pdf",
            str(pdf_fixture),
            "--musicxml",
            str(GOOD_SIDECAR),
            "--sidecar-manifest",
            str(manifest_path),
            "--out",
            str(out_gp),
            "--work-dir",
            str(work_dir),
        ],
    )
    assert res.exit_code == 0, f"CLI output: {res.output}"
    assert out_gp.exists()

    report_html = work_dir / "conversion-report.html"
    assert report_html.exists()
    html_content = report_html.read_text(encoding="utf-8")
    assert "Sidecar Provenance Manifest" in html_content
    assert "pdftomusic_pro" in html_content
    assert "op_cli_01" in html_content
