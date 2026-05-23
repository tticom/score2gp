# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-pdf-system-v0.4`
- **Base Branch**: `main`
- **Current PR**: [#30](https://github.com/tticom/score2gp/pull/30) (Draft)
- **Latest Local Commit**: `334100b8d266c923c039dae766e2334f56b3e3fc`
- **Latest Pushed Commit**: `334100b8d266c923c039dae766e2334f56b3e3fc`
- **Commit Subject**: Refresh private smoke after PDF system diagnostics
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
- Re-ran the private-safe E2E smoke workflow against the real private inputs under the newly integrated PDF system-detection blocker diagnostics (PR #29).
- Evaluated and recorded the detailed warning codes, counts, and stages on the real inputs without modifying gates or copying any private data.
- Confirmed that the new layout blockers cleanly separate:
  - `private_input_1` is classified as `drawn_tab_candidate` and successfully completes system detection but fails bar detection (detected systems: 14, bar boxes: 0), flagging `pdf_system_detected_bar_detection_missing`.
  - `private_input_2` is classified as `ascii_tab_candidate` and fails system detection (detected systems: 0, ASCII blocks: 3), flagging `pdf_drawn_system_not_detected`, `pdf_ascii_system_detected`, `pdf_ascii_system_measure_boundaries_missing`, and `pdf_ascii_system_timing_unavailable`.



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
- **Current Grouping Status**: `missing_pdf_grouping` remains the primary layout blocker. However, we have now verified that the pipeline's stage-split diagnostic hierarchy correctly identifies the exact blocker stages for real private inputs:
  - `private_input_1` is classified as `drawn_tab_candidate` with `primary_blocker_stage: bar_detection` (system detection succeeded with 14 systems, but bar detection is completely missing with 0 bar boxes), flagging `pdf_system_detected_bar_detection_missing`.
  - `private_input_2` is classified as `ascii_tab_candidate` / `unsupported` with `primary_blocker_stage: system_detection` (no drawn systems detected; ASCII blocks are detected but timing/bar boundaries are unavailable), flagging `pdf_drawn_system_not_detected`, `pdf_ascii_system_detected`, `pdf_ascii_system_measure_boundaries_missing`, and `pdf_ascii_system_timing_unavailable`.

## Current Top Blocker Classification
- **`pdf_bar_detection`** (primary layout blocker for `private_input_1` - systems exist but no barlines/bar boxes are detected).
- **`pdf_drawn_system_detection`** (primary layout blocker for `private_input_2` - drawn tab system was not detected or resolved).
- **`pdf_ascii_system_timing_boundary`** (primary ASCII blocker for `private_input_2` - ASCII blocks exist but timing/bar boundaries are unavailable).

## Recommended Next Branch
- **`feature/pdf-bar-detection-public-fixtures-v0.4`** (to introduce public synthetic PDF fixtures for barlines, rectangle/line detections, and bar-box overlays, ensuring that CI validation remains independent of any private materials).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
