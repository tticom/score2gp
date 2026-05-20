# Handoff

## Current Context

- Branch: `feature/scoreir-v0.1-contract`
- Latest local checkpoint commit: `285f478 Add PDF grouping diagnostic report`
- Current PDF grouping v0.1 work is intentionally uncommitted unless the user asks to commit.
- Private fixtures and diagnostic outputs must remain ignored and uncommitted.

## Implemented In This Working Tree

- PDF grouping v0.1 remains public-fixture-only and uses born-digital drawing geometry: six near-horizontal tab lines define a staff, vertical crossing lines define bar boxes, fret text is assigned to the nearest string line, and x-position assigns a bar.
- TabRaw v0.1 remains unchanged; grouping evidence is stored in candidate `raw` fields under `pdf-grouping.v0.1`.
- `extract-tab` now writes `grouping-diagnostics.html` and `overlays/page-*-grouping.png` for grouped, partial, and missing playable PDF extraction.
- Overlays show candidate boxes, inferred tab staff boxes, string lines, barlines, bar boxes, and assigned string/bar labels.
- `build-ir` now refuses partially grouped playable candidates too; every playable PDF-derived fret candidate must have system, string, and bar evidence.
- The unstructured public PDF fixture still reports `missing_pdf_grouping` and remains blocked before ScoreIR output.

## Verification

- Baseline before edits: `python -m pytest`: 66 passed
- Focused grouping/report/build tests: `python -m pytest tests/test_pdf.py tests/test_report.py tests/test_build_ir.py`: 22 passed

## Remaining Work

- Run full `python -m pytest`, schema export, `validate-ir`, CLI smoke commands, `git diff --check`, and private-safety status checks before any commit.
- Add low-confidence public fixtures for partial grouping such as missing barlines or incomplete staff geometry.
- Add developer-facing styling/thumbnails for grouping reports if useful.
- Continue adding public MusicXML timing-risk fixtures before another private diagnostic experiment.
- Keep GPIF expansion, OCR, ML, and real private conversion out of this phase.
