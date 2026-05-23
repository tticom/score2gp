# Handoff

## Metadata
- **Current Branch**: `feature/pdf-bar-detection-public-fixtures-v0.4`
- **Base Branch**: `main`
- **Current PR**: Draft (to be created)
- **Latest Local Commit**: (to be committed)
- **Latest Pushed Commit**: (to be pushed)
- **Commit Subject**: Add PDF bar detection fixtures v0.4
- **Working Tree Status**: Modified
- **Tests & Checks Run**:
  - `python -m pytest` -> 211 passed cleanly
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly with 0 trailing whitespaces
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Bar-detection Taxonomy**: Defined comprehensive reason codes for bar-detection failures:
  - `pdf_barlines_not_detected_in_system`
  - `pdf_barline_candidates_present_but_invalid`
  - `pdf_barline_does_not_cross_staff`
  - `pdf_barline_too_short`
  - `pdf_barline_outside_system_bounds`
  - `pdf_barline_ambiguous`
  - `pdf_bar_boxes_not_constructible`
  - `pdf_bar_detection_succeeded_string_assignment_pending`
  - `pdf_bar_detection_not_enough_for_build_ir`
- **Public Synthetic PDF Fixtures**: Created and generated 5 new PDF fixtures for barline-detection blocker classes:
  - `generated_pdf_bar_boxes_not_constructible.pdf` (only 1 valid barline)
  - `generated_pdf_barlines_ambiguous.pdf` (barline candidates horizontally close < 6.0pt)
  - `generated_pdf_barlines_do_not_cross_staff.pdf` (barlines not crossing tab staff)
  - `generated_pdf_barlines_outside_bounds.pdf` (barlines outside horizontal bounds)
  - `generated_pdf_barlines_too_short.pdf` (barlines too short < 40pt)
  - Regenerated all other synthetic layout diagnostics counterpart PDFs.
- **Reporting & Diagnostics HTML**:
  - Summarized per-system `barline_candidates_count`, `valid_barline_count`, `rejected_barline_count`, and `rejection_reasons`.
  - Propagated new bar-detection metrics into TabRaw candidate `raw` telemetry.
  - Updated the developer grouping diagnostics HTML to render exact vertical candidate and rejection details.
  - Updated HTML remediation hint for the `"bar_detection"` stage to: `"System detection succeeded, but safe bar boxes could not be constructed."`.
- **Pipeline Gates**: Registered the new blocker warning codes inside `src/score2gp/build_ir.py` validation filters to strictly block `build_ir` on unsafe inputs.
- **Tests**: Appended comprehensive unit tests under `tests/test_pdf.py` verifying correct blocker stage, code reporting, candidate telemetry, and `build_ir` rejection for each synthetic scenario.

## Private Smoke Blocker Classification
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Page count**: 2
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **Playable candidates**: 203 (non-playable: 126, total: 329)
  - **Detected systems/staves**: 14 (7 per page)
  - **Detected bar boxes**: 0
  - **Fret candidates with string**: 141 (with system: 162, with bar: 0)
  - **Grouping status**: `missing_pdf_grouping` (due to missing bar barlines and multiple vertical layout ambiguities)
  - **Primary refusal reason**: `musicxml_timing_risk` (69 timing issues, including 63 overfull bars, 1 underfull bar, 2 tie continuity risks, 2 many timing risks, 66 affected events; calibration feasibility `false`)
  - **Secondary reason codes**: `missing_pdf_grouping`
- **`private_input_2`** (`pdf-tab-only`):
  - **Page count**: 1
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **Playable candidates**: 54 (non-playable: 17, total: 71)
  - **Detected systems/staves**: 0 (drawn); 3 ASCII blocks inferred as 3 systems in ASCII tab parsing
  - **Detected bar boxes**: 0
  - **Fret candidates with string**: 54 (with system: 54, with bar: 0)
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary refusal reason**: None (no MusicXML)

## Recommended Next Branch
- **`feature/private-smoke-refresh-after-pdf-bar-detection-v0.1`** (to re-run the local E2E private smoke workflow and verify that the real inputs correctly report detailed bar candidate, accepted, rejected counts, and precise sub-blocker reasons).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
