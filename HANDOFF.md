# Handoff

## Metadata
- **Current Branch**: `feature/pdf-bar-box-edge-cases-public-fixtures-v0.7`
- **Base Branch**: `main`
- **Current PR**: Draft PR (to be created)
- **Latest Local Commit**: `c45621bba98654c68126e0a523bb84a5a698b9ec` (prior to committing task additions)
- **Latest Pushed Commit**: `c45621bba98654c68126e0a523bb84a5a698b9ec`
- **Commit Subject**: Merge PR #37 Refresh private smoke after PDF bar box construction
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
- **Refined PDF Grouping Taxonomy**: Refined and registered the new bar-box edge-case codes: `pdf_bar_box_single_system_failure`, `pdf_bar_box_edge_system_missing_boundary`, `pdf_bar_box_one_boundary_rejected`, `pdf_barline_short_but_near_staff_boundary`, `pdf_barline_ambiguous_on_edge_system`, `pdf_candidate_unassigned_due_to_unboxed_system`, `pdf_candidate_near_missing_bar_boundary`, `pdf_boundary_candidate_blocks_full_grouping`, `pdf_full_grouping_requires_all_systems_boxed`, `pdf_grouping_complete_all_playable_candidates_assigned`.
- **Empty System Toleration Heuristic**: Implemented page-level token pre-scanning to identify systems that contain actual playable fret candidates. Tolerated empty/decorative systems without playable candidates so they do not trigger system-level blockers like `pdf_partial_grouping_one_system_unboxed` or block `grouped` layout status.
- **Programmatic PDF Fixtures**: Extended `make_bar_box_construction_pdfs.py` to programmatically generate new edge-case PDFs: `generated_pdf_empty_system_policy.pdf`, `generated_pdf_one_accepted_one_rejected.pdf`, and `generated_pdf_two_short_barlines.pdf`.
- **Exhaustive Testing**: Added comprehensive assertions in `tests/test_pdf.py` verifying all edge-case warnings, empty system policy behavior, and proper IR-level rejection for incomplete layout groupings.
- **Strict Whitelist Alignment**: Aligned warning whitelists in `build_ir.py` and `report.py` to ensure all new partial grouping reason codes cleanly block ScoreIR generation.

## Private Smoke Blocker Classification (No Private Content Included)
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Drawn system count**: 14 (8 on page 1, 6 on page 2)
  - **Grouping status**: `partial_pdf_grouping`.
  - **Primary blocker stage**: `timing_alignment` (MusicXML timing risk prevents ScoreIR output).
  - **Primary PDF blocker stage**: `pdf_bar_box_construction` (due to system 6 on page 2 missing bar boxes, and some candidates unassigned or ambiguous).
  - **Primary PDF reason code**: `pdf_partial_grouping_one_system_unboxed`.
  - **ScoreIR gate status**: `refused`.

- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Page count**: 1
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary PDF blocker stage**: `drawn_system_detection` and `ascii_system_detection`
  - **Primary PDF reason code**: `pdf-tab-system-not-detected`

## Next Recommended Task
- **`feature/private-smoke-refresh-after-pdf-bar-box-edge-cases-v0.1`**: Re-run the private smoke E2E workflow on the new heuristics/warnings to verify if the unboxed system 6 on page 2 of `private_input_1` gets correctly identified and classified under the new taxonomy.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
