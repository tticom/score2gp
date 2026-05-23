# Handoff

## Metadata
- **Current Branch**: `feature/private-smoke-refresh-after-pdf-bar-detection-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft (to be created)
- **Latest Local Commit**: (to be committed)
- **Latest Pushed Commit**: (to be pushed)
- **Commit Subject**: Refresh private smoke after PDF bar diagnostics
- **Working Tree Status**: Modified
- **Tests & Checks Run**:
  - `python -m pytest` -> 211 passed cleanly
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Re-ran the local private-safe end-to-end diagnostic smoke test workflow against real private inputs after merging the PDF bar detection fixtures v0.4.
- Evaluated and recorded the detailed barline candidate, accepted, and rejected counts directly from real private inputs without copying private data or loosen grouping gates.
- Verified that the new pipeline diagnostics correctly extract and propagate system-level vertical candidate metrics (`barline_candidates_count`, `valid_barline_count`, `rejected_barline_count`, and `rejection_reasons`).

## Private Smoke Blocker Classification
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **Drawn system count**: 14 (7 per page)
  - **Barline candidates per system**: 2 candidates detected on most systems, but they are all rejected.
  - **Valid barline count per system**: 0 (on most systems) or 1 (on system 1).
  - **Rejected barline count per system**: 2 (on most systems) or 1 (on system 1).
  - **Barline rejection reason**: `pdf_barline_too_short` (vertical line height is below the 40pt threshold).
  - **Bar box count**: 0
  - **Playable fret candidates**: 203 (non-playable: 126, total: 329)
  - **Candidates assigned to system**: 282 (fret: 162, chord/text: 120)
  - **Candidates assigned to bar**: 0 (due to 0 bar boxes constructed)
  - **Candidates assigned to string**: 141 (fret candidates)
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary blocker stage**: `bar_detection` (sub-stage `pdf_barline_candidates_invalid` - barlines are present but rejected as too short).
  - **Primary PDF reason code**: `pdf_system_detected_bar_detection_missing`
  - **Secondary PDF reason codes**: `pdf_barline_candidates_present_but_invalid`, `pdf_bar_boxes_not_constructible`, `pdf_bar_detection_not_enough_for_build_ir`, `pdf_barline_too_short`, `missing_pdf_barlines`, `pdf_bar_boxes_missing`, `pdf_barlines_missing`
  - **Timing status**: `failed` (MusicXML timing risk prevents ScoreIR output: 69 timing issues, including 63 overfull bars, 1 underfull bar, 2 tie continuity risks, 2 many timing risks, 66 affected events; calibration feasibility `false`)
  - **ScoreIR gate status**: `refused`
  - **GP writing status**: `not_attempted`
- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Page count**: 1
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **Drawn system count**: 0
  - **ASCII block count**: 3
  - **Playable fret candidates**: 54 (non-playable: 17, total: 71)
  - **Candidates assigned to system**: 54
  - **Candidates assigned to bar**: 0 (due to missing ASCII timing boundary)
  - **Candidates assigned to string**: 54
  - **Bar box count**: 0
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary PDF blocker stage**: `system_detection` (drawn) and `ascii_system_detection` (ASCIItiming boundary unavailable).
  - **Primary PDF reason code**: `pdf-tab-system-not-detected`
  - **Secondary PDF reason codes**: `pdf_drawn_system_not_detected`, `pdf_ascii_system_detected`, `pdf_ascii_system_measure_boundaries_missing`, `pdf_ascii_system_timing_unavailable`, `pdf_text_geometry_present_but_no_safe_system`, `pdf_drawn_geometry_present_but_staff_unresolved`, `pdf_tab_staff_lines_fragmented`
  - **Timing status**: `not_attempted`
  - **ScoreIR gate status**: `not_attempted`

## Comparison with Previous Summary
- **Previous Bar-detection Status**: `private_input_1` reported 14 systems and 0 bar boxes under `pdf_system_detected_bar_detection_missing`, but could not expose why vertical barlines were missing or rejected.
- **Current Bar-detection Status**: With the v0.4 telemetry, `private_input_1` successfully reports detailed vertical line candidate counts (mostly 2 per system) and captures the exact reason they are invalid: they are rejected as `pdf_barline_too_short` because their height falls below the 40pt limit.

## Current Top Blocker Classification
- **`pdf_barline_candidates_invalid`** (primary grouping blocker for `private_input_1` - barline candidates exist but are invalid/too short).
- **`pdf_drawn_system_detection`** (primary grouping blocker for `private_input_2` - no drawn tab system detected).
- **`pdf_ascii_system_timing_boundary`** (primary timing/alignment blocker for `private_input_2` - ASCII block timing/barline boundary unavailable).

## Recommended Next Branch
- **`feature/pdf-barline-validation-public-fixtures-v0.5`** (to introduce public synthetic PDF fixtures for line/barline validation limits, and refine the vertical crossing and height heuristic thresholds so that valid barlines on real inputs are safely accepted).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
