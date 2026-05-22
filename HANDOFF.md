# Handoff

## Metadata
- **Current Branch**: `feature/musicxml-invalid-timing-public-fixtures-v0.4`
- **Base Branch**: `main`
- **Current PR**: [#23](https://github.com/tticom/score2gp/pull/23)
- **Latest Local Commit**: `ddbca3f074b2ee5579191c809408b5e607d53074`
- **Latest Pushed Commit**: `ddbca3f074b2ee5579191c809408b5e607d53074`
- **Commit Subject**: Add invalid MusicXML timing fixtures
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
- **Synthetic Public Fixtures**: Created 10 public synthetic MusicXML fixtures under `tests/fixtures/musicxml/` representing same-voice invalid timing and overfull measures:
  1. `timing_vc_same_voice_overfull.musicxml`: Same voice overfull by one note duration.
  2. `timing_vc_same_voice_accumulated_overflow.musicxml`: Same voice overfull by accumulated small rounding/subdivision errors.
  3. `timing_vc_same_voice_event_overlap.musicxml`: Same voice overlapping event caused by incorrect duration.
  4. `timing_vc_same_voice_rest_note_overlap.musicxml`: Same voice overlap caused by a rest plus note occupying the same tick range.
  5. `timing_vc_backup_no_voice_switch_overlap.musicxml`: Same voice overlap after backup that does not switch voice.
  6. `timing_vc_event_extends_past_measure.musicxml`: Same voice event whose duration extends beyond the measure end.
  7. `timing_vc_compound_meter_overfull.musicxml`: Overfull bar in compound meter.
  8. `timing_vc_invalid_duration_grid.musicxml`: Overfull bar with divisions that do not divide cleanly into expected measure ticks.
  9. `timing_vc_many_invalid_events.musicxml`: Synthetic "many invalid events" fixture that produces a count greater than one, proving summaries scale.
  10. `timing_vc_valid_counterparts.musicxml`: Valid counterpart for each important class.
- **Diagnostics Refinements**: Refined `MusicXmlVoiceCursorModel` and timing issue parsing to trace same-voice overfull measures, accumulated duration overflows, rest/note overlaps, invalid duration grids, and timing calibration suitability.
- **Reporting Improvements**: Enhanced `write_musicxml_timing_diagnostics_html` in `report.py` to aggregate and display calibration status, overfull divisions, overlap counts, and print the required hint: `"Fix or regenerate MusicXML timing; automatic timing repair is not implemented."`
- **Unit Tests**: Added a complete suite of unit tests in `tests/test_musicxml_invalid_fixtures.py` that verifies the exact classification and error reasons, proves that invalid timing blocks alignment/build-ir, and checks that no private fixtures are used. All 189 tests pass successfully.

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

## Current Blocker Classification
- **Top Blocker**: `musicxml_timing_invalid`
- **Rationale**: For `private_input_1`, the preflight timing check still fails due to 66 overfull or overlapping events. This has now been reproduced cleanly using public synthetic fixtures. The diagnostics have been significantly enhanced to track calibration feasibility, overfull divisions, overlap counts, and affected event IDs. The next step is to run the private smoke refresh to see these refined telemetry counts and calibration flags on the private inputs.

## Recommended Next Branch
- **Next Branch**: `feature/private-smoke-refresh-after-invalid-timing-diagnostics-v0.1`
- **Goal**: Re-run the local E2E private smoke workflow after invalid timing diagnostics (v0.4) to confirm that the new timing metadata (calibration feasibility, overfull divisions, overlap counts, and affected event IDs) is correctly extracted and reported on real private inputs.

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
