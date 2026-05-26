from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

import typer

from .ascii_alignment import align_ascii_musicxml_files
from .build_ir import BuildIrInputRiskError, build_ir_with_diagnostics_from_files
from .batch import run_batch_pipeline
from .diagnostics import run_system_diagnostics
from .gp_package import compare_gp, dumps_summary, inspect_gp, validate_gp, write_gp, validate_roundtrip
from .ir import ScoreIR, compare_score_ir, export_scoreir_schema, validate_score_ir_file
from .pdf import extract_tab as extract_tab_file
from .pdf import inspect_pdf as inspect_pdf_file
from .report import write_conversion_report, write_warnings

def parse_page_range(pages_str: str | None) -> tuple[int, int] | None:
    if not pages_str:
        return None
    pages_str = pages_str.strip()
    if not pages_str:
        return None
    import re
    parts = re.split(r'[-–—,]', pages_str)
    if len(parts) == 1:
        try:
            val = int(parts[0].strip())
            return (val, val)
        except ValueError:
            pass
    elif len(parts) == 2:
        try:
            start = int(parts[0].strip())
            end = int(parts[1].strip())
            return (start, end)
        except ValueError:
            pass
    raise typer.BadParameter(f"Invalid page range format: '{pages_str}'. Use format like '1-1' or '1-2'.")

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


@app.command("export-schema")
def export_schema_command(out: Path = typer.Option(...)) -> None:
    """Export committed JSON schemas for intermediate contracts."""
    path = export_scoreir_schema(out)
    typer.echo(str(path))


@app.command("validate-ir")
def validate_ir_command(input_ir: Path) -> None:
    """Validate ScoreIR JSON with pydantic and semantic checks."""
    score, errors = validate_score_ir_file(input_ir)
    result = {
        "path": str(input_ir),
        "valid": score is not None and not errors,
        "schema_version": score.schema_version if score else None,
        "errors": errors,
    }
    typer.echo(json.dumps(result, indent=2, sort_keys=True))
    if errors:
        raise typer.Exit(1)


@app.command("compare-ir")
def compare_ir_command(expected_ir: Path, actual_ir: Path) -> None:
    """Compare semantic ScoreIR content rather than JSON bytes."""
    result = compare_score_ir(expected_ir, actual_ir)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))
    if not result["matches"]:
        raise typer.Exit(1)


@app.command("write-gp")
def write_gp_command(
    ir_json: Path,
    template: Optional[Path] = typer.Option(None),
    out: Path = typer.Option(...),
    target: str = typer.Option("GP7", "--target", help="Target Guitar Pro version profile (GP6, GP7, GP8)"),
) -> None:
    """Write a minimal GP7-style package from ScoreIR JSON or Booklet JSON."""
    score, errors = validate_score_ir_file(ir_json)
    if errors:
        for err in errors:
            typer.echo(f"error: {err}", err=True)
        raise typer.Exit(1)
    assert score is not None
    warnings = write_gp(score, out, template, target_version=target)
    for warning in warnings:
        typer.echo(f"warning: {warning}", err=True)
    typer.echo(str(out))


@app.command("validate-roundtrip")
def validate_roundtrip_command(ir_json: Path, gp_package: Path) -> None:
    """Verify that an exported GP7 package can be round-tripped back to ScoreIR."""
    score, errors = validate_score_ir_file(ir_json)
    if errors:
        for err in errors:
            typer.echo(f"error loading IR: {err}", err=True)
        raise typer.Exit(1)
    if not isinstance(score, ScoreIR):
        typer.echo("error: round-trip validation is only supported for single ScoreIR inputs", err=True)
        raise typer.Exit(1)

    result = validate_roundtrip(gp_package, score)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise typer.Exit(1)


@app.command("batch")
def batch_command(
    manifest: Path,
    workdir: Path,
    workers: int = 4,
    cache: bool = typer.Option(True, "--cache/--no-cache", help="Enable or disable incremental build caching"),
) -> None:
    """Execute concurrent batch pipeline processing on multiple score payloads."""
    result = run_batch_pipeline(manifest, workdir, max_workers=workers, use_cache=cache)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))
    if result["failure_count"] > 0:
        raise typer.Exit(1)


