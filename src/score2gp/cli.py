from __future__ import annotations



import json

import subprocess

import sys

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





def _format_diagnostics_report(data: dict) -> str:

    lines = []

    lines.append("================================================================================")

    lines.append("OMR CONSOLIDATED DIAGNOSTICS REPORT")

    lines.append("================================================================================")

    lines.append(f"Source File: {data.get('source', 'Unknown')}")

    lines.append(f"Recognition Mode: {data.get('recognition_mode', 'Unknown')}")

    lines.append("")



    semantic_cands = data.get("semantic_candidates", [])

    outcomes = data.get("read_only_recognition_outcomes", [])

    timeline_preview = data.get("timeline_preview", [])



    staves = data.get("staff_geometry", [])

    if not staves:

        staves_set = set()

        for o in outcomes + semantic_cands + timeline_preview:

            p = o.get("page_index")

            sy = o.get("system_index")

            st = o.get("staff_index")

            if p is not None and sy is not None and st is not None:

                staves_set.add((p, sy, st))

        staves = [{"page_index": p, "system_index": sy, "staff_index": st} for p, sy, st in sorted(staves_set)]



    for staff in staves:

        p, sy, st = staff.get("page_index"), staff.get("system_index"), staff.get("staff_index")

        lines.append("--------------------------------------------------------------------------------")

        lines.append(f"STAFF INDEX SUMMARY: Page {p} | System {sy} | Staff {st}")

        lines.append("--------------------------------------------------------------------------------")



        sem = next((s for s in semantic_cands if s.get("page_index") == p and s.get("system_index") == sy and s.get("staff_index") == st), {})



        clef_info = sem.get("logical_clef", {})

        clef_text = "Unknown"

        if clef_info:

            status = clef_info.get("status")

            kind = (clef_info.get("clef_kind") or "").capitalize()

            if status == "logical_clef_candidate":

                clef_text = f"{kind} (Detected)"

            elif status == "assumed_default":

                clef_text = f"{kind} (Assumed)"

            elif status == "logical_clef_missing":

                clef_text = "Missing"

            elif status == "logical_clef_ambiguous":

                clef_text = "Ambiguous"

            else:

                clef_text = f"{kind} ({status})"

        lines.append(f"Clef: {clef_text}")



        key_info = sem.get("logical_key_signature", {})

        key_text = "Unknown"

        if key_info:

            if key_info.get("status") == "assumed_default":

                key_text = f"{key_info.get('key_name', 'C Major')} (Assumed)"

            else:

                key_text = key_info.get("key_name", "Unknown")

        else:

            key_text = "C Major"

        lines.append(f"Key Signature: {key_text}")

        lines.append("")



        staff_outcomes = [o for o in outcomes if o.get("page_index") == p and o.get("system_index") == sy and o.get("staff_index") == st]



        qn = sum(1 for o in staff_outcomes if o.get("symbol_type") == "quarter_note_candidate")

        hn = sum(1 for o in staff_outcomes if o.get("symbol_type") == "half_note_candidate")

        wn = sum(1 for o in staff_outcomes if o.get("symbol_type") == "whole_note_candidate")



        qr = sum(1 for o in staff_outcomes if o.get("symbol_type") == "quarter_rest_candidate") + len(sem.get("quarter_rests", []))

        hr = sum(1 for o in staff_outcomes if o.get("symbol_type") == "half_rest_candidate") + len(sem.get("half_rests", []))

        wr = sum(1 for o in staff_outcomes if o.get("symbol_type") == "whole_rest_candidate") + len(sem.get("whole_rests", []))



        lines.append("Note / Rest Candidates:")

        lines.append(f"- Quarter Notes: {qn}")

        lines.append(f"- Half Notes: {hn}")

        lines.append(f"- Whole Notes: {wn}")

        lines.append(f"- Quarter Rests: {qr}")

        lines.append(f"- Half Rests: {hr}")

        lines.append(f"- Whole Rests: {wr}")

        lines.append("")



        staff_notes = sum(1 for o in staff_outcomes if "note_candidate" in o.get("symbol_type", ""))

        mapped = sum(1 for o in staff_outcomes if "note_candidate" in o.get("symbol_type", "") and o.get("clef_resolved_staff_pitch") is not None)

        skipped = staff_notes - mapped

        pct_mapped = (mapped / staff_notes * 100.0) if staff_notes > 0 else 0.0

        pct_skipped = (skipped / staff_notes * 100.0) if staff_notes > 0 else 0.0



        lines.append("Diatonic Pitch Coverage:")

        lines.append(f"- Total Note Candidates: {staff_notes}")

        lines.append(f"- Successfully Mapped: {mapped} ({pct_mapped:.1f}%)")

        lines.append(f"- Skipped/Failed: {skipped} ({pct_skipped:.1f}%)")

        lines.append("")



        lines.append("Timeline Preview:")

        staff_timelines = [t for t in timeline_preview if t.get("page_index") == p and t.get("system_index") == sy and t.get("staff_index") == st]

        if not staff_timelines:

            lines.append("None")

        else:

            for t in staff_timelines:

                for m in t.get("measures", []):

                    m_idx = m.get("measure_index")

                    m_valid = "[VALID]" if m.get("valid") else "[INVALID]"

                    lines.append(f"Measure {m_idx} {m_valid}")



                    voices = {}

                    for ev in m.get("events", []):

                        v = ev.get("voice")

                        voices.setdefault(v, []).append(ev)



                    for v in sorted(voices.keys()):

                        v_name = "Voice 1 (Upper)" if v == 1 else f"Voice {v} (Lower)"

                        ev_strs = []

                        for ev in voices[v]:

                            stype = ev.get("symbol_type", "")

                            dur = ev.get("duration_ticks", 0)

                            pitch = ev.get("resolved_pitch")

                            if "rest" in stype:

                                if stype == "padding_rest":

                                    name = "Padding Rest"

                                else:

                                    name = stype.replace("_candidate", "").replace("_", " ").title()

                                ev_strs.append(f"--[{name}, {dur}]--")

                            else:

                                pitch_str = pitch if pitch else "?"

                                ev_strs.append(f"--({pitch_str}, {dur})--")

                        lines.append(f"  {v_name}: |" + "|".join(ev_strs) + "|")

        lines.append("")

    return "\n".join(lines).strip()





