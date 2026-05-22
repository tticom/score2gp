# Handoff

## Metadata
- **Current Branch**: `feature/symbol-attachment-html-inspection-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft PR pending creation
- **Latest Local Commit**: `3e26a57e3f2cb51c0702d8471bd7848f3224b78f` (Base main merge of PR #10)
- **Latest Pushed Commit**: `3e26a57e3f2cb51c0702d8471bd7848f3224b78f`
- **Commit Subject**: `Base merge commit`
- **Working Tree Status**: Clean (once modifications are committed)
- **Tests & Checks Run**:
  - `python -m pytest` -> 120 passed (pre-compaction verify)
  - `python -m score2gp.cli export-schema --out schemas` -> passed
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed
  - `git diff -- schemas` -> empty
- **GitHub Check Status**: Ready to create draft PR
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