@app.command("diagnose")
def diagnose_command(
    manifest: Path,
    workdir: Path,
    workers: int = 4,
) -> None:
    """Execute concurrent batch pipeline processing on multiple score payloads with strict diagnostics and roundtrip checks."""
    result = run_system_diagnostics(manifest, workdir, max_workers=workers)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))
    if result["failure_count"] > 0 or result["roundtrip_failure_count"] > 0:
        raise typer.Exit(1)


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
    input_pdf = input_pdf.resolve()
    if audiveris is not None:
        audiveris = audiveris.resolve()
    out.mkdir(parents=True, exist_ok=True)
    out = out.resolve()
    warnings = []
    if audiveris is None:
        warnings.append({"code": "audiveris-not-configured", "message": "Audiveris path was not provided."})
    else:
        log_path = out / "audiveris.log"
        try:
            completed = subprocess.run(
                [str(audiveris), "-batch", "-export", "-output", str(out), str(input_pdf)],
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
    tabraw: Optional[Path] = typer.Option(None, "--tabraw", "--tab"),
    out: Path = typer.Option(...),
    diagnostics_out: Optional[Path] = typer.Option(None, "--diagnostics-out"),
    ascii_alignment: Optional[Path] = typer.Option(None, "--ascii-alignment"),
    allow_remediation: bool = typer.Option(False, "--allow-remediation"),
    allow_skip_unboxed: bool = typer.Option(False, "--allow-skip-unboxed-systems"),
    optimize_fret_snapping: bool = typer.Option(False, "--optimize-fret-snapping", help="Enable Left-hand finger position/fret-snapping optimization"),
    pages: Optional[str] = typer.Option(None, "--pages", help="Explicit page range subset to process (e.g. '1-1' or '1-2')."),
    max_digit_gap: float = typer.Option(2.0, "--max-digit-gap", help="Maximum horizontal point distance allowed to merge separate characters into multi-digit frets"),
    string_snap_tolerance: float = typer.Option(1.5, "--string-snap-tolerance", help="Vertical search window cushion in points around a horizontal string line vector for note snapping"),
    strip_technique_text: bool = typer.Option(False, "--strip-technique-text", help="Pre-filter layout strings matching known technique expressions before executing character collision matrix routines"),
) -> None:
    """Build a limited ScoreIR file from synthetic MusicXML plus TabRaw inputs."""
    if musicxml is None or tabraw is None:
        raise typer.BadParameter(
            "ScoreIR v0.1 is ready. This build-ir phase requires --musicxml and --tabraw/--tab "
            "and supports only the limited synthetic MusicXML + TabRaw alignment path."
        )
    try:
        score, diagnostics = build_ir_with_diagnostics_from_files(
            musicxml,
            tabraw,
            out,
            ascii_alignment,
            allow_remediation=allow_remediation,
            allow_skip_unboxed=allow_skip_unboxed,
            optimize_fret_snapping=optimize_fret_snapping,
            page_range=parse_page_range(pages),
            max_digit_gap=max_digit_gap,
            string_snap_tolerance=string_snap_tolerance,
            strip_technique_text=strip_technique_text,
        )
    except BuildIrInputRiskError as exc:
        payload = exc.to_diagnostics_payload()
        if exc.category == "missing_pdf_grouping" and tabraw is not None:
            payload["artifacts"] = _grouping_artifacts_for_tabraw(tabraw)
        if diagnostics_out is not None:
            diagnostics_out.parent.mkdir(parents=True, exist_ok=True)
            diagnostics_out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            if exc.stage == "ascii-scoreir-gate":
                from .report import write_ascii_gate_diagnostics_html
                html_path = diagnostics_out.parent / "ascii-scoreir-gate-diagnostics.html"
                write_ascii_gate_diagnostics_html(html_path, payload, json_path_ref=diagnostics_out.name)
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        raise typer.Exit(1) from exc
    if diagnostics_out is not None:
        diagnostics.to_json_file(diagnostics_out)
        from .report import write_symbol_attachment_diagnostics_html
        html_path = diagnostics_out.parent / "symbol-attachment-diagnostics.html"
        write_symbol_attachment_diagnostics_html(html_path, diagnostics, score, tabraw_path=tabraw)
    typer.echo(
        json.dumps(
            {
                "out": str(out),
                "diagnostics_out": str(diagnostics_out) if diagnostics_out else None,
                "schema_version": score.schema_version,
                "bar_count": len(score.bars),
                "event_count": sum(len(bar.events) for bar in score.bars),
                "warning_count": len(score.warnings),
                "matched_candidate_count": diagnostics.matched_candidate_count,
                "unmatched_musicxml_event_count": diagnostics.unmatched_musicxml_event_count,
                "unmatched_tabraw_candidate_count": diagnostics.unmatched_tabraw_candidate_count,
                "warnings": [warning.model_dump(mode="json", exclude_none=True) for warning in score.warnings],
            },
            indent=2,
            sort_keys=True,
        )
    )


