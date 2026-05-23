# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-pdf-bar-box-edge-cases-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft PR (to be created)
- **Latest Local Commit**: (to be populated after commit)
- **Latest Pushed Commit**: (to be populated after push)
- **Commit Subject**: Refresh private smoke after PDF bar box edge cases
- **Working Tree Status**: Modified project files staged for commit
- **Tests & Checks Run**:
  - `python -m pytest` -> 228 passed cleanly
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Re-ran Diagnostic Smoke**: Re-ran the local private-safe E2E diagnostic smoke workflow against real private score inputs under the ignored output path `work/private_e2e_smoke_after_pdf_bar_box_edge_cases_v0_1/`.
- **Taxonomy Validation**: Programmatically validated that the new layout heuristics, warning codes, empty system policy, and candidate boundary checks implemented in PR #38 are correctly invoked and reported for real private score layouts.
- **Taxonomy Verification**: Confirmed that the unboxed System 6 on page 2 of `private_input_1` now successfully reports the newly added taxonomy edge-case codes: `pdf_bar_box_one_boundary_rejected` (1 accepted and 1 rejected boundary), `pdf_bar_box_edge_system_missing_boundary` (missing right/left boundaries), `pdf_candidate_unassigned_due_to_unboxed_system`, and `pdf_candidate_near_missing_bar_boundary`.

## Private Smoke Blocker Classification (No Private Content Included)
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Drawn system count**: 14 (8 on page 1, 6 on page 2)
  - **Barline candidates exist on systems**: Yes (2 candidates detected on most systems)
  - **Valid barline count per system**: 2 on most systems (systems 1-8 on page 1, systems 1-5 on page 2), but 1 on page 2 system 6.
  - **Rejected barline count per system**: 0 on most systems, but 1 on page 2 system 6.
  - **Accepted compact barlines**: Yes! Compact barlines were successfully accepted on page 1 (systems 1-8) and page 2 (systems 1-5) under the relative crossing check.
  - **Bar box count**: 13 successfully constructed (8 on page 1, 5 on page 2; missing for system 6 on page 2).
  - **Playable fret candidates**: 203 (non-playable: 126, total: 329).
  - **Candidates assigned to system**: 282.
  - **Candidates assigned to bar**: 265.
  - **Candidates assigned to string**: 141 (fret candidates).
  - **Grouping status**: `partial_pdf_grouping`.
  - **Primary blocker stage**: `timing_alignment` (MusicXML timing risk prevents ScoreIR output; timing status `failed`).
  - **Primary PDF blocker stage**: `pdf_bar_box_one_boundary_rejected` (due to system 6 on page 2 missing one boundary while the other is rejected, leaving it unboxed with playable candidates).
  - **Primary PDF reason code**: `pdf_bar_box_one_boundary_rejected`.
  - **Secondary PDF reason codes**: `pdf_bar_box_edge_system_missing_boundary`, `pdf_candidate_unassigned_due_to_unboxed_system`, `pdf_candidate_near_missing_bar_boundary`, `pdf_barline_too_short`, `pdf_barline_ambiguous`, `pdf_bar_box_requires_two_boundaries`, `pdf_bar_boxes_not_constructible`, `pdf_barlines_not_detected_in_system`, `pdf_bar_detection_not_enough_for_build_ir`, `ambiguous_bar_assignment`, `ambiguous_string_assignment`, `pdf_candidate_unassigned_to_bar`, `pdf_candidates_unassigned_to_bar`, `pdf_candidates_unassigned_to_string`, `pdf_candidates_unassigned_to_system`.
  - **ScoreIR gate status**: `refused`.

- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Page count**: 1
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary PDF blocker stage**: `drawn_system_detection` and `ascii_system_detection`
  - **Primary PDF reason code**: `pdf-tab-system-not-detected`

## Comparison with Previous Blocker Summary
- **Previous PDF grouping status**: `private_input_1` had 14 systems, 13 boxed, 1 unboxed. Grouping status was `partial_pdf_grouping`. System 6 on page 2 was unboxed.
- **Current PDF grouping status**: Remains `partial_pdf_grouping` with 14 systems (13 boxed, 1 unboxed). System 6 on page 2 remains unboxed.
- **Taxonomy update confirmation**: The unboxed system 6 on page 2 is now successfully identified and classified under the new taxonomy with the new edge case codes: `pdf_bar_box_one_boundary_rejected` (1 accepted and 1 rejected boundary), `pdf_bar_box_edge_system_missing_boundary` (missing right/left boundaries), `pdf_candidate_unassigned_due_to_unboxed_system`, and `pdf_candidate_near_missing_bar_boundary`.

## Current Top Blocker Classification
- PDF layout blocker: **`pdf_bar_box_one_boundary_rejected`** (due to unboxed system 6 on page 2 having playable candidates and one rejected boundary).
- Timing blocker: **`musicxml_timing_repair_not_safe`** (due to overfull timeline cursor overlaps in MusicXML timing preflight).

## Next Recommended Task
- **`feature/pdf-edge-system-boundary-public-fixtures-v0.8`**: Implement public synthetic fixtures and heuristics to handle edge systems with one rejected boundary, allowing them to construct complete bar boxes if safe fallback boundaries or page margins are available.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
