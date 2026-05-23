# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-calibration-boundary-v0.1`
- **Base Branch**: `main`
- **Current PR**: `Pending`
- **Latest Local Commit**: `Pending`
- **Latest Pushed Commit**: `Pending`
- **Commit Subject**: Refresh private smoke after calibration boundary diagnostics
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 190 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Private Smoke Refresh**: Re-ran the local private-safe E2E diagnostic smoke workflow to evaluate real private score fixtures under `fixtures/private/` with the new timing calibration boundary diagnostics.
- **Feasibility Verification**: Verified that the new timing preflight telemetry correctly extracts and reports detailed blocker counts and feasibility flags on real private inputs.
- **Anonymized Reporting**: Updated the private-safe blocker summaries and blocker classifications under ignored `work/` without leaking private musical content or committing private files.

## Private Smoke Result Summary (Safe Counts & Statuses Only)
1. **`private_input_1`** (`pdf-tab-musicxml`):
   - **Page Count**: 2
   - **Text/Geometry Detected**: Yes (both extractable text and drawn tab geometry detected)
   - **Playable Candidate Count**: 203 candidates (non-playable: 126, total: 329)
   - **Timing Status**: `failed` (ScoreIR gate status: `refused`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: `musicxml_timing_risk`
   - **Secondary Reason Codes**: `MusicXML timing risk prevents ScoreIR output: 66 overfull or overlapping event(s) would violate ScoreIR timing.`, `missing_pdf_grouping`
   - **Timing Risk Count**: 69 total issues (63 overfull bar errors across 16 distinct measures/bars, 1 underfull bar/measure, 2 many timing risks, 2 tie continuity risks)
   - **Calibration Feasibility Status**: `failed` (`calibration_possible` is false, meaning calibration/automatic repair is not safe or possible)
   - **Calibration Blocking Reasons**:
     - `musicxml_many_risks_block_calibration`
     - `musicxml_mixed_underfull_overfull_blocks_calibration`
     - `musicxml_overfull_too_large_for_calibration`
     - `musicxml_tie_continuity_blocks_calibration`
     - `musicxml_timing_calibration_not_safe`
   - **Calibration Candidate Reason**: `null` (not a candidate)
   - **Overfull measures/bars**: 16 distinct overfull measures/bars (measures 1-6 overfull by up to 36.0 divisions; active durations up to 84 divisions vs 48.0 expected)
   - **Underfull measures/bars**: 1
   - **Overlap counts**: 0 same-voice timing overlaps found
   - **Tie continuity risk count**: 2
   - **Many timing risks (high backup/forward density)**: 2
   - **Invalid duration grid count**: 0
   - **Affected Event Count**: 78 distinct note IDs affected
   - **Automatic repair attempted**: `false`
   - **Remediation Hint**: `Fix or regenerate MusicXML timing; automatic timing repair is not implemented.`
   - **Alignment status**: `failed`
   - **GP writing status**: `not_attempted`
   - **Stage reached**: `musicxml-import`
   - **Artifact paths under work/**: `work/private_e2e_smoke_after_calibration_boundary_v0_1/private_input_1/`
   - **Next Diagnostic Recommendation**: `review-musicxml-timing-risk-before-alignment`

2. **`private_input_2`** (`pdf-tab-only`):
   - **Page Count**: 1
   - **Text/Geometry Detected**: Yes (both extractable text and drawn tab geometry detected)
   - **Playable Candidate Count**: 54 candidates (non-playable: 17, total: 71)
   - **Timing Status**: `not_attempted` (ScoreIR gate status: `not_attempted`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: `none` (MusicXML is missing)
   - **Secondary Reason Codes**: `missing_pdf_grouping`, `pdf-tab-system-not-detected`
   - **Timing Risk Count**: 0 (not attempted)
   - **Calibration Feasibility Status**: `none`
   - **Overfull tick/division counts**: 0
   - **Overlap counts**: 0
   - **Alignment status**: `not_attempted`
   - **GP writing status**: `not_attempted`
   - **Stage reached**: `pdf-tab-extraction`
   - **Artifact paths under work/**: `work/private_e2e_smoke_after_calibration_boundary_v0_1/private_input_2/`
   - **Next Diagnostic Recommendation**: `provide-matching-musicxml-before-build-ir`

## Current Blocker Classification
- **Top Blocker**: `musicxml_timing_repair_not_safe`
- **Rationale**: For `private_input_1`, the new timing diagnostics successfully ran and verified that `calibration_possible` is `false` with multiple explicit blocking reasons: large overfull measures (`musicxml_overfull_too_large_for_calibration`), unresolved ties (`musicxml_tie_continuity_blocks_calibration`), high backup/forward densities (`musicxml_many_risks_block_calibration`), and mixed underfull/overfull bars (`musicxml_mixed_underfull_overfull_blocks_calibration`). Since these risks represent unrecoverable, non-safe timing errors, timing repair is impossible or unsafe. Additionally, both private inputs are blocked by PDF grouping issues (`missing_pdf_grouping`).
- **Comparison to Previous Blocker Summary**:
  - Previous Blocker: `musicxml_invalid_timing_confirmed`
  - Previous Summary: 69 detailed timing issues (63 overfull bar errors, 1 underfull bar, 2 tie continuity risks, 2 many timing risks), 66 affected events, `calibration_possible` false.
  - Current Summary: 69 detailed timing issues across 16 distinct overfull measures, 1 underfull measure, 78 affected event IDs, 2 tie continuity risks, 2 high-density timing risks, `calibration_possible` false. Calibration feasibility is confirmed as `calibration-not-safe` with explicit block reason telemetry.

## Recommended Next Branch
- **Next Branch**: `feature/pdf-layout-public-fixtures-v0.3`
- **Rationale**: Timing remains blocked and unrecoverable, and PDF grouping is also blocking (`missing_pdf_grouping` for both inputs). The next logical step is to improve layout grouping boundaries and add public synthetic fixtures for system/layout failures.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
