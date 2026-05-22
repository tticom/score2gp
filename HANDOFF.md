# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-invalid-timing-diagnostics-v0.1`
- **Base Branch**: `main`
- **Current PR**: [#24](https://github.com/tticom/score2gp/pull/24)
- **Latest Local Commit**: `e8a6ec377fb3d4be92a6d2179aaa5a647928a7f0`
- **Latest Pushed Commit**: `e8a6ec377fb3d4be92a6d2179aaa5a647928a7f0`
- **Commit Subject**: Refresh private smoke after invalid timing diagnostics
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 189 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Private Smoke Refresh**: Re-ran the local private-safe E2E diagnostic smoke workflow to evaluate real private score fixtures under `fixtures/private/` with the new invalid timing diagnostics v0.4.
- **Diagnostic Outcome Verification**: Successfully verified that the new timing metadata (such as calibration feasibility, overfull division counts, and affected event lists) is correctly extracted and reported on real private inputs.
- **Anonymized Reporting**: Wrote anonymized master reports under `work/private_e2e_smoke_after_invalid_timing_v0_1/` without leaking private musical content or committing private files.
- **Tasks & Handoff**: Moved the private smoke refresh task from Next to Done in `TASKS.md` and updated `HANDOFF.md` with the new counts, statuses, and blocker classifications.

## Private Smoke Result Summary (Safe Counts & Statuses Only)
1. **`private_input_1`** (`pdf-tab-musicxml`):
   - **Page Count**: 2
   - **Text/Geometry Detected**: Yes (both extractable text and drawn tab geometry detected)
   - **Playable Candidate Count**: 203 candidates (non-playable: 126, total: 329)
   - **Timing Status**: `failed` (ScoreIR gate status: `refused`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: `musicxml_timing_risk`
   - **Secondary Reason Codes**: `MusicXML timing risk prevents ScoreIR output: 66 overfull or overlapping event(s) would violate ScoreIR timing.`, `missing_pdf_grouping`
   - **Timing Risk Count**: 69 total issues (63 overfull bars, 1 underfull bar, 2 many timing risks, 2 tie continuity risks)
   - **Calibration Feasibility Status**: `failed` (`timing_calibration_possible` is false for all issues, as automatic timing repair is not implemented/safe)
   - **Overfull tick/division counts**: 63 overfull bar errors (measures 1-6 overfull by up to 36.0 divisions; active durations up to 84 divisions vs 48.0 expected)
   - **Overlap counts**: 0 same-voice timing overlaps found
   - **Voice cursor status**: `musicxml_voice_timeline_valid`
   - **Polyphony/support status**: Monophonic voice 1 timelines are valid but overfull
   - **Alignment status**: `failed`
   - **GP writing status**: `not_attempted`
   - **Stage reached**: `musicxml-import`
   - **Artifact paths under work/**: `work/private_e2e_smoke_after_invalid_timing_v0_1/private_input_1/`
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
   - **Voice cursor status**: `not_attempted`
   - **Polyphony/support status**: `not_attempted`
   - **Alignment status**: `not_attempted`
   - **GP writing status**: `not_attempted`
   - **Stage reached**: `pdf-tab-extraction`
   - **Artifact paths under work/**: `work/private_e2e_smoke_after_invalid_timing_v0_1/private_input_2/`
   - **Next Diagnostic Recommendation**: `provide-matching-musicxml-before-build-ir`

## Current Blocker Classification
- **Top Blocker**: `musicxml_invalid_timing_confirmed`
- **Rationale**: For `private_input_1`, the preflight timing check successfully ran and confirmed a high timing risk. Exactly 63 overfull bar errors (plus 6 other timing issues) were identified, totaling 69 issues. The calibration feasibility check returned `false` for all events (e.g. overfull by up to 36.0 divisions, which is far beyond expected measure lengths). The voice timelines are structurally valid but are heavily overfull. The next blocker classification is `musicxml_invalid_timing_confirmed` because these timing risks are confirmed on real private inputs.
- **Comparison to Previous Blocker**:
  - Previous blocker: `invalid same-voice timing / overfull measures`
  - Current blocker: `musicxml_invalid_timing_confirmed` with 69 detailed timing issues (63 overfull bars, 1 underfull bar, 2 tie continuity risks, 2 many timing risks) affecting 66 events and having `timing_calibration_possible: false`. Grouping also fails with `missing_pdf_grouping`.

## Recommended Next Branch
- **Next Branch**: `feature/musicxml-invalid-timing-public-fixtures-v0.5`
- **Goal**: Add further public synthetic MusicXML fixtures and preflight refinement targeting non-safe timing repair scenarios, or begin designing calibration contracts to safely partition these massive overfull errors.

## Known Limitations
- PDF grouping is strictly conservative and requires born-digital vector tab geometry. No ML layout recognition or OCR is supported.
- Unsafe PDF grouping (partial, missing, ambiguous, or unsupported) and unsafe MusicXML timing strictly block `build_ir` and prevent ScoreIR compilation.
- Scanned/raster PDFs remain unsupported.
- Automatic timing repair/calibration is not implemented; invalid same-voice timing blocks alignment strictly.

## Remaining Risks
- None. All 189 tests are fully passing locally. Whitespace checks are perfectly clean, and schemas are identical to the base branch.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken validation/timing gates or tune thresholds to private examples.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
