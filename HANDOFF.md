# Handoff

## Metadata
- **Current Branch**: `feature/pdf-fret-refinement-v0.8`
- **Base Branch**: `main`
- **Current PR**: [PR #48](https://github.com/tticom/score2gp/pull/48) (Draft)
- **Latest Local Commit**: `378f6c2`
- **Latest Pushed Commit**: `378f6c2`
- **Commit Subject**: feat: refine PDF fret digit size gates and horizontal overlap grouping filters v0.8
- **Working Tree Status**: Clean (except modified `HANDOFF.md` once saved, and local untracked venv/test outputs)
- **Tests & Checks Run**:
  - `.venv\Scripts\pytest` -> 287 passed cleanly in 14.54s (including 3 new fret overlap tests)
  - `.venv\Scripts\python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `.venv\Scripts\python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under Git
  - `git ls-files grouping-diagnostics.html inspect overlays tuning_outside.tabraw.json warnings.json` -> completely cleaned up / empty
- **GitHub Check Status**: N/A / pending
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## Cleanup Performed for PR #47 Leftovers
- Verified that PR #47 accidentally tracked several root generated/diagnostic files: `grouping-diagnostics.html`, `inspect/inspect_pdf.json`, `inspect/pages/page-001.png`, `overlays/page-001-grouping.png`, `tuning_outside.tabraw.json`, and `warnings.json`.
- Removed these leftover files completely from Git tracking using `git rm -r` as part of the immediate cleanup prerequisite.
- Committed the cleanup as `c26b270` before proceeding to feature implementation.
- Verified with `git ls-files` that these files are no longer tracked in our branch.

## What Changed in the Task
- **Refined Fret Digit Merging Logic (`pdf.py`)**:
  - Expanded the horizontal adjacent merging gap to support safe touch/overlap down to `-3.0 pt` (when vertically aligned within `2.0 pt`), allowing tight/touching digit spans to merge successfully into multi-digit frets (e.g. `"10"`).
  - Introduced `pdf_fret_digits_overlap_ambiguous` blocker warning code when the horizontal overlap is too deep (`gap < -3.0 pt`) or vertically misaligned with an overlap, marking both digit spans as unsafe to prevent silent corruption.
- **Added Blocker Whitelists (`build_ir.py` & `pdf.py`)**:
  - Registered `pdf_fret_digits_overlap_ambiguous` under `drawn_grouping_codes` in `pdf.py` and mapped it to a descriptive error message in `_WARNING_MESSAGE_MAP`.
  - Whitelisted it in `_tabraw_unsafe_grouping_warning_codes` in `build_ir.py` to ensure `build_ir` cleanly refuses compilation on ambiguous/deep overlaps.
- **Created 2 New Public Synthetic PDF Fixtures (`make_fret_refinement_pdfs.py`)**:
  - `generated_pdf_fret_touching_digits_safe.pdf`: Digits `"1 "` and `"0"` written close together with trailing whitespace (to force separate word tokens during PyMuPDF parsing) resulting in a safe touching overlap (`gap = -2.0 pt`).
  - `generated_pdf_fret_overlapping_digits_ambiguous.pdf`: Digits with too deep of an overlap (`gap = -5.0 pt`).
- **Added 3 New Fret Refinement Unit Tests (`test_pdf.py`)**:
  - `test_pdf_fret_touching_digits_safe`: Asserts that touching digits successfully merge into `"10"`.
  - `test_pdf_fret_overlapping_digits_ambiguous`: Asserts that deep overlaps trigger the `pdf_fret_digits_overlap_ambiguous` blocker warning.
  - `test_build_ir_refuses_overlapping_digits_ambiguous`: Asserts that `build_ir` cleanly raises `BuildIrInputRiskError` and refuses IR compilation on deep overlaps.

## Private Smoke Blocker Summary (No Private Content Included)
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Drawn system count**: 14 (8 on page 1, 6 on page 2)
  - **Constructed bar box count**: 13 constructed.
  - **Unboxed system count**: 1 (system 6 on page 2).
  - **Total candidate count**: 329.
  - **Playable candidate count**: 203.
  - **Non-playable candidate count**: 126.
  - **Candidates assigned to system**: 282.
  - **Candidates assigned to bar**: 265.
  - **Candidates assigned to string**: 141.
  - **Grouping status**: `partial_pdf_grouping`
  - **Primary PDF blocker stage**: `pdf_bar_box_one_boundary_rejected` (system 6 on page 2 has 1 accepted and 1 rejected boundary, blocking fallback and grouping).
  - **Timing blocker stage**: `musicxml_timing_repair_not_safe` (preflight VoiceOverlapError with 66 overfull or overlapping events).
  - **ScoreIR gate status**: `refused` (blocked by PDF grouping and timing).

- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Page count**: 1
  - **ASCII block count**: 1
  - **Total candidate count**: 71.
  - **Playable candidate count**: 54.
  - **Non-playable candidate count**: 17.
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary PDF blocker stage**: `drawn_system_detection` and `ascii_system_detection` (`pdf-tab-system-not-detected`).
  - **Timing status**: `not_attempted`.

## Current Top Blocker Classification
1. **`pdf_bar_box_one_boundary_rejected`** (Primary PDF grouping blocker stage)
2. **`musicxml_timing_repair_not_safe`** (Primary MusicXML timeline voice overlap blocker)

## Next Recommended Task / Branch
- **`feature/pdf-fret-optical-bounds-v0.9`**: Refine fret candidate character-recognition confidence scoring and handle custom fonts or ligature character widths (e.g. numbers overlapping with symbols).

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