@app.command("whole-note-recognition")

def whole_note_recognition_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture"),

    json_out: bool = typer.Option(False, "--json", help="Output machine-checkable JSON")

) -> None:

    """Expose read-only whole-note recognition outcomes. (Compatibility alias)"""

    from .whole_note_recogniser import run_recognition_on_file

    res = run_recognition_on_file(pdf)

    if not res:

        raise typer.Exit(1)



    if json_out:

        typer.echo(json.dumps(res, indent=2))

    else:

        typer.echo(_format_diagnostics_report(res))





@app.command("note-candidate-recognition")

def note_candidate_recognition_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture"),

    json_out: bool = typer.Option(False, "--json", help="Output machine-checkable JSON"),

    assume_treble_clef: bool = typer.Option(False, "--assume-treble-clef", help="Opt-in to assumed-treble pitch mapping")

) -> None:

    """Expose generic read-only note-candidate recognition outcomes."""

    from .whole_note_recogniser import run_recognition_on_file

    res = run_recognition_on_file(

        pdf,

        include_x_aligned_clusters=True,

        include_left_margin_candidates=True,

        include_flag_beam_candidates=True,

        include_ledger_line_candidates=True,

        assume_treble_clef=assume_treble_clef

    )

    if not res:

        raise typer.Exit(1)



    if json_out:

        typer.echo(json.dumps(res, indent=2))

    else:

        typer.echo(_format_diagnostics_report(res))





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





def _convert_exit_code_for_error(exc: Exception) -> int:

    """Maps preflight and layout exceptions/refusals to their respective exit codes.

    Exit codes:

    1: general parameter, missing input, path, or dependency failure

    2: PDF layout/grouping refusal (scanned PDF, missing barlines, unsupported layout)

    3: MusicXML timing or polyphony validation refusal

    4: ASCII/MusicXML alignment compatibility refusal or PDF-only unsafe grouping

    5: GP package writing or validation failure

    """

    if isinstance(exc, BuildIrInputRiskError):

        category = exc.category

        if category == "pdf_only_tab_grouping_unsafe":

            return 4

        elif category.startswith("ascii_") or "ascii" in category:

            return 4

        elif category in {

            "pdf_input_class_scanned_pdf_unsupported",

            "pdf_input_class_no_extractable_tab_geometry",

            "pdf_input_class_drawn_tab_requires_barlines",

            "missing_pdf_grouping",

        } or category.startswith("pdf_"):

            return 2

        elif category in {

            "musicxml_timing_risk",

            "musicxml_scoreir_polyphony_gate_refused",

        } or category.startswith("musicxml_"):

            return 3

    return 1





