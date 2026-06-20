from pathlib import Path

content = Path("src/score2gp/cli.py").read_text()
parts = content.split('if __name__ == "__main__":')

before_main = parts[0]
main_block = 'if __name__ == "__main__":' + parts[1].split('@app.command("notation-quarter-note-export")')[0]
commands_str = '@app.command("notation-quarter-note-export")' + parts[1].split('@app.command("notation-quarter-note-export")')[1]

helper = """
def _run_single_note_export_command(pdf: Path, out: Path, ir_out: Path | None, expected_duration: str) -> None:
    from .whole_note_recogniser import run_recognition_on_file
    from .notation_bridge import NotationBridgeInputError, build_ir_from_notation_outcomes
    from .gp_package import write_gp
    import typer

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
        
    # Extra check required by product: ensure it's actually the expected duration
    if score_ir.bars and score_ir.bars[0].events:
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
    \"\"\"Explicit, opt-in CLI route for single standard-notation quarter-note GP export (v0).\"\"\"
    _run_single_note_export_command(pdf, out, ir_out, "quarter")

@app.command("notation-eighth-note-export")
def notation_eighth_note_export_command(
    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one eighth note"),
    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),
    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),
) -> None:
    \"\"\"Explicit, opt-in CLI route for single standard-notation eighth-note GP export (v0).\"\"\"
    _run_single_note_export_command(pdf, out, ir_out, "eighth")

@app.command("notation-sixteenth-note-export")
def notation_sixteenth_note_export_command(
    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one sixteenth note"),
    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),
    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),
) -> None:
    \"\"\"Explicit, opt-in CLI route for single standard-notation sixteenth-note GP export (v0).\"\"\"
    _run_single_note_export_command(pdf, out, ir_out, "16th")

@app.command("notation-thirty-second-note-export")
def notation_thirty_second_note_export_command(
    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one thirty-second note"),
    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),
    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),
) -> None:
    \"\"\"Explicit, opt-in CLI route for single standard-notation thirty-second-note GP export (v0).\"\"\"
    _run_single_note_export_command(pdf, out, ir_out, "32nd")

@app.command("notation-sixty-fourth-note-export")
def notation_sixty_fourth_note_export_command(
    pdf: Path = typer.Option(..., "--pdf", help="Path to the PDF fixture containing exactly one sixty-fourth note"),
    out: Path = typer.Option(..., "--out", help="Output GP artifact path"),
    ir_out: Optional[Path] = typer.Option(None, "--ir-out", help="Optional debug path to write the intermediate ScoreIR JSON"),
) -> None:
    \"\"\"Explicit, opt-in CLI route for single standard-notation sixty-fourth-note GP export (v0).\"\"\"
    _run_single_note_export_command(pdf, out, ir_out, "64th")
"""

new_content = before_main + helper + "\n" + main_block
Path("src/score2gp/cli.py").write_text(new_content)
