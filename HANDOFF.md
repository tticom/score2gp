# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-pdf-barline-validation-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #34](https://github.com/tticom/score2gp/pull/34) (Draft)
- **Latest Local Commit**: `37992c8`
- **Latest Pushed Commit**: `37992c8`
- **Commit Subject**: Refresh private smoke after PDF barline validation
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 213 passed cleanly
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Re-ran the local private-safe end-to-end E2E diagnostic smoke test workflow against real private inputs after merging the PDF barline validation fixtures v0.5.
- Confirmed that the new relative staff-crossing rules successfully accept compact barlines on the real inputs, resolving the previous universal barline-validation blocker for `private_input_1`.
- Verified that 13 out of 14 systems in `private_input_1` now successfully construct bar boxes and assign fret candidates to bars.

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
  - **Accepted compact barlines**: Yes! Telemetry shows compact barlines (height = 31.89pt, below 40pt absolute threshold) were successfully accepted on page 1 and page 2 systems under the relative crossing check (crossing 5 gaps of 6.0pt spacing staff).
  - **Bar box count**: 14 (constructed for systems 1-7 on page 1, systems 1-5 and 7 on page 2; missing for system 6 on page 2).
  - **Playable fret candidates**: 203 (non-playable: 126, total: 329).
  - **Candidates assigned to system**: 282.
  - **Candidates assigned to bar**: 265.
  - **Candidates assigned to string**: 141 (fret candidates).
  - **Grouping status**: `partial_pdf_grouping` (improved from `missing_pdf_grouping`).
  - **Primary blocker stage**: `timing_alignment` (MusicXML timing risk prevents ScoreIR output: 66 overfull or overlapping event(s) would violate ScoreIR timing; timing status `failed`).
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
- **Current PDF grouping status**: Thanks to relative staff-crossing validation, 13 out of 14 systems now successfully accept barlines and construct bar boxes. Fret candidates are assigned to bars. The grouping status has improved to `partial_pdf_grouping` (due to 1 remaining system on page 2 and unassigned/ambiguous candidates).
- **Previous primary ScoreIR blocker**: PDF grouping failure blocked `build_ir` from even trying to compile ScoreIR.
- **Current primary ScoreIR blocker**: PDF grouping is now resolved enough that `build_ir` preflights MusicXML timing, and is strictly blocked by `musicxml_timing_risk` (unrecoverable same-voice cursor overlaps).

## Current Top Blocker Classification
- **`musicxml_timing_repair_not_safe`** (primary timing/ScoreIR blocker for `private_input_1`).
- **`pdf_drawn_system_detection`** / **`pdf_ascii_system_timing_boundary`** (primary PDF grouping blockers for `private_input_2`).

## Recommended Next Branch
- **`feature/musicxml-unrecoverable-timing-report-v0.1`** (to introduce a robust, private-safe, detailed HTML/JSON unrecoverable-timing reporting path that helps users identify exactly where and why the MusicXML timeline cursor failed to align with the tab staff).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