def _write_convert_report(

    report_path: Path,

    status: str,

    stage: str,

    exit_code: int,

    work_dir: Path,

    error_type: Optional[str] = None,

    refusal_code: Optional[str] = None,

    recommended_action: Optional[str] = None,

    output_path: Optional[Path] = None,

    output_written: bool = False,

    strict: bool = True,

    summary_counts: Optional[dict] = None,

    pdf_only_diagnostics: Optional[dict] = None,

    musicxml_sidecar_info: Optional[dict] = None,

) -> None:

    """Writes a consolidated, private-safe execution JSON report."""

    report = {

        "status": status,

        "stage": stage,

        "exit_code": exit_code,

        "error_type": error_type,

        "refusal_code": refusal_code,

        "recommended_action": recommended_action,

        "output_path": str(output_path) if output_path else None,

        "output_written": output_written,

        "work_dir": str(work_dir),

        "diagnostics_paths": {

            "warnings_json": str(work_dir / "warnings.json") if (work_dir / "warnings.json").exists() else None,

            "diagnostics_json": str(work_dir / "diagnostics.json") if (work_dir / "diagnostics.json").exists() else None,

            "grouping_diagnostics_html": str(work_dir / "grouping-diagnostics.html") if (work_dir / "grouping-diagnostics.html").exists() else None,

            "symbol_attachment_diagnostics_html": str(work_dir / "symbol-attachment-diagnostics.html") if (work_dir / "symbol-attachment-diagnostics.html").exists() else None,

        },

        "strict": strict,

        "summary_counts": summary_counts or {},

        "python_import_path": str(Path(__file__).parent.resolve()),

        "cli_executable_path": sys.executable,

        "musicxml_sidecar_info": musicxml_sidecar_info,

    }

    if pdf_only_diagnostics is not None:

        report["pdf_only_diagnostics"] = pdf_only_diagnostics

    try:

        report_path.parent.mkdir(parents=True, exist_ok=True)

        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    except Exception as exc:

        typer.echo(f"Warning: failed to write JSON report to {report_path}: {exc}", err=True)





@app.command("notation-whole-note-export")

def notation_whole_note_export_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one whole note"),

    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),

    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),

    assume_treble_clef: bool = typer.Option(False, "--assume-treble-clef", help="Assume a treble clef if no clef is detected"),

) -> None:

    """Explicit, opt-in CLI route for single standard-notation whole-note GP export (v0)."""

    from .whole_note_recogniser import run_recognition_on_file

    from .notation_bridge import NotationBridgeInputError, build_ir_from_notation_outcomes

    from .gp_package import write_gp



    result = run_recognition_on_file(pdf, assume_treble_clef=assume_treble_clef)

    if not result:

        typer.echo("Error: Recognition failed or returned no results.", err=True)

        raise typer.Exit(1)



    outcomes = result.get("read_only_recognition_outcomes", [])

    whole_cands = [o for o in outcomes if o.get("symbol_type") == "whole_note_candidate"]

    if len(whole_cands) > 1:

        typer.echo(f"Error: Found {len(whole_cands)} whole-note candidates but single-note export requires exactly 1", err=True)

        raise typer.Exit(1)



    try:

        score_ir = build_ir_from_notation_outcomes(outcomes)

    except NotationBridgeInputError as e:

        typer.echo(f"NotationBridgeInputError: {e}", err=True)

        raise typer.Exit(1)



    if score_ir.bars and score_ir.bars[0].events:

        evt = score_ir.bars[0].events[0]

        if evt.timing.notated_duration.value != "whole":

            typer.echo(f"Error: Bridge produced non-whole note ({evt.timing.notated_duration.value})", err=True)

            raise typer.Exit(1)



    if ir_out:

        ir_out.parent.mkdir(parents=True, exist_ok=True)

        ir_out.write_text(score_ir.model_dump_json(indent=2))



    out.parent.mkdir(parents=True, exist_ok=True)

    try:

        warnings = write_gp(score_ir, out)

        for w in warnings:

            typer.echo(f"warning: {w}", err=True)

    except Exception as e:

        typer.echo(f"GP Writer failed: {e}", err=True)

        raise typer.Exit(1)





@app.command("notation-half-note-export")

