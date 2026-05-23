# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-pdf-bar-box-construction-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #37](https://github.com/tticom/score2gp/pull/37) (Draft)
- **Latest Local Commit**: `3c4baee`
- **Latest Pushed Commit**: `3c4baee`
- **Commit Subject**: Refresh private smoke after PDF bar box construction
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 225 passed cleanly
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Re-ran the local private-safe E2E diagnostic smoke workflow against real private score inputs under the ignored output path `work/private_e2e_smoke_after_pdf_bar_box_construction_v0_1/`.
- Programmatically validated that the new layout heuristics, warning codes, and candidate boundary checks implemented in PR #36 are correctly invoked and reported for real private score layouts.
- Identified that `private_input_1` successfully compiles 8 out of 8 systems on page 1 and 5 out of 6 systems on page 2 (total 13 out of 14 systems boxed and grouped successfully), while page 2 system 6 fails with precise bar-box construction warning codes.
- Confirmed that candidate unassigned/ambiguous warnings are accurately logged in warnings telemetry.

## Private Smoke Blocker Classification
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **Drawn system count**: 14 (8 on page 1, 6 on page 2)
  - **Barline candidates exist on systems**: Yes (2 candidates detected on most systems)
  - **Valid barline count per system**: 2 on most systems (systems 1-8 on page 1, systems 1-5 on page 2), but 0 on page 2 system 6.
  - **Rejected barline count per system**: 0 on most systems, but 2 on page 2 system 6.
  - **Accepted compact barlines**: Yes! Compact barlines were successfully accepted on page 1 (systems 1-8) and page 2 (systems 1-5) under the relative crossing check.
  - **Bar box count**: 13 successfully constructed (8 on page 1, 5 on page 2; missing for system 6 on page 2).
  - **Playable fret candidates**: 203 (non-playable: 126, total: 329).
  - **Candidates assigned to system**: 282.
  - **Candidates assigned to bar**: 265.
  - **Candidates assigned to string**: 141 (fret candidates).
  - **Grouping status**: `partial_pdf_grouping`.
  - **Primary blocker stage**: `timing_alignment` (MusicXML timing risk prevents ScoreIR output; timing status `failed`).
  - **Primary PDF blocker stage**: `pdf_bar_box_construction` (due to system 6 on page 2 missing bar boxes, and some candidates unassigned or ambiguous).
  - **Primary PDF reason code**: `pdf_partial_grouping_one_system_unboxed`.
  - **Secondary PDF reason codes**: `pdf_barline_too_short`, `pdf_barline_ambiguous`, `pdf_bar_box_requires_two_boundaries`, `pdf_bar_boxes_not_constructible`, `pdf_barlines_not_detected_in_system`, `pdf_bar_detection_not_enough_for_build_ir`, `ambiguous_bar_assignment`, `ambiguous_string_assignment`, `pdf_candidate_unassigned_to_bar`, `pdf_candidates_unassigned_to_bar`, `pdf_candidates_unassigned_to_string`, `pdf_candidates_unassigned_to_system`.
  - **ScoreIR gate status**: `refused`.
  - **GP writing status**: `not_attempted`.

- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Page count**: 1
  - **Text detected**: Yes
  - **Geometry detected**: Yes (PyMuPDF detected drawing lines in the PDF, but no drawn systems were resolved)
  - **Drawn system count**: 0
  - **ASCII block count**: 3
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary PDF blocker stage**: `drawn_system_detection` and `ascii_system_detection`
  - **Primary PDF reason code**: `pdf-tab-system-not-detected`
  - **Secondary PDF reason codes**: `missing_pdf_grouping`, `pdf-tab-system-not-detected`
  - **Timing status**: `not_attempted`
  - **ScoreIR gate status**: `not_attempted`

## Comparison with Previous Summary
- **Previous PDF grouping status**: `private_input_1` achieved `partial_pdf_grouping` with 13 of 14 systems boxed.
- **Current PDF grouping status**: Re-running the smoke workflow confirms that `private_input_1` continues to achieve `partial_pdf_grouping` with 13 of 14 systems successfully constructing bar boxes, but the newly refined bar-box construction diagnostics are now programmatically reported. The unboxed system 6 on page 2 precisely triggers `pdf_partial_grouping_one_system_unboxed`, `pdf_bar_boxes_not_constructible`, and `pdf_barline_too_short` warnings.
- **Previous primary ScoreIR blocker**: Blocked by timing alignment risk.
- **Current primary ScoreIR blocker**: Timing preflight remains blocked by `musicxml_timing_risk` (66 overlapping same-voice events in `private_input_1`), while the PDF layout diagnostics are correctly reporting layout boundaries.

## Current Top Blocker Classification
- **`pdf_bar_box_construction`** (primary PDF grouping blocker for `private_input_1`).
- **`musicxml_timing_repair_not_safe`** (primary timing/ScoreIR blocker for `private_input_1`).
- **`pdf_drawn_system_detection`** / **`pdf_ascii_system_timing_boundary`** (primary PDF grouping blockers for `private_input_2`).

## Next Recommended Task
- **`feature/pdf-bar-box-edge-cases-public-fixtures-v0.7`** (to introduce public synthetic fixtures and heuristics to handle remaining layout blocker edge cases like missing barlines on system 6 and unassigned candidates, moving from `partial_pdf_grouping` to full `pdf_grouped` status).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
