# Handoff

## Metadata

- **Current Branch**: `feature/pdf-system-overlap-public-fixtures-v0.2`
- **Base Branch**: `main`
- **Current PR**: [PR #63](https://github.com/tticom/score2gp/pull/63) (Draft)
- **Latest Local Commit**: `14340cc`
- **Latest Pushed Commit**: `14340cc`
- **Latest Commit Subject**: `feat: implement advanced vertical partitioning heuristics for same-column vertical overlaps and dense adjacent systems`
- **Working Tree Status Before Handoff Update**: Modified `TASKS.md` and `HANDOFF.md` (clean code changes)
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 310 passed (100% success).
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` -> empty.

## What Changed In This Task

- **Created Public Synthetic PDF Overlap Fixtures**:
  - `generated_pdf_system_overlap_same_column.pdf`: Truly interleaved/overlapping vertical ranges (refused).
  - `generated_pdf_system_overlap_ambiguous_bbox.pdf`: Borderline vertical overlap with a playable fret candidate in the gap between staves (refused).
  - `generated_pdf_system_overlap_dense_adjacent.pdf`: Dense adjacent vertical systems with no fret candidates in the gap (resolved/safe).
  - `generated_pdf_system_overlap_safe_counterpart.pdf`: Clean well-spaced vertical systems control (resolved/safe).
  - Created `tests/fixtures/pdf/make_generated_system_overlap_pdfs.py` to compile these fixtures deterministically.
- **Refined PDF Overlap Partitioning Heuristics**:
  - Replaced simple `has_overlap` Y-range overlap with a refined partitioning check in `src/score2gp/pdf.py`.
  - Significant vertical overlaps (> 4.0pt) are immediately refused as ambiguous.
  - Minor overlaps/gaps (< 20.0pt) are only refused if a playable fret candidate falls within the critical gap region between the systems. Otherwise, they are safely ordered and grouped without any blocker warnings!
- **Added Comprehensive Pytest Coverage**:
  - Added `test_pdf_system_overlap_same_column_refused`, `test_pdf_system_overlap_ambiguous_bbox_refused`, `test_pdf_system_overlap_dense_adjacent_safely_ordered`, and `test_pdf_system_overlap_safe_counterpart_safely_ordered` in `tests/test_pdf.py`.
- **Tasks & Handoff Update**:
  - Updated `TASKS.md` Next and Done sections.
  - Fully updated branch metadata, checks, and E2E findings in `HANDOFF.md`.

## Known Limitations

- Visual overlaps with dense interleaved staff lines are truly ambiguous and will continue to be refused.

## Remaining Risks

- Same-column string assignment ambiguities on visually close layouts can block IR generation until coordinate-based string alignment is resolved.

## Next Recommended Task

- **String Assignment Alignment Heuristics**: Address same-column vertical string assignment ambiguities (`pdf_string_assignment_not_enough_for_build_ir` / `pdf_string_assignment_missing`) by implementing robust staff-line proximity calculations.

## Explicit Scope Boundaries

- **No new automatic grouping or bar-box repair** implemented.
- **No altering of edge-boundary fallback or build-ir compiler gates**.
- **No private scores, diagnostic overlays, or raw XML/PDF snippets committed**.