def notation_half_note_export_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one half note"),

    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),

    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),

) -> None:

    """Explicit, opt-in CLI route for single standard-notation half-note GP export (v0)."""

    from .whole_note_recogniser import run_recognition_on_file

    from .notation_bridge import NotationBridgeInputError, build_ir_from_notation_outcomes

    from .gp_package import write_gp



    result = run_recognition_on_file(pdf)

    if not result:

        typer.echo("Error: Recognition failed or returned no results.", err=True)

        raise typer.Exit(1)



    outcomes = result.get("read_only_recognition_outcomes", [])



    try:

        score_ir = build_ir_from_notation_outcomes(outcomes)

    except NotationBridgeInputError as e:

        typer.echo(f"NotationBridgeInputError: {e}", err=True)

        raise typer.Exit(1)



    # Extra check required by product: ensure it's actually a half note

    if score_ir.bars and score_ir.bars[0].events:

        evt = score_ir.bars[0].events[0]

        if evt.timing.notated_duration.value != "half":

            typer.echo(f"Error: Bridge produced non-half note ({evt.timing.notated_duration.value})", err=True)

            raise typer.Exit(1)



    if ir_out:

        ir_out.parent.mkdir(parents=True, exist_ok=True)

        ir_out.write_text(score_ir.model_dump_json(indent=2))



    out.parent.mkdir(parents=True, exist_ok=True)

    try:

        warnings = write_gp(score_ir, out)

        for w in warnings:

            typer.echo(f"warning: {w}", err=True)

    except Exception as e:

        typer.echo(f"GP Writer failed: {e}", err=True)

        raise typer.Exit(1)





@app.command("convert")

