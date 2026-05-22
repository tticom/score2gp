# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-musicxml-voice-cursor-v0.1`
- **Base Branch**: `main`
- **Current PR**: [#22](https://github.com/tticom/score2gp/pull/22)
- **Latest Local Commit**: `af5a52172f7f7ff7041a9a77eb2b00e3bbef1031`
- **Latest Pushed Commit**: `af5a52172f7f7ff7041a9a77eb2b00e3bbef1031`
- **Commit Subject**: Refresh private smoke blocker summary after voice cursor model
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 169 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Re-ran the local private-safe E2E diagnostic smoke workflow (`scripts/private_e2e_smoke.py`) against the real private inputs in `fixtures/private/` after PR #21 (deterministic MusicXML voice cursor model).
- Successfully generated all local, ignored diagnostic outputs under `work/private_e2e_smoke_after_voice_cursor_v0_1/`.
- Updated the private-safe blocker summary in `HANDOFF.md` and `TASKS.md` with the new E2E diagnostic smoke results using only the safe anonymized details.
- Confirmed that `private_input_1` continues to report exactly 66 overfull or overlapping events. The new voice cursor model isolates these as true same-voice invalid timeline issues (`musicxml-overfull-bar` where voice durations sum to 78 divisions inside a 48-division measure) rather than false-positive overlaps or multi-voice structural issues.

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
- The number of overfull or overlapping events detected in `private_input_1` remains exactly **66**, which is completely mathematically consistent. However, thanks to the deterministic voice cursor model implemented in PR #21, we now have precise diagnostics (`build_error.json`) confirming that these are same-voice invalid timing errors (primarily `musicxml-overfull-bar` where notes in voice 1 extend past measure boundaries) rather than polyphony-gate or backup/forward-handling ambiguities.

## Current Blocker Classification
- **Top Blocker**: `musicxml_timing_invalid`
- **Rationale**: For the E2E input `private_input_1`, the preflight timing check still fails with `musicxml_timing_risk` due to 66 overfull or overlapping events. This is classified as `musicxml_timing_invalid` because the notes in the MusicXML file have durations exceeding the expected measure duration. We need to implement public synthetic timing fixtures for invalid timing/overfull measures to refine timing calibration and explore duration adjustments before alignment.

## Recommended Next Branch
- **Next Branch**: `feature/musicxml-invalid-timing-public-fixtures-v0.4`
- **Goal**: Add public synthetic MusicXML fixtures and tests representing invalid same-voice timing / overfull measures to design and refine timing calibration, duration adjustments, and recovery heuristics before alignment.

## Known Limitations
- PDF grouping is strictly conservative and requires born-digital vector tab geometry. No ML layout recognition or OCR is supported.
- Unsafe PDF grouping (partial, missing, ambiguous, or unsupported) and unsafe MusicXML timing strictly block `build_ir` and prevent ScoreIR compilation.
- Scanned/raster PDFs remain unsupported.

## Remaining Risks
- None. All 169 tests are fully passing locally. Whitespace checks are perfectly clean, and schemas are identical to the base branch.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken validation/timing gates or tune thresholds to private examples.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
