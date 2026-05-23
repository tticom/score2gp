# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-pdf-layout-v0.3`
- **Base Branch**: `main`
- **Current PR**: TBD
- **Latest Local Commit**: `0f5fb37d97e6ac668cb460f622d27ae300d82204`
- **Latest Pushed Commit**: `0f5fb37d97e6ac668cb460f622d27ae300d82204`
- **Commit Subject**: Merge pull request #27 from tticom/feature/pdf-layout-public-fixtures-v0.3
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 197 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Re-ran the private-safe E2E smoke workflow against the private inputs under the newly integrated PDF layout blocker diagnostics (PR #27).
- Evaluated and recorded the detailed warning codes, counts, and statuses on the real inputs without modifying gates, converting them, or copying any private data.

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
- **Previous Grouping Blocker**: `missing_pdf_grouping` and `pdf-tab-system-not-detected`.
- **Current Grouping Status**: `missing_pdf_grouping` remains the primary layout blocker. For `private_input_1`, drawn systems exist but barlines/bar boxes are completely missing, alongside vertical layout ambiguities. For `private_input_2`, no drawn systems were detected, while ASCII tab blocks are successfully extracted but lack timing/barlines.
- **Diagnostics Refinement**: The run has successfully validated the newly refined PDF blocker warnings (PR #27) on real private inputs.

## Current Top Blocker Classification
- **`pdf_system_detection`** (primary blocker for `private_input_2` - unresolved staff lines and no drawn systems detected)
- **`pdf_bar_detection`** (primary blocker for `private_input_1` - systems exist but no barlines/bar boxes are detected)

## Recommended Next Branch
- **`feature/pdf-system-detection-public-fixtures-v0.4`** (to introduce public synthetic fixtures for unresolved staff lines, OCR-like / scanned-tab system boundaries, or ASCII tab calibration, and refine layout/system detection heuristics).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
