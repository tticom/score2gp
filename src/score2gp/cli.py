from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

import typer

from .gp_package import compare_gp, dumps_summary, inspect_gp, validate_gp, write_gp
from .ir import ScoreIR
from .pdf import extract_tab as extract_tab_file
from .pdf import inspect_pdf as inspect_pdf_file
from .report import write_conversion_report, write_warnings

app = typer.Typer(help="Inspectable PDF score to Guitar Pro conversion pipeline.")


@app.command("inspect-gp")
def inspect_gp_command(input_gp: Path) -> None:
    """Inspect a GP7-style zip package and summarize semantic features."""
    typer.echo(dumps_summary(inspect_gp(input_gp)))


@app.command("validate")
def validate_command(input_gp: Path) -> None:
    """Validate basic GP package structure and GPIF XML well-formedness."""
    result = validate_gp(input_gp)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))
    if result["errors"]:
        raise typer.Exit(1)


@app.command("compare")
def compare_command(expected_gp: Path, actual_gp: Path) -> None:
    """Compare semantic GP features rather than package bytes."""
    result = compare_gp(expected_gp, actual_gp)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))
    if not result["matches"]:
        raise typer.Exit(1)


@app.command("write-gp")
def write_gp_command(ir_json: Path, template: Optional[Path] = typer.Option(None), out: Path = typer.Option(...)) -> None:
    """Write a minimal GP7-style package from ScoreIR JSON."""
    score = ScoreIR.from_json_file(ir_json)
    warnings = write_gp(score, out, template)
    for warning in warnings:
        typer.echo(f"warning: {warning}", err=True)
    typer.echo(str(out))


@app.command("inspect-pdf")
def inspect_pdf_command(input_pdf: Path, out: Path = typer.Option(...)) -> None:
    """Render pages, detect vector/raster clues, and extract text coordinates."""
    typer.echo(json.dumps(inspect_pdf_file(input_pdf, out), indent=2))


@app.command("extract-tab")
def extract_tab_command(input_pdf: Path, out: Path = typer.Option(...)) -> None:
    """Write first-pass tab candidate text diagnostics."""
    typer.echo(json.dumps(extract_tab_file(input_pdf, out), indent=2))


@app.command("omr")
def omr_command(input_pdf: Path, out: Path = typer.Option(...), audiveris: Optional[Path] = typer.Option(None)) -> None:
    """Run optional Audiveris OMR if configured."""
    out.mkdir(parents=True, exist_ok=True)
    warnings = []
    if audiveris is None:
        warnings.append({"code": "audiveris-not-configured", "message": "Audiveris path was not provided."})
    else:
        log_path = out / "audiveris.log"
        try:
            completed = subprocess.run(
                [str(audiveris), "-batch", "-export", str(input_pdf)],
                cwd=out,
                text=True,
                capture_output=True,
                check=False,
            )
            log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
            if completed.returncode:
                warnings.append({"code": "audiveris-failed", "message": f"Audiveris exited {completed.returncode}."})
        except OSError as exc:
            warnings.append({"code": "audiveris-error", "message": str(exc)})
    (out / "warnings.json").write_text(json.dumps(warnings, indent=2), encoding="utf-8")
    typer.echo(json.dumps({"out": str(out), "warnings": warnings}, indent=2))


@app.command("build-ir")
def build_ir_command(
    musicxml: Optional[Path] = typer.Option(None),
    tab: Optional[Path] = typer.Option(None),
    out: Path = typer.Option(...),
) -> None:
    """Placeholder aligner: write a clear error until MusicXML/tab alignment exists."""
    raise typer.BadParameter(
        f"build-ir alignment is not implemented yet; received musicxml={musicxml} tab={tab} out={out}"
    )


@app.command("convert")
def convert_command(
    input_pdf: Path,
    template: Optional[Path] = typer.Option(None),
    out: Path = typer.Option(...),
    workdir: Path = typer.Option(...),
) -> None:
    """Run the current staged pipeline and report that full conversion is incomplete."""
    workdir.mkdir(parents=True, exist_ok=True)
    pdf_summary = inspect_pdf_file(input_pdf, workdir / "inspect")
    tab_summary = extract_tab_file(input_pdf, workdir / "tab")
    warnings = [
        {
            "code": "full-conversion-not-implemented",
            "message": "Current milestone stops before OMR/tab timing alignment and GP writing from PDF.",
        }
    ]
    write_warnings(workdir / "warnings.json", warnings)
    summary = {"pdf": pdf_summary, "tab": tab_summary, "requested_output": str(out), "template": str(template) if template else None}
    write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
    typer.echo(json.dumps({"workdir": str(workdir), "warnings": warnings}, indent=2))


if __name__ == "__main__":
    app()
