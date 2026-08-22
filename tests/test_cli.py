import json
from pathlib import Path
from unittest import mock
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.errors import HumanReadableConversionError

runner = CliRunner()

def test_build_ir_catches_human_readable_conversion_error(tmp_path: Path):
    musicxml = tmp_path / "test.musicxml"
    tabraw = tmp_path / "test.tabraw"
    musicxml.write_text("<score-partwise/>")
    tabraw.write_text("dummy tabraw")
    out = tmp_path / "out.json"

    with mock.patch("score2gp.cli.build_ir_with_diagnostics_from_files") as mock_build:
        mock_build.side_effect = HumanReadableConversionError("Unowned note", page=1, measure=2, voice=1)

        result = runner.invoke(app, [
            "build-ir",
            "--musicxml", str(musicxml),
            "--tabraw", str(tabraw),
            "--out", str(out)
        ])

        assert result.exit_code == 1
        assert "Error at Page 1, Measure 2, Voice 1: Unowned note" in result.stdout or "Error at Page 1, Measure 2, Voice 1: Unowned note" in result.stderr
