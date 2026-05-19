# score2gp

`score2gp` is a staged command-line toolkit for converting owned PDF guitar scores into inspectable intermediate data and, eventually, Guitar Pro 7 `.gp` files.

This project does **not** promise perfect PDF-to-Guitar-Pro conversion. Printed music recognition is uncertain, guitar tablature has details that generic OMR tools often miss, and every conversion stage should leave artefacts a musician can inspect and correct.

## Current milestone

Implemented now:

- Strict `ScoreIR` pydantic models.
- Limited uncompressed MusicXML importer for synthetic fixtures, including simple harmony, tuplets, and selected guitar techniques.
- `tabraw.v0.1` candidate model with unique stable IDs, spatial evidence, confidence, and provenance.
- Narrow `build-ir` path from synthetic MusicXML + TabRaw into valid ScoreIR with optional `build-ir-diagnostics.v0.1` sidecar output.
- Public generated born-digital PDF fixture proving that real `extract-tab` output can feed the diagnostics-backed `build-ir` path.
- `score2gp inspect-gp input.gp` for GP7 zip/GPIF inspection.
- Minimal GP7-style package writer from hand-authored ScoreIR.
- `score2gp validate output.gp`.
- Basic PDF inspection/rendering scaffolding.
- Tests for IR validation, GPIF writing, zip creation, PDF inspection fallback, and report generation.

Planned next:

- More robust PDF system and tab-line detection beyond controlled generated fixtures.
- Tab number/chord/technique extraction from real born-digital PDFs.
- `.mxl` package parsing and broader Audiveris MusicXML intake.
- Real MusicXML/tab alignment from owned score PDFs.
- Better GPIF coverage for techniques and layout.

## CLI

```powershell
score2gp inspect-gp fixtures/private/Derek Trucks BB King.gp
score2gp validate output.gp
score2gp write-gp fixtures/public/tiny_score.ir.json --template fixtures/templates/minimal_gp7.gp --out output.gp
score2gp inspect-pdf input.pdf --out work/inspect
score2gp extract-tab input.pdf --out work/tab
score2gp extract-tab tests/fixtures/pdf/generated_tiny_tab.pdf --out work/generated_pdf/generated_tiny_tab.tabraw.json
score2gp build-ir --musicxml tests/fixtures/musicxml/tiny_single_bar.musicxml --tabraw tests/fixtures/tabraw/tiny_single_bar_tabraw.json --out work/synthetic/score.ir.json
score2gp build-ir --musicxml tests/fixtures/musicxml/generated_tiny_tab.musicxml --tabraw work/generated_pdf/generated_tiny_tab.tabraw.json --out work/generated_pdf/generated_tiny_tab.ir.json --diagnostics-out work/generated_pdf/generated_tiny_tab.diagnostics.json
score2gp build-ir --musicxml tests/fixtures/musicxml/rich_guitar_cases.musicxml --tabraw tests/fixtures/tabraw/rich_guitar_cases_tabraw.json --out work/synthetic/rich_score.ir.json
score2gp build-ir --musicxml tests/fixtures/musicxml/tiny_multibar.musicxml --tabraw tests/fixtures/tabraw/tiny_multibar_tabraw.json --out work/synthetic/multibar.ir.json --diagnostics-out work/synthetic/multibar.diagnostics.json
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

See [docs/workflow.md](docs/workflow.md) for the intended staged PDF-to-GP workflow and current implementation status.

See [docs/scoreir.md](docs/scoreir.md) for the formal ScoreIR v0.1 contract, validation rules, and schema commands.

See [docs/musicxml-tabraw-build-ir.md](docs/musicxml-tabraw-build-ir.md) for the limited MusicXML, TabRaw, and synthetic `build-ir` proof path.

```powershell
python -m pip install -e .[dev]
python -m pytest
```
