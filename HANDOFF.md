# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-musicxml-v0.2`
- **Base Branch**: `main`
- **Current PR**: N/A (not created yet)
- **Latest Local Commit**: `442bab3d382c6e1934a2a576531e9ea059b89a11`
- **Latest Pushed Commit**: `442bab3d382c6e1934a2a576531e9ea059b89a11`
- **Commit Subject**: Refresh private smoke blocker summary after MusicXML fixtures
- **Working Tree Status**: Clean (after committing handoff)
- **Tests & Checks Run**:
  - `python -m pytest` -> 150 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A (local-only prior to push)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Re-ran the private-safe E2E diagnostic smoke pass locally using the ignored output directory `work/private_e2e_smoke_after_musicxml_v0_2/` to refresh our pipeline capability assessments.
- Analyzed the diagnostic warnings and gating results after recent MusicXML timing public fixtures work (PR #17).
- Updated the canonical private-safe blocker summary and classification using only anonymized counts, statuses, and reason codes.

## Private Smoke Result Summary (Safe Counts & Statuses Only)
1. **`private_input_1`** (`pdf-tab-musicxml`):
   - **Page Count**: 2
   - **Text/Geometry Detected**: Yes (both extractable text and drawn tab geometry detected)
   - **Playable Candidate Count**: 203 candidates (non-playable: 126, total: 329)
   - **Timing Status**: `failed` (ScoreIR gate status: `refused`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: `musicxml_timing_risk`
   - **Secondary Reason Codes**: `MusicXML timing risk prevents ScoreIR output: 64 overfull or overlapping event(s) would violate ScoreIR timing.`, `missing_pdf_grouping`
   - **Next Diagnostic Recommendation**: `review-musicxml-timing-risk-before-alignment`
2. **`private_input_2`** (`pdf-tab-only`):
   - **Page Count**: 1
   - **Text/Geometry Detected**: Yes (both extractable text and drawn tab geometry detected)
   - **Playable Candidate Count**: 54 candidates (non-playable: 17, total: 71)
   - **Timing Status**: `not_attempted` (ScoreIR gate status: `not_attempted`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: `none` (MusicXML is missing)
   - **Secondary Reason Codes**: `missing_pdf_grouping`, `pdf-tab-system-not-detected`
   - **Next Diagnostic Recommendation**: `provide-matching-musicxml-before-build-ir`

## Current Blocker Classification
- **Top Blocker**: `musicxml_timing`
- **Rationale**: For the E2E input `private_input_1`, the preflight timing check still fails with `musicxml_timing_risk` due to 64 overfull or overlapping events violating ScoreIR timing (timing status is `failed`). While the previous work added robust preflight checks and precise diagnostics, the specific timing issues in this private score are not yet fully modeled. We need to create a third round of public synthetic timing fixtures to address the remaining voice cursor alignment and backup/forward cases.

## Recommended Next Branch
- **Next Branch**: `feature/musicxml-timing-public-fixtures-v0.3`
- **Goal**: Add a third round of public synthetic MusicXML timing fixtures focusing on the remaining voice cursor alignment, backup/forward movements, and layout risks.

## Known Limitations
- PDF grouping is strictly conservative and requires born-digital vector tab geometry. No ML layout recognition or OCR is supported.
- Unsafe PDF grouping (partial, missing, ambiguous, or unsupported) and unsafe MusicXML timing strictly block `build_ir` and prevent ScoreIR compilation.
- Scanned/raster PDFs remain unsupported.

## Remaining Risks
- None. All 150 tests are fully passing locally. Whitespace checks are perfectly clean, and schemas are identical to the base branch.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken validation/timing gates or tune thresholds to private examples.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