def convert_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to input born-digital vector PDF"),

    musicxml: Optional[Path] = typer.Option(None, "--musicxml", "-m", help="Path to matching MusicXML/MXL sidecar"),

    template: Optional[Path] = typer.Option(None, "--template", help="Path to optional template GP package"),

    out: Path = typer.Option(..., "--out", "-o", help="Path where the final .gp package will be written"),

    work_dir: Optional[Path] = typer.Option(None, "--work-dir", help="Directory for intermediate assets"),

    workdir: Optional[Path] = typer.Option(None, "--workdir", help="Alias for --work-dir", hidden=True),

    json_report: Optional[Path] = typer.Option(None, "--json-report", help="Path to write consolidated JSON execution summary"),

    strict: bool = typer.Option(True, "--strict/--no-strict", help="Enforce strict exit codes on preflight warnings or timing risks"),

    allow_remediation: bool = typer.Option(False, "--allow-remediation"),

    allow_skip_unboxed: bool = typer.Option(False, "--allow-skip-unboxed-systems"),

    optimize_fret_snapping: bool = typer.Option(False, "--optimize-fret-snapping", help="Enable Left-hand finger position/fret-snapping optimization"),

    pages: Optional[str] = typer.Option(None, "--pages", help="Explicit page range subset to process (e.g. '1-1' or '1-2')."),

    pdf_only_tab: bool = typer.Option(False, "--pdf-only-tab", help="Enable direct PDF-to-GP conversion without a MusicXML timing source"),

    editable_draft: bool = typer.Option(False, "--editable-draft", help="Generate an editable GP draft with defaulted rhythms and tuning from PDF tab extraction."),

    require_precise_timing: bool = typer.Option(False, "--require-precise-timing", help="Reject input if reliable precise timing evidence is missing."),

    ref_gp: Optional[Path] = typer.Option(None, "--ref-gp", help="Path to optional reference GP package for semantic comparison"),

) -> None:

    """Run the complete conversion pipeline: extraction, alignment, IR generation, and GP7 package writing."""

    actual_work_dir = work_dir or workdir

    if actual_work_dir is None:

        typer.echo("Error: --work-dir or --workdir option is required.", err=True)

        raise typer.Exit(1)



    pdf_only_diag_payload = None



    mxl_info = None

    if musicxml and musicxml.exists():

        import hashlib

        h = hashlib.sha256()

        with open(musicxml, "rb") as f:

            for b in iter(lambda: f.read(4096), b""): h.update(b)

        mxl_info = {

            "path": str(musicxml.resolve()),

            "sha256": h.hexdigest(),

            "generation_provenance": "supplied"

        }



    # Validate PDF file existence early

    if not pdf.exists():

        typer.echo(f"Error: Input PDF file not found at {pdf}", err=True)

        if json_report:

            _write_convert_report(

                report_path=json_report,

                status="failed",

                stage="argument-validation",

                exit_code=1,

                work_dir=actual_work_dir,

                error_type="FileNotFoundError",

                refusal_code="pdf_not_found",

                recommended_action=f"Provide a valid PDF path. Checked path: {pdf}",

                output_written=False,

                strict=strict,

                    musicxml_sidecar_info=mxl_info,

            )

        raise typer.Exit(1)



    actual_work_dir.mkdir(parents=True, exist_ok=True)

    warnings = []

    summary = {}



    # Stage 1: Inspect PDF and Extract Tab Candidates

    try:

        pdf_summary = inspect_pdf_file(pdf, actual_work_dir / "inspect")

        summary["pdf"] = pdf_summary

    except Exception as exc:

        warnings.append({"code": "pdf_inspect_failed", "message": f"PDF inspection failed: {str(exc)}", "severity": "error"})

        write_warnings(actual_work_dir / "warnings.json", warnings)

        write_conversion_report(actual_work_dir / "conversion-report.html", "score2gp conversion report", warnings, summary)

        if json_report:

            _write_convert_report(

                report_path=json_report,

                status="failed",

                stage="pdf-inspection",

                exit_code=1,

                work_dir=actual_work_dir,

                error_type=type(exc).__name__,

                refusal_code="pdf_inspect_failed",

                recommended_action=f"Ensure the PDF is a valid born-digital document. Error: {str(exc)}",

                output_written=False,

                strict=strict,

                    musicxml_sidecar_info=mxl_info,

            )

        raise typer.Exit(1)



    try:

        tabraw_path = actual_work_dir / "tab" / "tab_raw.json"

        tab_summary = extract_tab_file(pdf, tabraw_path)

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

        write_warnings(actual_work_dir / "warnings.json", warnings)

        write_conversion_report(actual_work_dir / "conversion-report.html", "score2gp conversion report", warnings, summary)

        if json_report:

            _write_convert_report(

                report_path=json_report,

                status="failed",

                stage="tab-extraction",

                exit_code=1,

                work_dir=actual_work_dir,

                error_type=type(exc).__name__,

                refusal_code="tab_extraction_failed",

                recommended_action=f"Ensure the PDF contains extractable vector tab geometry. Error: {str(exc)}",

                output_written=False,

                strict=strict,

                    musicxml_sidecar_info=mxl_info,

            )

        raise typer.Exit(1)

    # Stage 2: Check for MusicXML sidecar requirement

    if not pdf_only_tab and not editable_draft:

        if musicxml is None:

            typer.echo("Error: MusicXML sidecar path must be provided via --musicxml or -m.", err=True)

            warnings.append({

                "code": "missing_musicxml",

                "message": "MusicXML file is required for timing alignment and GP7 conversion.",

                "severity": "warning",

            })

            summary["blocking_reason"] = "missing_musicxml"

            write_warnings(actual_work_dir / "warnings.json", warnings)

            write_conversion_report(actual_work_dir / "conversion-report.html", "score2gp conversion report", warnings, summary)

            if json_report:

                _write_convert_report(

                    report_path=json_report,

                    status="refused",

                    stage="orchestration-gate",

                    exit_code=1,

                    work_dir=actual_work_dir,

                    error_type="ValueError",

                    refusal_code="missing_musicxml",

                    recommended_action="Provide a matching MusicXML sidecar before attempting build-ir.",

                    output_written=False,

                    strict=strict,

                    musicxml_sidecar_info=mxl_info,

                )

            raise typer.Exit(1)



        if not musicxml.exists():

            typer.echo(f"Error: MusicXML file not found at {musicxml}", err=True)

            warnings.append({

                "code": "musicxml_not_found",

                "message": f"Provided MusicXML file not found: {musicxml}",

                "severity": "error",

            })

            write_warnings(actual_work_dir / "warnings.json", warnings)

            write_conversion_report(actual_work_dir / "conversion-report.html", "score2gp conversion report", warnings, summary)

            if json_report:

                _write_convert_report(

                    report_path=json_report,

                    status="failed",

                    stage="argument-validation",

                    exit_code=1,

                    work_dir=actual_work_dir,

                    error_type="FileNotFoundError",

                    refusal_code="musicxml_not_found",

                    recommended_action=f"Provide a valid MusicXML path. Checked path: {musicxml}",

                    output_written=False,

                    strict=strict,

                    musicxml_sidecar_info=mxl_info,

                )

            raise typer.Exit(1)



    # Check if there are playable ASCII tab candidates in the TabRaw output

    has_ascii_candidates = any(

        c.get("parsed_fret") is not None and c.get("raw", {}).get("parser_version") == "ascii-tab.v0.1"

        for c in tab_summary.get("candidates", [])

    )



    alignment_path = None

    if has_ascii_candidates and not (pdf_only_tab or editable_draft):

        try:

            alignment_dir = actual_work_dir / "alignment"

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

            write_warnings(actual_work_dir / "warnings.json", warnings)

            write_conversion_report(actual_work_dir / "conversion-report.html", "score2gp conversion report", warnings, summary)

            if json_report:

                _write_convert_report(

                    report_path=json_report,

                    status="failed",

                    stage="ascii-alignment",

                    exit_code=1,

                    work_dir=actual_work_dir,

                    error_type=type(exc).__name__,

                    refusal_code="ascii_alignment_failed",

                    recommended_action=f"Verify alignment parameters. Error: {str(exc)}",

                    output_written=False,

                    strict=strict,

                    musicxml_sidecar_info=mxl_info,

                )

            raise typer.Exit(1)



    # Stage 3: ScoreIR Generation

    score = None

    diagnostics = None

    ir_path = actual_work_dir / "score.ir.json"

    diagnostics_path = actual_work_dir / "diagnostics.json"



    try:

        if pdf_only_tab or editable_draft:

            from .build_ir import build_ir_from_tabraw_only

            score, diagnostics = build_ir_from_tabraw_only(

                tabraw_path=tabraw_path,

                editable_draft=editable_draft,

                require_precise_timing=require_precise_timing,

            )

            score.to_json_file(ir_path)

        else:

            score, diagnostics = build_ir_with_diagnostics_from_files(

                musicxml_path=musicxml,

                tabraw_path=tabraw_path,

                out_path=ir_path,

                ascii_alignment_path=alignment_path,

                allow_remediation=allow_remediation,

                allow_skip_unboxed=allow_skip_unboxed,

                optimize_fret_snapping=optimize_fret_snapping,

                page_range=parse_page_range(pages),

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

            write_ascii_gate_diagnostics_html(actual_work_dir / "ascii-scoreir-gate-diagnostics.html", payload, json_path_ref="diagnostics.json")

        elif exc.stage == "musicxml-import":

            from .report import write_musicxml_timing_diagnostics_html

            write_musicxml_timing_diagnostics_html(actual_work_dir / "musicxml-timing-diagnostics.html", payload, json_path_ref="diagnostics.json")



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

        write_warnings(actual_work_dir / "warnings.json", warnings)

        write_conversion_report(actual_work_dir / "conversion-report.html", "score2gp conversion report", warnings, summary)



        exit_code = _convert_exit_code_for_error(exc)

        refusal_code = exc.category



        recommended_action = exc.details.get("remediation_hint")

        if not recommended_action:

            timing_refinement = payload.get("musicxml_timing_refinement", {})

            recommended_action = timing_refinement.get("remediation_hint")

        if not recommended_action:

            pdf_timing_mapping = payload.get("pdf_timing_mapping", {})

            recommended_action = pdf_timing_mapping.get("remediation_hint")

        if not recommended_action:

            recommended_action = "Check the intermediate diagnostics report for details."



        typer.echo(f"refusal_code: {refusal_code}", err=True)

        typer.echo(f"recommended_action: {recommended_action}", err=True)



        if json_report:

            if pdf_only_tab or editable_draft:

                pdf_only_diag_payload = {

                    "pdf_grouping_status": "refused",

                    "inferred_rhythm_status": None,

                    "gp_package_written": False,

                }

            _write_convert_report(

                report_path=json_report,

                status="refused",

                stage=exc.stage,

                exit_code=exit_code,

                work_dir=actual_work_dir,

                error_type=type(exc).__name__,

                refusal_code=refusal_code,

                recommended_action=recommended_action,

                output_written=False,

                strict=strict,

                    musicxml_sidecar_info=mxl_info,

                summary_counts={

                    "total_candidates": tab_summary.get("candidates_count", 0) if isinstance(tab_summary, dict) else 0,

                    "playable_candidates": sum(1 for c in tab_summary.get("candidates", []) if c.get("parsed_fret") is not None) if isinstance(tab_summary, dict) else 0

                },

                pdf_only_diagnostics=pdf_only_diag_payload

            )



        raise typer.Exit(exit_code)

    except Exception as exc:

        warnings.append({"code": "build_ir_failed", "message": f"ScoreIR generation failed: {str(exc)}", "severity": "error"})

        write_warnings(actual_work_dir / "warnings.json", warnings)

        write_conversion_report(actual_work_dir / "conversion-report.html", "score2gp conversion report", warnings, summary)

        if json_report:

            if pdf_only_tab or editable_draft:

                pdf_only_diag_payload = {

                    "pdf_grouping_status": "refused" if getattr(exc, "category", None) == "pdf_only_tab_grouping_unsafe" else "failed",

                    "inferred_rhythm_status": None,

                    "gp_package_written": False,

                }

            _write_convert_report(

                report_path=json_report,

                status="failed",

                stage="build-ir",

                exit_code=1,

                work_dir=actual_work_dir,

                error_type=type(exc).__name__,

                refusal_code="build_ir_failed",

                recommended_action=f"ScoreIR generation failed. Error: {str(exc)}",

                output_written=False,

                strict=strict,

                    musicxml_sidecar_info=mxl_info,

                pdf_only_diagnostics=pdf_only_diag_payload

            )

        raise typer.Exit(1)



    # Write regular symbol attachment diagnostics report on success

    if diagnostics is not None:

        from .report import write_symbol_attachment_diagnostics_html

        write_symbol_attachment_diagnostics_html(actual_work_dir / "symbol-attachment-diagnostics.html", diagnostics, score, tabraw_path=tabraw_path)



    if score is not None:

        try:

            temp_out = actual_work_dir / "temp_output.gp"

            gp_warnings = write_gp(score, temp_out, template)

            for w in gp_warnings:

                warnings.append({"code": "gp_write_warning", "message": w, "severity": "warning"})



            # Validate GP structure and GPIF XML well-formedness

            validation = validate_gp(temp_out)

            if validation["errors"]:

                raise ValueError(f"GP package structure validation failed: {validation['errors']}")



            # Move temp file to final output path atomically / cleanly

            import shutil

            shutil.move(str(temp_out), str(out))



            summary["gp_write"] = {

                "succeeded": True,

                "output_path": str(out),

                "warning_count": len(gp_warnings),

            }

        except Exception as exc:

            warnings.append({"code": "gp_write_failed", "message": f"Guitar Pro package writing failed: {str(exc)}", "severity": "error"})

            write_warnings(actual_work_dir / "warnings.json", warnings)

            write_conversion_report(actual_work_dir / "conversion-report.html", "score2gp conversion report", warnings, summary)

            if json_report:

                if pdf_only_tab or editable_draft:

                    pdf_only_diag_payload = {

                        "pdf_grouping_status": "safe",

                        "inferred_rhythm_status": "defaulted_placeholder" if editable_draft else "applied",

                        "gp_package_written": False,

                    }

                _write_convert_report(

                    report_path=json_report,

                    status="failed",

                    stage="gp-write",

                    exit_code=5,

                    work_dir=actual_work_dir,

                    error_type=type(exc).__name__,

                    refusal_code="gp_write_failed",

                    recommended_action=f"Check the ScoreIR output and template validity. Error: {str(exc)}",

                    output_written=False,

                    strict=strict,

                    musicxml_sidecar_info=mxl_info,

                    pdf_only_diagnostics=pdf_only_diag_payload

                )

            raise typer.Exit(5)



    # Write warnings and conversion-report

    write_warnings(actual_work_dir / "warnings.json", warnings)

    write_conversion_report(actual_work_dir / "conversion-report.html", "score2gp conversion report", warnings, summary)



    # Write successful JSON report

    if json_report:

        if pdf_only_tab or editable_draft:

            pdf_only_diag_payload = {

                "pdf_grouping_status": "safe",

                "inferred_rhythm_status": "defaulted_placeholder" if editable_draft else "applied",

                "gp_package_written": True,

            }

            if ref_gp:

                try:

                    from .gp_package import compare_gp

                    comp = compare_gp(ref_gp, out)

                    pdf_only_diag_payload["semantic_comparison"] = {

                        "matches": comp["matches"],

                        "differences": comp["differences"],

                    }

                except Exception as exc:

                    pdf_only_diag_payload["semantic_comparison"] = {

                        "matches": False,

                        "error": f"Semantic comparison failed: {exc}"

                    }

        _write_convert_report(

            report_path=json_report,

            status="success",

            stage="gp-write",

            exit_code=0,

            work_dir=actual_work_dir,

            output_path=out,

            output_written=True,

            strict=strict,

                    musicxml_sidecar_info=mxl_info,

            summary_counts={

                "bar_count": len(score.bars) if score else 0,

                "event_count": sum(len(bar.events) for bar in score.bars) if score else 0,

                "warning_count": len(score.warnings) if score else 0,

                "matched_candidate_count": diagnostics.matched_candidate_count if diagnostics else 0,

                "unmatched_musicxml_event_count": diagnostics.unmatched_musicxml_event_count if diagnostics else 0,

                "unmatched_tabraw_candidate_count": diagnostics.unmatched_tabraw_candidate_count if diagnostics else 0,

            },

            pdf_only_diagnostics=pdf_only_diag_payload

        )



    typer.echo(f"Success: GP package written to {out}")

    typer.echo(json.dumps({"workdir": str(actual_work_dir), "warnings": warnings}, indent=2))





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







def _run_single_note_export_command(pdf: Path, out: Path, ir_out: Path | None, expected_duration: str) -> None:

    from .whole_note_recogniser import run_recognition_on_file

    from .notation_bridge import NotationBridgeInputError, build_ir_from_notation_outcomes

    from .gp_package import write_gp

    import typer



    result = run_recognition_on_file(pdf, include_flag_beam_candidates=True)

    if not result:

        typer.echo("Error: Recognition failed or returned no results.", err=True)

        raise typer.Exit(1)



    outcomes = result.get("read_only_recognition_outcomes", [])



    try:

        score_ir = build_ir_from_notation_outcomes(outcomes)

    except NotationBridgeInputError as e:

        typer.echo(f"NotationBridgeInputError: {e}", err=True)

        raise typer.Exit(1)



    # Extra check required by product: ensure it's actually the expected duration and exactly one event

    if not score_ir.bars or not score_ir.bars[0].events:

        typer.echo("Error: Bridge produced no events", err=True)

        raise typer.Exit(1)



    if len(score_ir.bars[0].events) != 1:

        typer.echo(f"Error: Bridge produced {len(score_ir.bars[0].events)} events but single-note export requires exactly 1", err=True)

        raise typer.Exit(1)



    evt = score_ir.bars[0].events[0]

    if evt.timing.notated_duration.value != expected_duration:

        typer.echo(f"Error: Bridge produced non-{expected_duration} note ({evt.timing.notated_duration.value})", err=True)

        raise typer.Exit(1)



    if ir_out:

        ir_out.parent.mkdir(parents=True, exist_ok=True)

        ir_out.write_text(score_ir.model_dump_json(indent=2))



    out.parent.mkdir(parents=True, exist_ok=True)

    try:

        warnings = write_gp(score_ir, out)

        for w in warnings:

            typer.echo(f"warning: {w}", err=True)

    except Exception as e:

        typer.echo(f"GP Writer failed: {e}", err=True)

        raise typer.Exit(1)



@app.command("notation-quarter-note-export")

def notation_quarter_note_export_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one quarter note"),

    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),

    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),

) -> None:

    """Explicit, opt-in CLI route for single standard-notation quarter-note GP export (v0)."""

    _run_single_note_export_command(pdf, out, ir_out, "quarter")



