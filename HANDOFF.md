# Handoff

## Metadata
- **Current Branch**: `feature/musicxml-timing-public-fixtures-v0.3`
- **Base Branch**: `main`
- **Current PR**: [#19](https://github.com/tticom/score2gp/pull/19)
- **Latest Local Commit**: `cf18a6227a74eb5a710599eb112bd56cb1fc9c9a`
- **Latest Pushed Commit**: `cf18a6227a74eb5a710599eb112bd56cb1fc9c9a`
- **Commit Subject**: Add MusicXML timing blocker fixtures v0.3
- **Working Tree Status**: Clean (after committing handoff)
- **Tests & Checks Run**:
  - `python -m pytest` -> 160 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A (local-only prior to push)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Added a third round of public synthetic MusicXML timing fixtures (v0.3) focusing on voice cursor alignment, repeated backup/forward movement, and Audiveris-like timing risk patterns:
  1. `timing_v03_repeated_backup_forward.musicxml` (exceeds 3 cursor movements)
  2. `timing_v03_voice_cursor_reset.musicxml` (same-voice same-onset overlap)
  3. `timing_v03_multivoice_staggered.musicxml` (cross-voice timing overlap)
  4. `timing_v03_backup_measure_start_forward.musicxml` (occupied tick ranges duplicate)
  5. `timing_v03_rest_note_cursor_overlap.musicxml` (rest/note overlap)
  6. `timing_v03_chord_marker_backup_forward.musicxml` (legitimate chord stack separate from overlap)
  7. `timing_v03_audiveris_heavy_rewinds.musicxml` (heavy rewind/cursor subdivision)
  8. `timing_v03_high_count_timing_risk.musicxml` (high density of errors)
  9. `timing_v03_valid_counterpart.musicxml` (compound meter valid counterpart)
  10. `timing_v03_alignment_not_attempted.musicxml` (final alignment-not-attempted Refusal)
- Refined timing preflight diagnostics in `src/score2gp/musicxml.py` to identify same-voice same-onset tick overlap (without chord elements), multi-voice tick overlap, rest overlap, and repeated backup/forward movement risk, returning a rich set of specific timing codes.
- Added mapped HTML remediation advice for the new codes in `src/score2gp/report.py`.
- Added 10 corresponding unit tests in `tests/test_musicxml_timing_overlap.py` that fully cover all new fixtures and verify the strict refusals, valid counterpart passes, and gate blocks.
- Documented these v0.3 features and codes in `docs/architecture.md`, `docs/workflow.md`, `docs/limitations.md`, and `TASKS.md`.

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
- **Next Branch**: `feature/private-smoke-refresh-after-musicxml-v0.3`
- **Goal**: Re-run the private-safe E2E diagnostic smoke workflow after the MusicXML timing public fixture work v0.3 to see if the timing blocker details have changed and to refresh the blocker summary.

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
