# Handoff

## Metadata
- **Current Branch**: `feature/pdf-fret-optical-bounds-v0.9`
- **Base Branch**: `main`
- **Current PR**: [PR #49](https://github.com/tticom/score2gp/pull/49) (Draft)
- **Latest Local Commit**: `963d274`
- **Latest Pushed Commit**: `963d274`
- **Commit Subject**: Refine fret candidate confidence scoring, character-splitting, and digit-symbol overlap gates v0.9
- **Working Tree Status**: Clean (except modified `HANDOFF.md` once saved, and local untracked venv/test outputs)
- **Tests & Checks Run**:
  - `.venv\Scripts\pytest` -> 290 passed cleanly in 16.01s (including 3 new custom width & ligature overlap tests)
  - `.venv\Scripts\python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `.venv\Scripts\python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under Git
  - `git ls-files grouping-diagnostics.html inspect overlays tuning_outside.tabraw.json warnings.json` -> completely cleaned up / empty
- **GitHub Check Status**: N/A / pending
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Broadened Mixed-Word Technique/Symbol Splitting (`pdf.py`)**:
  - Expanded `tech_chars` in `_split_technique_mixed_words` to support parentheses `()`, brackets `[]`, and punctuation `.,-`.
  - Adjusted the splitting regex to `r"(\d+|[hpsvbr~/\\()\[\].,\-]+)"` to cleanly isolate pure digit parts from adjacent non-playable symbol/punctuation wrappers.
- **Visual Bounds Validation on Split Digits (`pdf.py`)**:
  - Added a validation check in `_split_technique_mixed_words` to detect if a split digit part has a resulting bounding box `width < 4.0 pt`, flagging it with `pdf_fret_digit_symbol_overlap_ambiguous` and `pdf_fret_refinement_not_enough_for_build_ir` to catch highly compressed ligatures.
- **Digit-Symbol Horizontally Close Overlap Detection (`pdf.py`)**:
  - Implemented logic comparing all merged playable fret candidates against non-playable symbol candidates on the same system. If they horizontally overlap (`overlap > 1.5 pt`) and are vertically close (`dy <= 6.0 pt`), it flags them with `pdf_fret_digit_symbol_overlap_ambiguous`.
- **Refined Fret Candidate Confidence Scoring (`pdf.py`)**:
  - Added parameter passing of `width`, `height`, `line_spacing`, and `assignment_warnings` to `_candidate_confidence`.
  - Introduced confidence deductions inside `_candidate_confidence` for extremely small bounds, aspect ratio anomalies, and `pdf_fret_digit_symbol_overlap_ambiguous` warnings.
- **Safety Gate Integration in `build_ir.py`**:
  - Registered `pdf_fret_digit_symbol_overlap_ambiguous` under unsafe grouping warnings whitelists in `build_ir.py` so that the compiler blocks ScoreIR compilation and prevents converting uncertain text into playable notes.
- **Created 2 New Public Synthetic PDF Fixtures (`make_fret_refinement_pdfs.py`)**:
  - `generated_pdf_fret_custom_width_digits.pdf`: Safe narrow/wide fonts, parentheses `(5)`, brackets `[3]`, punctuation `7.`, and clean `h` separation.
  - `generated_pdf_fret_ligature_overlapping_ambiguous.pdf`: Unsafe deep horizontal overlap of `5` and `h` (overlap = 1.5 pt), and extremely squished `"9p"` ligature word at `fontsize=5`.
- **Added 3 New Unit Tests (`test_pdf.py`)**:
  - `test_pdf_fret_custom_width_digits`: Asserts that safe custom-width / parentheses parse successfully and get accepted with confidence >= 0.70.
  - `test_pdf_fret_ligature_overlapping_ambiguous`: Asserts that unsafe visual overlaps/ligatures are rejected and flagged with `pdf_fret_digit_symbol_overlap_ambiguous` (confidence < 0.70).
  - `test_build_ir_refuses_ligature_overlapping_ambiguous`: Asserts that `build_ir` refuses compilation with `BuildIrInputRiskError` on ambiguous overlaps.

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
- **`feature/pdf-timing-refinement-v1.0`**: Design a strategy for refining timing preflight checks, resolving voice durational overlaps, or establishing safe heuristics for aligning vector-layout events.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
