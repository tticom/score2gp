# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-pdf-edge-system-boundary-v0.1`
- **Base Branch**: `main`
- **Current PR**: N/A (to be created as Draft PR)
- **Latest Local Commit**: N/A (will commit shortly)
- **Latest Pushed Commit**: N/A (will push shortly)
- **Commit Subject**: Refresh private smoke after PDF edge boundary policy
- **Working Tree Status**: Clean (except modified HANDOFF.md and TASKS.md)
- **Tests & Checks Run**:
  - `python -m pytest` -> 238 passed cleanly in 13.19s
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under Git
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Re-ran the private-safe smoke workflow locally**: Executed `python scripts/private_e2e_smoke.py --out work/private_e2e_smoke_after_pdf_edge_system_boundary_v0_1` successfully.
- **Updated the private-safe blocker summary**: Summarized exact page counts, candidate counts, grouping statuses, warning codes, timing preflight results, and next diagnostic recommendations.
- **Validated conservative fallback rejection policy**: Verified that on `private_input_1` page 2 system 6 (where one accepted boundary and one rejected boundary exist), our new conservative fallback policy successfully rejects unsafe edge fallback due to the ambiguous candidate / rejected barline in the inference direction. It generated clear warnings (`pdf_bar_box_edge_boundary_fallback_rejected`, `pdf_bar_box_edge_boundary_ambiguous`, and `pdf_bar_box_inferred_boundary_requires_clear_system_edge`) and kept grouping as `partial_pdf_grouping`.
- **Identified next blockers and recommended branch**: Evaluated primary/secondary blockers and categorized the next steps.

