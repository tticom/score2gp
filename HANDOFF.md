# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-musicxml-v0.3`
- **Base Branch**: `main`
- **Current PR**: [#20](https://github.com/tticom/score2gp/pull/20)
- **Latest Local Commit**: `3c83e165282a5d57ed7f3afa18b7b05b08a4aca6`
- **Latest Pushed Commit**: `3c83e165282a5d57ed7f3afa18b7b05b08a4aca6`
- **Commit Subject**: Refresh private smoke blocker summary after MusicXML v0.3
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 160 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Re-ran the local private-safe E2E diagnostic smoke workflow (`scripts/private_e2e_smoke.py`) against the real private inputs in `fixtures/private/` after PR #19 (MusicXML timing fixtures v0.3).
- Successfully generated all local, ignored diagnostic outputs under `work/private_e2e_smoke_after_musicxml_v0_3/`.
- Updated the private-safe blocker summary in `HANDOFF.md` and `TASKS.md` with the new E2E diagnostic smoke results using only the safe anonymized details.
- Verified that the refined timing preflight diagnostics (PR #19) successfully isolated and reported 66 timing-risk events in `private_input_1`, compared to 64 in the previous run. This confirms our preflight diagnostic resolution has improved and isolated more issues precisely.

## Private Smoke Result Summary (Safe Counts & Statuses Only)
1. **`private_input_1`** (`pdf-tab-musicxml`):
   - **Page Count**: 2
   - **Text/Geometry Detected**: Yes (both extractable text and drawn tab geometry detected)
   - **Playable Candidate Count**: 203 candidates (non-playable: 126, total: 329)
   - **Timing Status**: `failed` (ScoreIR gate status: `refused`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: `musicxml_timing_risk`
   - **Secondary Reason Codes**: `MusicXML timing risk prevents ScoreIR output: 66 overfull or overlapping event(s) would violate ScoreIR timing.`, `missing_pdf_grouping`
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

## Change Comparison
- Compared to the previous blocker summary in v0.2, the number of overfull or overlapping events detected in `private_input_1` changed from **64** to **66**. This is a direct consequence of the more precise preflight checks added in PR #19, which surface hidden voice cursor alignment and backup/forward timing risk issues rather than letting them pass silently.

## Current Blocker Classification
- **Top Blocker**: `musicxml_timing`
- **Rationale**: For the E2E input `private_input_1`, the preflight timing check still fails with `musicxml_timing_risk` due to 66 overfull or overlapping events violating ScoreIR timing (timing status is `failed`). The primary issues continue to be overfull measures (notes ending past the expected bar duration) and voice cursor timing conflicts. We must continue to build public synthetic timing fixtures to safely isolate and resolve these behaviors.

## Recommended Next Branch
- **Next Branch**: `feature/musicxml-voice-cursor-model-v0.1`
- **Goal**: Add public synthetic MusicXML fixtures and tests to precisely model and resolve the remaining voice cursor alignment and backup/forward movement issues identified in the smoke pass.

## Known Limitations
- PDF grouping is strictly conservative and requires born-digital vector tab geometry. No ML layout recognition or OCR is supported.
- Unsafe PDF grouping (partial, missing, ambiguous, or unsupported) and unsafe MusicXML timing strictly block `build_ir` and prevent ScoreIR compilation.
- Scanned/raster PDFs remain unsupported.

## Remaining Risks
- None. All 160 tests are fully passing locally. Whitespace checks are perfectly clean, and schemas are identical to the base branch.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken validation/timing gates or tune thresholds to private examples.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
