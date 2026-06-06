from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.gp_package import inspect_gp, validate_gp

ASCII_GATE_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_scoreir_gate.pdf")
ASCII_GATE_MUSICXML = Path("tests/fixtures/musicxml/ascii_scoreir_gate_simple.musicxml")


def test_orchestration_convert_success(tmp_path) -> None:
    workdir = tmp_path / "workdir"
    out_gp = tmp_path / "output.gp"

    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(ASCII_GATE_PDF),
            "--musicxml",
            str(ASCII_GATE_MUSICXML),
            "--out",
            str(out_gp),
            "--workdir",
            str(workdir),
        ],
    )

    assert result.exit_code == 0, result.output

    # Verify artifacts generated
    assert out_gp.exists()
    assert (workdir / "warnings.json").exists()
    assert (workdir / "conversion-report.html").exists()

    # Validate output GP
    validation = validate_gp(out_gp)
    assert validation["is_zip"] is True
    assert validation["xml_well_formed"] is True
    assert validation["errors"] == []

    summary = inspect_gp(out_gp)
    assert summary["tracks"] == ["Guitar"]
    assert summary["tempo"] == "84"
    assert summary["bar_count"] == 2


def test_orchestration_convert_missing_musicxml(tmp_path) -> None:
    workdir = tmp_path / "workdir"
    out_gp = tmp_path / "output.gp"

    result = CliRunner().invoke(
        app,
        [
            "convert",
            "--pdf",
            str(ASCII_GATE_PDF),
            "--out",
            str(out_gp),
            "--workdir",
            str(workdir),
        ],
    )

    assert result.exit_code == 1, result.output

    # GP file should not be created since it halts due to missing MusicXML
    assert not out_gp.exists()
    assert (workdir / "warnings.json").exists()
    assert (workdir / "conversion-report.html").exists()

    warnings = json.loads((workdir / "warnings.json").read_text(encoding="utf-8"))
    assert any(w["code"] == "missing_musicxml" for w in warnings)
