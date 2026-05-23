# Handoff

## Metadata
- **Current Branch**: `feature/pdf-barline-validation-public-fixtures-v0.5`
- **Base Branch**: `main`
- **Current PR**: [PR #33](https://github.com/tticom/score2gp/pull/33) (Draft)
- **Latest Local Commit**: `9d58edb18e3423b851fd0bf0171e5b7fc266bd90`
- **Latest Pushed Commit**: `9d58edb18e3423b851fd0bf0171e5b7fc266bd90`
- **Commit Subject**: Add PDF barline validation fixtures v0.5
- **Working Tree Status**: Clean (prior to handoff commit)
- **Tests & Checks Run**:
  - `python -m pytest` -> 213 passed cleanly (including 2 new layout/barline validation test suites)
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Added public synthetic PDF fixtures for compact and boundary barline validation scenarios under `tests/fixtures/pdf/`:
  - `generated_pdf_barlines_below_threshold_crossing_staff.pdf` (height < 40pt but crosses all six string lines, accepted).
  - `generated_pdf_barlines_below_threshold_crossing_partial_staff.pdf` (height < 40pt and only partially crosses, rejected).
  - `generated_pdf_barlines_above_threshold_outside_staff_region.pdf` (tall lines outside staff region, rejected).
  - `generated_pdf_barlines_crossing_top_bottom_missing_middle.pdf` (crosses top/bottom strings but missing middle staff lines, rejected).
  - `generated_pdf_barlines_crossing_all_gaps_short_absolute.pdf` (spacing = 6.0pt, height = 30pt crossing all gaps, accepted).
  - `generated_pdf_barlines_crossing_only_some_gaps.pdf` (crosses only 2/3 gaps, rejected).
  - `generated_pdf_compact_barlines_safe_boxes.pdf` (compact system with valid barlines, successfully grouped).
  - `generated_pdf_compact_barlines_candidate_outside.pdf` (valid compact barlines, but fret candidate is outside bars, blocked downstream).
- Refined validation engine and taxonomy in `src/score2gp/pdf.py`:
  - Implemented relative staff crossing logic based on gaps crossed (requires crossing at least `len(ys) - 1` gaps for a safe crossing).
  - Accepted compact but safe barlines down to `20pt` height when they safely cross the entire tab staff region.
  - Strictly rejected lines that do not cross enough string gaps or are outside the staff region.
  - Implemented detailed candidate-level barline validation telemetry: absolute height, staff height, coverage ratio, gaps crossed count, absolute-height decision, relative staff-crossing decision, and final decision.
- Propagated new barline validation blockers to page warnings and BuildIR stages.
- Preserved existing warning code and E2E smoke tests compatibility.
- Added comprehensive unit tests in `tests/test_pdf.py` verifying all 13 boundary scenarios, safety gates, and telemetry outputs.

## Private Smoke Blocker Classification
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Drawn system count**: 14
  - **Barline candidates exist on most systems**: Yes (mostly 2 per system)
  - **Valid barline count**: 0 on most systems
  - **Rejected barline count**: mostly 2 per system
  - **Rejection reason**: `pdf_barline_too_short`
  - **Primary blocker**: `pdf_barline_candidates_invalid`
- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Drawn system count**: 0
  - **ASCII block count**: 3
  - **Primary blockers**: `pdf_drawn_system_detection` and `pdf_ascii_system_timing_boundary`

## Current Top Blocker Classification
- **`pdf_barline_candidates_invalid`** (primary grouping blocker for `private_input_1` - barline candidates exist but are invalid/too short).
- **`pdf_drawn_system_detection`** (primary grouping blocker for `private_input_2` - no drawn tab system detected).
- **`pdf_ascii_system_timing_boundary`** (primary timing/alignment blocker for `private_input_2` - ASCII block timing/barline boundary unavailable).

## Recommended Next Branch
- **`feature/private-smoke-refresh-after-pdf-barline-validation-v0.1`** (to run the private E2E smoke test workflow again and verify if the refined relative crossing rules successfully accept compact barlines on the real inputs).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
