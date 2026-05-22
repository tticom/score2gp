# Handoff

## Metadata
- **Current Branch**: `feature/symbol-attachment-html-inspection-v0.1`
- **Base Branch**: `main`
- **Current PR**: #11 (URL: https://github.com/tticom/score2gp/pull/11)
- **Latest Local Commit**: `ea466122d107a729525c34749fbe706786c5f726`
- **Latest Pushed Commit**: `ea466122d107a729525c34749fbe706786c5f726`
- **Commit Subject**: `Add symbol attachment HTML diagnostics`
- **Working Tree Status**: Clean (once HANDOFF.md is committed)
- **Tests & Checks Run**:
  - `python -m pytest` -> 120 passed (pre-compaction verify)
  - `python -m score2gp.cli export-schema --out schemas` -> passed
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed
  - `git diff -- schemas` -> empty
- **GitHub Check Status**: Pending (Checks running on draft PR #11)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL files, overlays, logs, or diagnostic outputs are tracked or staged.

## What Changed in the Task
- Added developer-facing HTML inspection report for attached and unattached chord symbols and technique text evidence in generated ScoreIR (`symbol-attachment-diagnostics.html`).
- The HTML report displays:
  - title identifying symbol/technique attachment diagnostics
  - source ScoreIR path or build output path
  - total/attached/unattached chord candidates
  - total/attached/unattached technique candidates
  - attachment target IDs (bar index, event ID, note target details where available)
  - confidence values
  - provenance/candidate IDs
  - warning/reason codes for unattached, ambiguous, or unsupported candidates
  - clear statement that GPIF rendering is not implemented
  - clear statement that symbols and techniques did not create notes, events, or timing
- Preserved existing JSON diagnostics.
- Hooked the report generation into the successful build path of `build_ir_from_files` in `src/score2gp/build_ir.py` and `build-ir` CLI command in `src/score2gp/cli.py`.
- Added comprehensive public test suite proving all visual, count, and statement requirements in `tests/test_symbol_attachment.py` (no private fixtures used).
- Updated architectural and workflow documentation in `docs/architecture.md`, `docs/workflow.md`, and `docs/limitations.md`.

## Known Limitations
- HTML diagnostics are developer-facing only. JSON diagnostics remain the programmatic source of truth.
- GPIF technique/chord rendering is not implemented.
- No OCR.
- No scanned-PDF support.
- No ML layout recognition.
- No broad ASCII-to-ScoreIR conversion.
- Symbols and techniques do not create notes, events, or timing.

## Remaining Risks
- None. The inspection report is purely informative and sidecar-like, with zero impact on ScoreIR semantic generation correctness or conservative alignment logic.

## Explicit Scope Boundaries
- **Do not** start GPIF technique rendering.
- **Do not** broaden ASCII-to-ScoreIR conversion.
- **Do not** infer durations from PDF text.
- **Do not** use private PDFs as regression fixtures.
- **Do not** commit `work/` outputs or private files.

## Next Recommended Task
- Add developer-facing HTML styling and compact thumbnails for grouping diagnostics.
