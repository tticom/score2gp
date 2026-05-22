# Handoff

## Metadata
- **Current Branch**: `feature/pdf-system-layout-diagnostics-v0.1`
- **Base Branch**: `main`
- **Current PR**: [#15](https://github.com/tticom/score2gp/pull/15)
- **Latest Local Commit**: `d16aeddd8d3d3a8267d27d4cbd42ee626aee2421`
- **Latest Pushed Commit**: `d16aeddd8d3d3a8267d27d4cbd42ee626aee2421`
- **Commit Subject**: Improve PDF system layout diagnostics
- **Working Tree Status**: Clean (committed and pushed)
- **Tests & Checks Run**:
  - `python -m pytest` -> 140 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A (local-only prior to push)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Improved PDF grouping and system layout diagnostics based on private-smoke warning classes without tuning to private files or weakening safety gates.
- Refined and added strict warning/reason codes for PDF grouping and system layout anomalies:
  - `pdf_no_systems_detected`, `pdf_partial_system_detection`, `pdf_tab_staff_missing`, `pdf_tab_staff_incomplete`, `pdf_tab_staff_ambiguous`
  - `pdf_barlines_missing`, `pdf_barlines_ambiguous`, `pdf_bar_boxes_missing`
  - `pdf_string_lines_missing`, `pdf_string_assignment_missing`, `pdf_string_assignment_ambiguous`
  - `pdf_candidate_outside_system`, `pdf_candidate_outside_bar`, `pdf_candidate_between_strings`
  - `pdf_multi_system_order_ambiguous`, `pdf_page_layout_unsupported`
  - `pdf_text_candidate_without_geometry`, `pdf_ascii_and_drawn_layout_conflict`, `pdf_grouping_not_safe_for_build_ir`
- Replaced sequential chunk line-grouping logic with a robust, greedy gap-cluster search algorithm that handles vertically interleaved/overlapping tab systems.
- Updated heuristic precedence in `grouping_status_for_tabraw` to ensure that severe drawn-layout anomalies and conflicts are evaluated first.
- Ensured a plain prose/legend page correctly fails with systems-missing warnings even when there are zero playable fret candidates on the page.
- Added 5 new public synthetic PDF fixtures under `tests/fixtures/pdf/` generated via PyMuPDF/fitz:
  - `generated_pdf_candidate_outside_system.pdf`
  - `generated_pdf_candidate_outside_bar.pdf`
  - `generated_pdf_multi_system_order_ambiguous.pdf`
  - `generated_pdf_ascii_and_drawn_layout_conflict.pdf`
  - `generated_pdf_prose_legend_text.pdf`
- Appended 5 dedicated regression tests in `tests/test_pdf.py` confirming that each of these layout warning classes is correctly diagnosed and successfully blocks `build_ir` from compiling ScoreIR.
- Updated documentation (`docs/architecture.md`, `docs/workflow.md`, `docs/limitations.md`, and `TASKS.md`) to integrate and explain the new preflight gates and HTML diagnostics.

## Private Smoke Result Summary (Safe Counts & Statuses Only)
The local diagnostic smoke scan from the previous task remains valid:
1. **`private_input_1`** (`pdf-tab-musicxml`):
   - **Page Count**: 2
   - **Text/Geometry Detected**: Yes (both ASCII tab and drawn tab geometry detected)
   - **Playable Candidate Count**: 203 candidates
   - **Timing Status**: `failed` (ScoreIR gate status: `refused`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: `musicxml_timing_risk`
   - **Secondary Reason Codes**: `MusicXML timing risk prevents ScoreIR output: 63 overfull or overlapping event(s) would violate ScoreIR timing`, `missing_pdf_grouping`, `pdf-tab-system-not-detected`
2. **`private_input_2`** (`pdf-tab-only`):
   - **Page Count**: 1
   - **Text/Geometry Detected**: Yes (both ASCII tab and drawn tab geometry detected)
   - **Playable Candidate Count**: 54 candidates
   - **Timing Status**: `not_attempted` (ScoreIR gate status: `not_attempted`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: None (MusicXML is missing)
   - **Secondary Reason Codes**: `missing_pdf_grouping`, `pdf-tab-system-not-detected`

## Known Limitations
- PDF grouping is strictly conservative and requires born-digital vector tab geometry. No ML layout recognition or OCR is supported.
- Unsafe PDF grouping (partial, missing, ambiguous, or unsupported) strictly blocks `build_ir` and prevents ScoreIR compilation.
- Scanned/raster PDFs remain unsupported.

## Remaining Risks
- None. All 140 tests are fully passing locally. Whitespace checks are perfectly clean, and schemas are identical to the base branch.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken validation/timing gates or tune thresholds to private examples.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