@app.command("align-ascii-musicxml")
def align_ascii_musicxml_command(
    tab: Path = typer.Option(..., "--tab", "--tabraw"),
    musicxml: Path = typer.Option(...),
    out: Path = typer.Option(...),
) -> None:
    """Write diagnostic-only ASCII-tab-to-MusicXML onset compatibility evidence."""
    alignment = align_ascii_musicxml_files(tabraw_path=tab, musicxml_path=musicxml, out_dir=out)
    typer.echo(
        json.dumps(
            {
                "out": str(out),
                "schema_version": alignment.schema_version,
                "overall_status": alignment.overall_status,
                "alignment_attempted": alignment.alignment_attempted,
                "scoreir_written": alignment.scoreir_written,
                "summary_counts": alignment.summary_counts,
                "warning_codes": [warning.code for warning in alignment.warnings],
            },
            indent=2,
            sort_keys=True,
        )
    )


@app.command("convert")
def convert_command(
    input_pdf: Path,
    musicxml: Optional[Path] = typer.Option(None, "--musicxml", "-m"),
    template: Optional[Path] = typer.Option(None),
    out: Path = typer.Option(...),
    workdir: Path = typer.Option(...),
    allow_remediation: bool = typer.Option(False, "--allow-remediation"),
    allow_skip_unboxed: bool = typer.Option(False, "--allow-skip-unboxed-systems"),
    optimize_fret_snapping: bool = typer.Option(False, "--optimize-fret-snapping", help="Enable Left-hand finger position/fret-snapping optimization"),
    pages: Optional[str] = typer.Option(None, "--pages", help="Explicit page range subset to process (e.g. '1-1' or '1-2')."),
    max_digit_gap: float = typer.Option(2.0, "--max-digit-gap", help="Maximum horizontal point distance allowed to merge separate characters into multi-digit frets"),
    string_snap_tolerance: float = typer.Option(1.5, "--string-snap-tolerance", help="Vertical search window cushion in points around a horizontal string line vector for note snapping"),
    strip_technique_text: bool = typer.Option(False, "--strip-technique-text", help="Pre-filter layout strings matching known technique expressions before executing character collision matrix routines"),
) -> None:
    """Run the complete conversion pipeline: extraction, alignment, IR generation, and GP7 package writing."""
    workdir.mkdir(parents=True, exist_ok=True)
    warnings = []
    summary = {}

    # Stage 1: Inspect PDF and Extract Tab Candidates
    try:
        pdf_summary = inspect_pdf_file(input_pdf, workdir / "inspect")
        summary["pdf"] = pdf_summary
    except Exception as exc:
        warnings.append({"code": "pdf_inspect_failed", "message": f"PDF inspection failed: {str(exc)}", "severity": "error"})
        write_warnings(workdir / "warnings.json", warnings)
        write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
        raise typer.Exit(1)

    try:
        tabraw_path = workdir / "tab" / "tab_raw.json"
        tab_summary = extract_tab_file(
            input_pdf,
            tabraw_path,
            max_digit_gap=max_digit_gap,
            string_snap_tolerance=string_snap_tolerance,
            strip_technique_text=strip_technique_text,
        )
        summary["tab"] = tab_summary
        if tab_summary.get("warnings"):
            p_range = parse_page_range(pages)
            for w in tab_summary["warnings"]:
                if p_range is not None:
                    p_idx = w.get("page_index") or w.get("page_number")
                    if p_idx is not None:
                        try:
                            p = int(p_idx)
                            if not (p_range[0] <= p <= p_range[1]):
                                continue
                        except (ValueError, TypeError):
                            pass
                    else:
                        # Strip global/general suitability or layout warnings that are stale when page range constraints are active
                        code = w.get("code")
                        if code in {
                            "pdf_grouping_not_safe_for_build_ir",
                            "pdf_missing_pdf_grouping_blocks_build_ir",
                            "pdf_partial_grouping_one_system_unboxed",
                            "pdf_playable_candidate_requires_string_assignment",
                            "pdf_partial_grouping_with_playable_candidates",
                            "pdf_layout_detection_requires_manual_review",
                            "partial_pdf_grouping",
                            "missing_pdf_grouping",
                            "missing_pdf_barlines",
                            "incomplete_tab_staff",
                            "ambiguous_string_assignment",
                            "ambiguous_bar_assignment",
                            "pdf_system_detection_not_enough_for_build_ir",
                            "pdf_bar_detection_not_enough_for_build_ir",
                            "pdf_bar_box_construction_not_enough_for_build_ir",
                            "pdf_string_assignment_not_enough_for_build_ir",
                            "pdf_fret_refinement_not_enough_for_build_ir",
                            "pdf_pitch_tuning_diagnostics_not_enough_for_build_ir",
                            "pdf_timing_mapping_refused",
                            "pdf_timing_mapping_not_enough_for_build_ir",
                        } or (isinstance(code, str) and (code.startswith("pdf_") or code.startswith("ascii_"))):
                            continue
                if w not in warnings:
                    warnings.append(w)
    except Exception as exc:
        warnings.append({"code": "tab_extraction_failed", "message": f"Tab extraction failed: {str(exc)}", "severity": "error"})
        write_warnings(workdir / "warnings.json", warnings)
        write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
        raise typer.Exit(1)

    # Stage 2: Check for MusicXML Ingestion
    if musicxml is None:
        warnings.append({
            "code": "missing_musicxml",
            "message": "MusicXML file is required for timing alignment and GP7 conversion.",
            "severity": "warning",
        })
        summary["blocking_reason"] = "missing_musicxml"
        write_warnings(workdir / "warnings.json", warnings)
        write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
        typer.echo(json.dumps({"workdir": str(workdir), "warnings": warnings, "blocking_reason": "missing_musicxml"}, indent=2))
        return

    if not musicxml.exists():
        warnings.append({
            "code": "musicxml_not_found",
            "message": f"Provided MusicXML file not found: {musicxml}",
            "severity": "error",
        })
        write_warnings(workdir / "warnings.json", warnings)
        write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
        raise typer.Exit(1)

    # Check if there are playable ASCII tab candidates in the TabRaw output
    has_ascii_candidates = any(
        c.get("parsed_fret") is not None and c.get("raw", {}).get("parser_version") == "ascii-tab.v0.1"
        for c in tab_summary.get("candidates", [])
    )

    alignment_path = None
    if has_ascii_candidates:
        try:
            alignment_dir = workdir / "alignment"
            alignment = align_ascii_musicxml_files(
                tabraw_path=tabraw_path,
                musicxml_path=musicxml,
                out_dir=alignment_dir,
            )
            alignment_path = alignment_dir / "ascii_musicxml_alignment.json"
            summary["alignment"] = {
                "overall_status": alignment.overall_status,
                "alignment_attempted": alignment.alignment_attempted,
                "summary_counts": alignment.summary_counts,
            }
            if alignment.warnings:
                for w in alignment.warnings:
                    warnings.append(w.model_dump(mode="json", exclude_none=True))
        except Exception as exc:
            warnings.append({"code": "ascii_alignment_failed", "message": f"ASCII/MusicXML alignment failed: {str(exc)}", "severity": "error"})
            write_warnings(workdir / "warnings.json", warnings)
            write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
            raise typer.Exit(1)

    # Stage 3: ScoreIR Generation
    score = None
    diagnostics = None
    ir_path = workdir / "score.ir.json"
    diagnostics_path = workdir / "diagnostics.json"

    try:
        score, diagnostics = build_ir_with_diagnostics_from_files(
            musicxml_path=musicxml,
            tabraw_path=tabraw_path,
            out_path=ir_path,
            ascii_alignment_path=alignment_path,
            allow_remediation=allow_remediation,
            allow_skip_unboxed=allow_skip_unboxed,
            optimize_fret_snapping=optimize_fret_snapping,
            page_range=parse_page_range(pages),
            max_digit_gap=max_digit_gap,
            string_snap_tolerance=string_snap_tolerance,
            strip_technique_text=strip_technique_text,
        )
        summary["build_ir"] = {
            "ran": True,
            "failed": False,
            "bar_count": len(score.bars),
            "event_count": sum(len(bar.events) for bar in score.bars),
            "matched_candidate_count": diagnostics.matched_candidate_count,
            "unmatched_musicxml_event_count": diagnostics.unmatched_musicxml_event_count,
            "unmatched_tabraw_candidate_count": diagnostics.unmatched_tabraw_candidate_count,
        }
        if score.warnings:
            for w in score.warnings:
                warnings.append(w.model_dump(mode="json", exclude_none=True))
    except BuildIrInputRiskError as exc:
        payload = exc.to_diagnostics_payload()
        if exc.category == "missing_pdf_grouping":
            payload["artifacts"] = _grouping_artifacts_for_tabraw(tabraw_path)
        diagnostics_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        # If it was an ASCII gate refusal, render the appropriate HTML diagnostics
        if exc.stage == "ascii-scoreir-gate":
            from .report import write_ascii_gate_diagnostics_html
            write_ascii_gate_diagnostics_html(workdir / "ascii-scoreir-gate-diagnostics.html", payload, json_path_ref="diagnostics.json")

        warnings.append({
            "code": exc.category,
            "message": str(exc),
            "severity": "error"
        })
        summary["build_ir"] = {
            "ran": False,
            "failed": True,
            "error_category": exc.category,
            "message": str(exc),
        }
        write_warnings(workdir / "warnings.json", warnings)
        write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
        typer.echo(json.dumps({"workdir": str(workdir), "warnings": warnings, "build_ir_failed": True}, indent=2))
        return
    except Exception as exc:
        warnings.append({"code": "build_ir_failed", "message": f"ScoreIR generation failed: {str(exc)}", "severity": "error"})
        write_warnings(workdir / "warnings.json", warnings)
        write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
        raise typer.Exit(1)

    # Write regular symbol attachment diagnostics report on success
    if diagnostics is not None:
        from .report import write_symbol_attachment_diagnostics_html
        write_symbol_attachment_diagnostics_html(workdir / "symbol-attachment-diagnostics.html", diagnostics, score, tabraw_path=tabraw_path)

    # Stage 4: GP7 Package Writing
    if score is not None:
        try:
            gp_warnings = write_gp(score, out, template)
            for w in gp_warnings:
                warnings.append({"code": "gp_write_warning", "message": w, "severity": "warning"})
            summary["gp_write"] = {
                "succeeded": True,
                "output_path": str(out),
                "warning_count": len(gp_warnings),
            }
        except Exception as exc:
            warnings.append({"code": "gp_write_failed", "message": f"Guitar Pro package writing failed: {str(exc)}", "severity": "error"})
            write_warnings(workdir / "warnings.json", warnings)
            write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
            raise typer.Exit(1)

    # Write warnings and conversion-report
    write_warnings(workdir / "warnings.json", warnings)
    write_conversion_report(workdir / "conversion-report.html", "score2gp conversion report", warnings, summary)
    typer.echo(json.dumps({"workdir": str(workdir), "warnings": warnings}, indent=2))


def _grouping_artifacts_for_tabraw(tabraw_path: Path) -> dict[str, object]:
    base = tabraw_path.parent
    artifacts: dict[str, object] = {}
    grouping_html = base / "grouping-diagnostics.html"
    warnings = base / "warnings.json"
    overlays = base / "overlays"
    if grouping_html.exists():
        artifacts["grouping_diagnostics_html"] = str(grouping_html)
    if warnings.exists():
        artifacts["warnings"] = str(warnings)
    if overlays.exists():
        artifacts["overlay_images"] = [str(path) for path in sorted(overlays.glob("*-grouping.png"))]
    return artifacts


if __name__ == "__main__":
    app()
