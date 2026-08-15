
import pytest
from pathlib import Path

def _get_dynamic_private_pdf():
    pdfs = list(Path("fixtures/private").glob("*.pdf"))
    if not pdfs:
        pytest.skip("No private fixtures found", allow_module_level=True)
    return pdfs[0]

def _get_dynamic_private_musicxml():
    xmls = list(Path("fixtures/private").glob("*.musicxml"))
    if not xmls:
        # Fallback to pdf just so Path doesn't fail, test will likely skip or fail gracefully
        return _get_dynamic_private_pdf()
    return xmls[0]

from pathlib import Path
from typer.testing import CliRunner
from score2gp.cli import app
from score2gp.notation_omr.pipeline import run_recognition_on_file


def test_run_recognition_on_file_public_pdf() -> None:
    pdf_path = _get_dynamic_private_pdf()
    assert pdf_path.exists()

    result = run_recognition_on_file(
        pdf_path,
        include_flag_beam_candidates=True,
        assume_treble_clef=True,
    )
    assert result is not None
    assert isinstance(result, dict)
    assert "read_only_recognition_outcomes" in result
    assert "semantic_candidates" in result
    assert "staff_geometry" in result
    assert "timeline_preview" in result


def test_run_recognition_on_file_nonexistent_returns_none(tmp_path: Path) -> None:
    missing_pdf = tmp_path / "nonexistent.pdf"
    result = run_recognition_on_file(missing_pdf)
    assert result is None


def test_convert_with_generated_sidecar_end_to_end(tmp_path: Path) -> None:
    pdf_path = _get_dynamic_private_pdf()
    sidecar_path = tmp_path / "sidecar.musicxml"
    out_gp = tmp_path / "output.gp"
    report_json = tmp_path / "report.json"
    workdir = tmp_path / "workdir"

    runner = CliRunner()
    # 1. Generate sidecar
    gen_res = runner.invoke(app, ["generate-sidecar", "--pdf", str(pdf_path), "--out", str(sidecar_path)])
    assert gen_res.exit_code == 0
    assert sidecar_path.exists()

    # 2. Run convert using generated sidecar
    conv_res = runner.invoke(
        app,
        [
            "convert",
            "--pdf",
            str(pdf_path),
            "--musicxml",
            str(sidecar_path),
            "--out",
            str(out_gp),
            "--work-dir",
            str(workdir),
            "--json-report",
            str(report_json),
        ],
    )
    # The convert command should produce a valid json report with status refusal/success rather than unhandled crash
    assert report_json.exists()
    assert conv_res.exit_code in (0, 2)
