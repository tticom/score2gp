# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-layout-v0.1`
- **Base Branch**: `main`
- **Current PR**: Pending draft creation
- **Latest Local Commit**: Pending commit
- **Latest Pushed Commit**: Pending push
- **Commit Subject**: Refresh private smoke blocker summary
- **Working Tree Status**: Modified (verified and ready to commit)
- **Tests & Checks Run**:
  - `python -m pytest` -> 140 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A (local-only prior to push)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Re-ran the private-safe E2E diagnostic smoke pass locally using the ignored output directory `work/private_e2e_smoke_after_layout_v0_1/` to refresh our pipeline capability assessments.
- Analyzed the diagnostic warnings and gating results after recent MusicXML timing and PDF layout diagnostics improvements.
- Updated the canonical private-safe blocker summary and classification using only anonymized counts, statuses, and reason codes.

## Private Smoke Result Summary (Safe Counts & Statuses Only)
1. **`private_input_1`** (`pdf-tab-musicxml`):
   - **Page Count**: 2
   - **Text/Geometry Detected**: Yes (both extractable text and drawn tab geometry detected)
   - **Playable Candidate Count**: 203 candidates
   - **Timing Status**: `failed` (ScoreIR gate status: `refused`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: `musicxml_timing_risk`
   - **Secondary Reason Codes**: `MusicXML timing risk prevents ScoreIR output: 63 overfull or overlapping event(s) would violate ScoreIR timing`, `missing_pdf_grouping`
   - **Next Diagnostic Recommendation**: `review-musicxml-timing-risk-before-alignment`
2. **`private_input_2`** (`pdf-tab-only`):
   - **Page Count**: 1
   - **Text/Geometry Detected**: Yes (both extractable text and drawn tab geometry detected)
   - **Playable Candidate Count**: 54 candidates
   - **Timing Status**: `not_attempted` (ScoreIR gate status: `not_attempted`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: None (MusicXML is missing)
   - **Secondary Reason Codes**: `missing_pdf_grouping`, `pdf-tab-system-not-detected`
   - **Next Diagnostic Recommendation**: `provide-matching-musicxml-before-build-ir`

## Current Blocker Classification
- **Top Blocker**: `musicxml_timing`
- **Rationale**: For the E2E input `private_input_1`, the preflight timing check failed with `musicxml_timing_risk` due to 63 overfull or overlapping events violating ScoreIR timing. Unsafe MusicXML strictly blocks the ScoreIR generation to prevent downstream compiler failure. Additionally, the PDF layout has overlapping systems and lacks clean barlines/bar boxes (`missing_pdf_grouping`), which also gates `build_ir`. For `private_input_2`, matching MusicXML reference is completely missing (`missing_reference_musicxml`).

## Recommended Next Branch
- **Next Branch**: `feature/musicxml-timing-public-fixtures-v0.2`
- **Goal**: Add public synthetic timing/overlap fixtures mirroring Audiveris compound meter and backup/forward voice timings, and improve preflight timing heuristics to resolve timing overlap refusal boundaries.

## Known Limitations
- PDF grouping is strictly conservative and requires born-digital vector tab geometry. No ML layout recognition or OCR is supported.
- Unsafe PDF grouping (partial, missing, ambiguous, or unsupported) and unsafe MusicXML timing strictly block `build_ir` and prevent ScoreIR compilation.
- Scanned/raster PDFs remain unsupported.

## Remaining Risks
- None. All 140 tests are fully passing locally. Whitespace checks are perfectly clean, and schemas are identical to the base branch.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken validation/timing gates or tune thresholds to private examples.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
