# Handoff

## Metadata
- **Current Branch**: `feature/pdf-string-assignment-public-fixtures-v0.4`
- **Base Branch**: `main`
- **Current PR**: None yet (Draft PR to be created)
- **Latest Local Commit**: `d30e040`
- **Latest Pushed Commit**: `9443187` (PR #42 merge is `b4a5265` on main)
- **Commit Subject**: Implement PDF string assignment heuristics and public fixtures
- **Working Tree Status**: Clean (except modified `HANDOFF.md` once saved)
- **Tests & Checks Run**:
  - `python -m pytest` -> 249 passed cleanly in 14.70s
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under Git
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Added 10 Public Synthetic PDF Fixtures**: Created a programmatic generator `tests/fixtures/pdf/make_string_assignment_pdfs.py` compiling 10 public synthetic PDF fixtures under `tests/fixtures/pdf/` mapping to key string assignment conditions:
  1. `generated_pdf_string_assignment_valid.pdf`: Six-line tab staff with single-digit fret numbers centered on each string.
  2. `generated_pdf_string_assignment_multidigit.pdf`: Valid staff with multi-digit fret numbers (e.g., "10", "12", "15").
  3. `generated_pdf_string_assignment_offset_tolerant.pdf`: Candidate slightly above/below a string line but inside the tolerance threshold.
  4. `generated_pdf_string_assignment_between_lines.pdf`: Candidate exactly between two string lines.
  5. `generated_pdf_string_assignment_outside_staff.pdf`: Candidate outside the top/bottom staff region.
  6. `generated_pdf_string_assignment_compact_staff.pdf`: Compact staff where vertical spacing between lines is too small (`< 8.0`).
  7. `generated_pdf_string_assignment_techniques.pdf`: Inline technique markers near strings (e.g., 'h', 'p', '/').
  8. `generated_pdf_string_assignment_chords.pdf`: Chord symbols above the staff.
  9. `generated_pdf_string_assignment_grouped_success.pdf`: Fully grouped page where system, bar, and string assignment all succeed.
  10. `generated_pdf_string_assignment_upstream_blocked.pdf`: String assignment succeeds but upstream edge-boundary/bar-box failures remain.
- **Defined Taxonomy of 14 String-Related Warning/Reason/Provenance Codes**:
  - `pdf_string_assignment_nearest_line`: Success code indicating a fret candidate was successfully assigned to the nearest string line.
  - `pdf_string_assignment_outside_staff`: Blocker warning for a fret candidate lying outside the vertical bounds of the tab staff.
  - `pdf_string_assignment_between_lines`: Blocker warning for a fret candidate lying exactly between two string lines.
  - `pdf_string_assignment_too_far_from_line`: Blocker warning for a fret candidate too far from any string line to assign safely.
  - `pdf_string_assignment_overlaps_multiple_bands`: Blocker warning for a fret candidate whose height overlaps multiple string lines.
  - `pdf_string_assignment_confidence_below_threshold`: Blocker warning for low-confidence string assignment.
  - `pdf_string_assignment_compact_staff_ambiguous`: Blocker warning for compact staff spacing preventing safe assignment.
  - `pdf_playable_candidate_requires_string_assignment`: Blocker warning that playable fret candidates require unambiguous string assignment.
  - `pdf_non_playable_text_not_string_assigned`: Info code indicating non-playable text candidates do not require string assignment.
  - `pdf_multidigit_fret_string_assigned`: Success code for a multi-digit fret candidate successfully assigned.
  - `pdf_string_assignment_not_enough_for_build_ir`: Blocker warning indicating one or more playable candidates lack safe string assignment.
  - `pdf_string_assignment_succeeded_upstream_grouping_still_blocks`: Info warning indicating string assignment succeeded, but upstream system/bar grouping blockers prevent full grouping.
  - `pdf_candidates_unassigned_to_string`: Blocker warning indicating candidates inside system/bar are not assignable to any string.
  - `ambiguous_string_assignment`: Blocker warning indicating candidate is too far or ambiguous.
- **Implemented Conservative Heuristics in Layout Parsing**:
  - Refined `string_for_y` in `src/score2gp/pdf.py` to analyze line spacing, height, compact spacing (`< 8.0`), outside staff bounds, and between-strings midpoints.
  - Refined `_extract_pdf_text_candidates` to assign strings, calculate vertical height, classify non-playable text elements (chords, techniques), and attach correct warning/provenance codes.
- **Corrected Compiler Gates and Blockers Whitelists**:
  - Correctly categorized Phase 9 string assignment codes, ensuring success/info codes (like `nearest_line`, `multidigit`, `non_playable_text_excluded`, and `succeeded_upstream_grouping_still_blocks`) are **excluded** from build-blocking whitelists (`drawn_grouping_codes` in `pdf.py` and `_tabraw_unsafe_grouping_warning_codes` in `build_ir.py`), while strict blockers block ScoreIR building.
  - Robustly refined `_append_grouping_warnings` to gather all candidate and page warnings when identifying upstream blockers.
- **Enriched HTML/JSON Diagnostics**:
  - Appended string assignment metrics, blockers, and remediation advice to Master Grouping HTML/JSON reports in `report.py`.
  - Added per-candidate string distance and assignment details to system-level HTML tables.
- **Robust Candidate Classification and Capping**:
  - Excluded words containing "string" or "strings" from being classified as technique-text because of the "ring" token, resolving title extraction issues.
  - Only cap candidate confidence to `0.65` when actual unsafe/blocker layout warnings are present.

## Private Smoke Blocker Summary (No Private Content Included)
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **ASCII block count**: 0
  - **Drawn system count**: 14 (8 on page 1, 6 on page 2)
  - **Accepted barline count**: System 6 on page 2 has 1 accepted boundary and 1 rejected boundary. The other 13 systems have accepted barlines and successfully constructed bar boxes.
  - **Constructed bar box count**: 13 constructed.
  - **Unboxed system count**: 1 (system 6 on page 2).
  - **Total candidate count**: 329.
  - **Playable candidate count**: 203.
  - **Non-playable candidate count**: 126.
  - **Candidates assigned to system**: 282.
  - **Candidates assigned to bar**: 265.
  - **Candidates assigned to string**: 141.
  - **Grouping status**: `partial_pdf_grouping`
  - **Primary PDF blocker stage**: `pdf_bar_box_one_boundary_rejected` (due to system 6 on page 2 having a rejected boundary, which correctly rejects fallback and blocks grouping).
  - **Timing blocker stage**: `musicxml_timing_repair_not_safe` (preflight VoiceOverlapError with 66 overfull or overlapping events).
  - **ScoreIR gate status**: `refused` (blocked by PDF grouping and timing).

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
- **Previous summary**: `private_input_1` had grouping status `partial_pdf_grouping` and system 6 on page 2 had fallback rejected safely under PR #42 (v0.9).
- **Current summary**: Rejection behavior remains correctly strict, keeping `partial_pdf_grouping` and blocking ScoreIR generation. Non-playable chord symbols and techniques are successfully preserved and excluded from string blocking. Success codes do not block the build, and the diagnostics accurately report the string metrics (141 candidates assigned to string).

## Current Top Blocker Classification
1. **`pdf_bar_box_one_boundary_rejected`** (Primary PDF grouping blocker stage)
2. **`musicxml_timing_repair_not_safe`** (Primary MusicXML timeline voice overlap blocker)

## Next Recommended Branch
- **`feature/pdf-fret-refinement-v0.5`**: Once the draft PR for string assignment is merged into main, the next recommended branch is `feature/pdf-fret-refinement-v0.5` to refine fret number optical bounds and handle OCR/digit alignment edge cases.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