## Private Smoke Blocker Summary (No Private Content Included)
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **ASCII block count**: 0
  - **Drawn system count**: 14 (8 on page 1, 6 on page 2)
  - **Accepted barline count**: System 6 on page 2 has 1 accepted boundary and 1 rejected boundary. The other 13 systems have accepted barlines and successfully constructed bar boxes.
  - **Rejected barline/boundary count**: 1 on system 6 page 2.
  - **Inferred boundary count**: 0 (rejected).
  - **Fallback accepted/rejected count**: 0 accepted / 1 rejected.
  - **Fallback rejection reason counts**: 1 (`pdf_bar_box_edge_boundary_fallback_rejected` due to rejected candidate / ambiguous barline in the inference direction).
  - **Too-narrow inferred box count**: 0.
  - **Candidate-near-inferred-boundary count**: 0.
  - **Constructed bar box count**: 13 constructed.
  - **Unboxed system count**: 1 (system 6 on page 2).
  - **Systems with playable candidates**: 14.
  - **Unboxed systems with playable candidates**: 1 (system 6 on page 2).
  - **Total candidate count**: 329.
  - **Playable candidate count**: 203.
  - **Non-playable candidate count**: 126.
  - **Candidates assigned to system**: 282.
  - **Candidates assigned to bar**: 265.
  - **Candidates assigned to string**: 141.
  - **Grouping status**: `partial_pdf_grouping`
  - **Primary PDF blocker stage**: `pdf_bar_box_one_boundary_rejected` (due to system 6 on page 2 having a rejected boundary, which correctly rejects fallback and blocks grouping).
  - **Secondary PDF reason codes**:
    - `ambiguous_bar_assignment`
    - `ambiguous_string_assignment`
    - `incomplete_tab_staff`
    - `missing_pdf_barlines`
    - `pdf_bar_box_construction_not_enough_for_build_ir`
    - `pdf_bar_box_edge_boundary_ambiguous`
    - `pdf_bar_box_edge_boundary_fallback_rejected`
    - `pdf_bar_box_edge_system_missing_boundary`
    - `pdf_bar_box_inferred_boundary_not_enough_for_build_ir`
    - `pdf_bar_box_inferred_boundary_requires_clear_system_edge`
    - `pdf_bar_box_missing_right_boundary`
    - `pdf_bar_box_one_boundary_rejected`
    - `pdf_bar_box_requires_two_boundaries`
    - `pdf_bar_boxes_missing`
    - `pdf_bar_boxes_not_constructible`
    - `pdf_bar_detection_not_enough_for_build_ir`
    - `pdf_barline_ambiguous`
    - `pdf_barline_too_short`
    - `pdf_barlines_missing`
    - `pdf_barlines_not_detected_in_system`
    - `pdf_candidate_near_missing_bar_boundary`
    - `pdf_candidate_outside_bar`
    - `pdf_candidate_outside_system`
    - `pdf_candidate_unassigned_due_to_unboxed_system`
    - `pdf_candidate_unassigned_to_bar`
    - `pdf_candidates_unassigned_to_bar`
    - `pdf_candidates_unassigned_to_string`
    - `pdf_candidates_unassigned_to_system`
    - `pdf_drawn_system_ambiguous`
    - `pdf_grouping_confidence_below_threshold`
    - `pdf_grouping_not_safe_for_build_ir`
    - `pdf_layout_detection_requires_manual_review`
    - `pdf_missing_pdf_grouping_blocks_build_ir`
    - `pdf_multi_system_order_ambiguous`
    - `pdf_partial_grouping_one_system_unboxed`
    - `pdf_partial_grouping_with_playable_candidates`
    - `pdf_partial_system_detection`
    - `pdf_string_assignment_ambiguous`
    - `pdf_string_assignment_missing`
    - `pdf_system_bbox_ambiguous`
    - `pdf_system_order_ambiguous`
    - `pdf_tab_staff_ambiguous`
    - `pdf_tab_staff_incomplete`
  - **Timing blocker stage**: `musicxml_timing_repair_not_safe` (preflight VoiceOverlapError with 66 overfull or overlapping events).
  - **Calibration possible status**: `unrecoverable_scenario` (due to timing risk).
  - **Alignment status**: `failed`.
  - **ScoreIR gate status**: `refused`.
  - **GP writing status**: `not_attempted` (refused at IR gate).
  - **Stage reached**: PDF extraction raw output completed, MusicXML preflight timing risk flagged.
  - **Artifact paths under work/**:
    - `work/private_e2e_smoke_after_pdf_edge_system_boundary_v0_1/private_input_1/extracted.tabraw.json`
    - `work/private_e2e_smoke_after_pdf_edge_system_boundary_v0_1/private_input_1/warnings.json`
    - `work/private_e2e_smoke_after_pdf_edge_system_boundary_v0_1/private_input_1/musicxml-unrecoverable-timing-report.json`
    - `work/private_e2e_smoke_after_pdf_edge_system_boundary_v0_1/private_input_1/musicxml-unrecoverable-timing-report.html`
    - `work/private_e2e_smoke_after_pdf_edge_system_boundary_v0_1/private_input_1/build_error.json`

- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Page count**: 1
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **ASCII block count**: 1
  - **Total candidate count**: 71.
  - **Playable candidate count**: 54.
  - **Non-playable candidate count**: 17.
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary PDF blocker stage**: `drawn_system_detection` and `ascii_system_detection` (`pdf-tab-system-not-detected`).
  - **Timing status**: `not_attempted`.

## Comparison with Previous Blocker Summary
- **Previous summary**: `private_input_1` had grouping status `partial_pdf_grouping` and system 6 on page 2 had one accepted boundary and one rejected boundary. Under PR #39 (v0.7), system 6 was simply unboxed as `pdf_bar_box_one_boundary_rejected`.
- **Current summary**: Under the new conservative edge system boundary fallback policy (PR #40), fallback is analyzed and programmatically **rejected** due to ambiguous vertical candidates / rejected barline in the inference direction. Consequently, system 6 remains safely unboxed under `pdf_bar_box_one_boundary_rejected` with rich explicit warning details (`pdf_bar_box_edge_boundary_fallback_rejected`, `pdf_bar_box_edge_boundary_ambiguous`, `pdf_bar_box_inferred_boundary_requires_clear_system_edge`). The behavior is exactly as expected, keeping strict safety gates without regressions.

## Current Top Blocker Classification
1. **`pdf_bar_box_one_boundary_rejected`** (Primary PDF grouping blocker stage)
2. **`musicxml_timing_repair_not_safe`** (Primary MusicXML timeline voice overlap blocker)

## Next Recommended Branch
- **`feature/pdf-edge-boundary-reporting-v0.9`**: Since fallback is correctly rejected and the same blocker remains, the next step is to improve edge-boundary error reporting/diagnostics.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
