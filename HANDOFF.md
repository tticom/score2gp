# Handoff

## Metadata
- **Current Branch**: `feature/musicxml-unrecoverable-timing-report-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #35](https://github.com/tticom/score2gp/pull/35) (Draft)
- **Latest Local Commit**: `ebcc67b`
- **Latest Pushed Commit**: `ebcc67b`
- **Commit Subject**: Add unrecoverable MusicXML timing report
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 215 passed cleanly
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Added a robust, private-safe HTML/JSON report for unrecoverable MusicXML timing failures (`musicxml-unrecoverable-timing-report.json`, `musicxml-unrecoverable-timing-report.html`).
- Integrated report generation with `build-ir` failure diagnostics and the local private E2E smoke test workflow.
- Ensured JSON report is the source of truth, containing anonymised telemetry (calibration blockers, overfull/underfull measure counts, expected vs actual ticks breakdown per measure/voice, affected event counts) without exposing private pitch step/octave values, chord symbols, lyrics, or raw notation text.
- Added visually premium dark-mode HTML styling for the unrecoverable timing report, featuring clear verdict blocks, summaries, breakdown tables, and remediation guidance.
- Added public synthetic tests proving report correctness, private safety, and integration.

## Private Smoke Blocker Classification
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **Drawn system count**: 14 (7 per page)
  - **Barline candidates exist on systems**: Yes (2 candidates detected on most systems)
  - **Valid barline count per system**: 2 on most systems (systems 1-7 on page 1, systems 1-5 and 7 on page 2), but 0 on page 2 system 6.
  - **Rejected barline count per system**: 0 on most systems, but 2 on page 2 system 6 (rejected as `pdf_barline_too_short` / `pdf_barline_ambiguous`).
  - **Accepted compact barlines**: Yes! Compact barlines (height = 31.89pt, below 40pt absolute threshold) were successfully accepted on page 1 and page 2 systems under the relative crossing check.
  - **Bar box count**: 14 (constructed for systems 1-7 on page 1, systems 1-5 and 7 on page 2; missing for system 6 on page 2).
  - **Playable fret candidates**: 203 (non-playable: 126, total: 329).
  - **Candidates assigned to system**: 282.
  - **Candidates assigned to bar**: 265.
  - **Candidates assigned to string**: 141 (fret candidates).
  - **Grouping status**: `partial_pdf_grouping` (improved from `missing_pdf_grouping`).
  - **Primary blocker stage**: `timing_alignment` (MusicXML timing risk prevents ScoreIR output; timing status `failed`).
  - **Primary PDF blocker stage**: `bar_detection` (due to system 6 on page 2 missing bar boxes, and some candidates unassigned to bar/system).
  - **Primary PDF reason code**: `pdf_system_detection_succeeded_but_grouping_incomplete`
  - **Secondary PDF reason codes**: `pdf_barlines_not_detected_in_system`, `pdf_bar_boxes_not_constructible`, `pdf_bar_detection_not_enough_for_build_ir`, `pdf_barline_too_short`, `pdf_barline_ambiguous`, `pdf_multi_system_order_ambiguous`, `pdf_system_order_ambiguous`, `pdf_tab_staff_ambiguous`, `pdf_system_bbox_ambiguous`
  - **ScoreIR gate status**: `refused`.
  - **GP writing status**: `not_attempted`.

- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Page count**: 1
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **Drawn system count**: 0
  - **ASCII block count**: 3
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary PDF blocker stage**: `drawn_system_detection` and `ascii_system_detection`
  - **Primary PDF reason code**: `pdf-tab-system-not-detected`
  - **Secondary PDF reason codes**: `missing_pdf_grouping`, `pdf-tab-system-not-detected`
  - **Timing status**: `not_attempted`
  - **ScoreIR gate status**: `not_attempted`

## Comparison with Previous Summary
- **Previous PDF grouping status**: `private_input_1` had grouping status `missing_pdf_grouping` because ALL barline candidates were rejected as `pdf_barline_too_short`. Zero valid barlines were found, and zero bar boxes were constructed.
- **Current PDF grouping status**: Thanks to relative staff-crossing validation, 13 out of 14 systems now successfully accept barlines and construct bar boxes. Fret candidates are assigned to bars. The grouping status has improved to `partial_pdf_grouping`.
- **Previous primary ScoreIR blocker**: PDF grouping failure blocked `build_ir` from even trying to compile ScoreIR.
- **Current primary ScoreIR blocker**: PDF grouping is now resolved enough that `build_ir` preflights MusicXML timing, and is strictly blocked by `musicxml_timing_risk` (unrecoverable same-voice cursor overlaps), generating the anonymised unrecoverable timing JSON and HTML reports.

## Current Top Blocker Classification
- **`musicxml_timing_repair_not_safe`** (primary timing/ScoreIR blocker for `private_input_1`).
- **`pdf_drawn_system_detection`** / **`pdf_ascii_system_timing_boundary`** (primary PDF grouping blockers for `private_input_2`).

## Next Recommended Task
- **`feature/pdf-bar-box-construction-public-fixtures-v0.6`** (to introduce public synthetic fixtures and heuristics to handle remaining partial grouping layout blockers like missing barlines on system 6 and unassigned candidates, moving from `partial_pdf_grouping` to full `pdf_grouped` status).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