@app.command("notation-eighth-note-export")

def notation_eighth_note_export_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one eighth note"),

    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),

    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),

) -> None:

    """Explicit, opt-in CLI route for single standard-notation eighth-note GP export (v0)."""

    _run_single_note_export_command(pdf, out, ir_out, "eighth")



@app.command("notation-sixteenth-note-export")

def notation_sixteenth_note_export_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one sixteenth note"),

    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),

    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),

) -> None:

    """Explicit, opt-in CLI route for single standard-notation sixteenth-note GP export (v0)."""

    _run_single_note_export_command(pdf, out, ir_out, "16th")



@app.command("notation-thirty-second-note-export")

def notation_thirty_second_note_export_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one thirty-second note"),

    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),

    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),

) -> None:

    """Explicit, opt-in CLI route for single standard-notation thirty-second-note GP export (v0)."""

    _run_single_note_export_command(pdf, out, ir_out, "32nd")



@app.command("notation-sixty-fourth-note-export")

def notation_sixty_fourth_note_export_command(

    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one sixty-fourth note"),

    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),

    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),

) -> None:

    """Explicit, opt-in CLI route for single standard-notation sixty-fourth-note GP export (v0)."""

    _run_single_note_export_command(pdf, out, ir_out, "64th")



if __name__ == "__main__":

    app()

