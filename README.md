# score2gp

`score2gp` is a staged command-line toolkit for converting owned PDF guitar scores into inspectable intermediate data and, eventually, Guitar Pro 7 `.gp` files.

This project does **not** promise perfect PDF-to-Guitar-Pro conversion. Printed music recognition is uncertain, guitar tablature has details that generic OMR tools often miss, and every conversion stage should leave artefacts a musician can inspect and correct.

## Current milestone

Implemented now:

- Strict `ScoreIR` pydantic models.
- `score2gp inspect-gp input.gp` for GP7 zip/GPIF inspection.
- Minimal GP7-style package writer from hand-authored ScoreIR.
- `score2gp validate output.gp`.
- Basic PDF inspection/rendering scaffolding.
- Tests for IR validation, GPIF writing, zip creation, PDF inspection fallback, and report generation.

Planned next:

- More robust PDF system and tab-line detection.
- Tab number/chord/technique extraction from born-digital PDFs.
- Optional Audiveris integration for MusicXML timing.
- Better GPIF coverage for techniques and layout.

## CLI

```powershell
score2gp inspect-gp fixtures/private/Derek Trucks BB King.gp
score2gp validate output.gp
score2gp write-gp fixtures/public/tiny_score.ir.json --template fixtures/templates/minimal_gp7.gp --out output.gp
score2gp inspect-pdf input.pdf --out work/inspect
score2gp extract-tab input.pdf --out work/tab
score2gp convert input.pdf --template fixtures/templates/minimal_gp7.gp --out output.gp --workdir work/run1
```

Several pipeline commands are intentionally first-pass scaffolds. They write warnings and intermediate files rather than pretending the hard recognition work is complete.

## Private fixtures

Private copyrighted or licence-unclear examples belong in `fixtures/private/`, which is ignored by Git:

- `fixtures/private/Derek Trucks BB King.pdf`
- `fixtures/private/Derek Trucks BB King.gp`

Use them for local development and regression evaluation only.

## Development

See [docs/setup.md](docs/setup.md) for full Windows setup, Audiveris installation, private fixtures, and smoke-test commands.

```powershell
python -m pip install -e .[dev]
python -m pytest
```
