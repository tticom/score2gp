# Handoff

## Metadata
- **Current Branch**: `feature/pdf-system-detection-public-fixtures-v0.4`
- **Base Branch**: `main`
- **Current PR**: [#29](https://github.com/tticom/score2gp/pull/29) (Draft)
- **Latest Local Commit**: `53f90c329f59edd138ce2500b5c3c109037a9b32`
- **Latest Pushed Commit**: `53f90c329f59edd138ce2500b5c3c109037a9b32`
- **Commit Subject**: Add PDF system detection fixtures v0.4
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 205 passed cleanly
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Added public synthetic PDF layout fixtures for unresolved drawn staff lines, overlapping systems, ASCII tab blocks without bars, mixed pages, system-detected no barlines, and valid grouped counterparts.
- Refined the warning taxonomy in `src/score2gp/pdf.py` with 11 precise codes (e.g. `pdf_drawn_system_not_detected`, `pdf_drawn_system_ambiguous`, `pdf_drawn_staff_lines_unresolved`, `pdf_ascii_system_detected`, `pdf_ascii_system_measure_boundaries_missing`, `pdf_ascii_system_timing_unavailable`, `pdf_system_detected_bar_detection_missing`, etc.).
- Refined diagnostics in `src/score2gp/report.py` to classify `input_class` and `primary_blocker_stage`, distinguishing system-detection blockers from downstream bar-detection blockers.
- Updated developer-facing HTML grouping report with clear remediation hints.
- Updated documentation (`architecture.md`, `workflow.md`, `limitations.md`) and task status (`TASKS.md`).


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
  - **Detailed PDF warning codes**: `pdf_multi_system_order_ambiguous`, `pdf_system_order_ambiguous`, `pdf_tab_staff_ambiguous`, `pdf_system_bbox_ambiguous`, `pdf_partial_system_detection`, `pdf_grouping_not_safe_for_build_ir`, `pdf_missing_pdf_grouping_blocks_build_ir`, `pdf_layout_detection_requires_manual_review`, `pdf_partial_grouping_with_playable_candidates`, `pdf_grouping_confidence_below_threshold`, `ambiguous_string_assignment`, `incomplete_tab_staff`, `missing_pdf_barlines`, `pdf_bar_boxes_missing`, `pdf_barlines_missing`, `pdf_candidate_outside_system`, `pdf_candidates_unassigned_to_bar`, `pdf_candidates_unassigned_to_string`, `pdf_candidates_unassigned_to_system`, `pdf_string_assignment_ambiguous`, `pdf_string_assignment_missing`, `pdf_tab_staff_incomplete`
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
  - **Secondary reason codes**: `missing_pdf_grouping`, `pdf-tab-system-not-detected`
  - **Detailed PDF warning codes**: `pdf-tab-system-not-detected`, `pdf_text_geometry_present_but_no_safe_system`, `pdf_drawn_geometry_present_but_staff_unresolved`, `pdf_tab_staff_lines_fragmented`, `ascii_tab_detected`, `ascii_tab_timing_unavailable`, `ascii_tab_measure_boundary_missing`, `unsupported_ascii_tab_rhythm`, `pdf_no_systems_detected`, `pdf_tab_staff_missing`, `pdf_string_lines_missing`, `pdf_tab_candidates_present_but_system_not_detected`, `pdf_grouping_not_safe_for_build_ir`, `pdf_missing_pdf_grouping_blocks_build_ir`, `pdf_layout_detection_requires_manual_review`, `pdf_partial_grouping_with_playable_candidates`

## Comparison with Previous Summary
- **Previous Grouping Blocker**: `missing_pdf_grouping` and `pdf-tab-system-not-detected` were the main layout blockers, but the precise boundary between system detection and downstream bar detection was blurred.
- **Current Grouping Status**: `missing_pdf_grouping` remains the primary layout blocker. However, we have now introduced a clear stage-split diagnostic hierarchy. System detection success and bar detection success are tracked as distinct booleans, and `primary_blocker_stage` maps to `system_detection`, `bar_detection`, `string_assignment`, `timing_alignment`, or `unsupported_input_class`.
- **Diagnostics Refinement**: The public warning codes and classifications now perfectly model the splits: `private_input_1` is classified as `drawn_tab_candidate` with `primary_blocker_stage: bar_detection` (since systems are detected but barlines/bar boxes are 0), whereas `private_input_2` maps to `primary_blocker_stage: system_detection` (since no drawn systems are found and ASCII blocks lack aligned bar separators).

## Current Top Blocker Classification
- **`pdf_system_detection`** (primary blocker for `private_input_2` - unresolved staff lines and no drawn systems detected)
- **`pdf_bar_detection`** (primary blocker for `private_input_1` - systems exist but no barlines/bar boxes are detected)

## Recommended Next Branch
- **`feature/private-smoke-refresh-after-pdf-system-detection-v0.1`** (to re-run the local private E2E diagnostic smoke workflow and verify that the real inputs are correctly classified and reported under the new distinct system/bar blocker stages, input classes, and taxonomy codes).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.

