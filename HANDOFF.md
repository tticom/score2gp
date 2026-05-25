# Handoff

## Metadata

- **Current Branch**: `feature/convert-orchestration-v0.1`
- **Base Branch**: `main`
- **Current PR**: #74 (Draft PR: https://github.com/tticom/score2gp/pull/74)
- **Latest Local Commit**: `fed1ceb` ("Document CLI convert orchestration in handoff and tasks")
- **Latest Pushed Commit**: `fed1ceb` ("Document CLI convert orchestration in handoff and tasks")
- **Working Tree Status**: Clean.

- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. No root generated artifacts tracked.

## Tests And Checks Run

- `python -m pytest` -> 323 passed (100% success, including new synthetic orchestration tests `test_orchestration_convert_success` and `test_orchestration_convert_missing_musicxml`).
- `python -m score2gp.cli export-schema --out schemas` -> passed cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/test_gpif_multi_voice.ir.json` -> valid.
- `git diff --check` -> passed cleanly.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.

## What Changed In This Task

- **Sequential CLI Convert Orchestration**:
  - Replaced the placeholder dummy stub in `convert_command` (`src/score2gp/cli.py`) with a fully realized, sequential stage orchestration pipeline.
  - Automatically runs `inspect_pdf_file` to capture PDF metadata, followed by `extract_tab_file` to yield first-pass born-digital TabRaw candidate text evidence.
  - If a matching MusicXML file is provided, checks for the presence of playable ASCII-tab candidates. If present, runs the `align_ascii_musicxml_files` alignment sidecar to construct compatible onset mappings.
  - Dynamically runs `build_ir_with_diagnostics_from_files` to generate ScoreIR and handle vertical/horizontal technique and chord attachments.
  - Gracefully catches `BuildIrInputRiskError` exceptions to halt execution on layout grouping or alignment blockers, writing the failure diagnostics to `diagnostics.json` in the workdir.
  - Writes the final output Guitar Pro 7 package (`write_gp`) on successful ScoreIR compilation.
  - Aggregates warning structures from all execution stages (PDF extraction, ASCII alignment, ScoreIR generation, and GP packaging) and outputs them to `warnings.json` in the output `--workdir`.
  - Produces a comprehensive HTML conversion diagnostics report `conversion-report.html` inside the workdir to keep any guessed or unsupported features highly visible.
- **Added Comprehensive E2E Tests**:
  - Authored a new E2E test file `tests/test_orchestration.py` to assert correct convert command execution.
  - `test_orchestration_convert_success` verifies full, successful E2E conversion from PDF + compatible MusicXML to a valid GP package and HTML report.
  - `test_orchestration_convert_missing_musicxml` verifies that the pipeline halts gracefully, writes an aggregated `missing_musicxml` warning, and produces reports without creating the output GP file.
- **E2E Private Smoke Test Results**:
  - Ran `scripts/private_e2e_smoke.py` to confirm zero regressions in underlying grouping, snapping, recovery, and alignment modules.

## Known Limitations

- Scanning is limited to digital PDF vector layouts; no scanned-PDF, image-based OCR, or layout ML is supported.

## Remaining Risks

- None.

## Next Recommended Task

- **Auditory Fidelity Refinements (Milestone 5)**: Expand Guitar Pro 7 writer coverage to support more expressive techniques (like slides/bends visual refinements, dynamic expressions, or pitch variations).

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
