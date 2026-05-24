# Handoff

## Metadata

- **Current Branch**: `feature/pdf-string-assignment-heuristics-v0.1`
- **Base Branch**: `main`
- **Current PR**: N/A (Will be created next using `gh pr create --draft --fill`)
- **Latest Local Commit**: `a5400f8`
- **Latest Pushed Commit**: `a5400f8`
- **Latest Commit Subject**: `feat: implement robust vertical string proximity heuristics and systematic offset calibration`
- **Working Tree Status Before Handoff Update**: Modified `HANDOFF.md` (clean code changes committed and pushed)
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 312 passed (100% success).
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` -> empty.

## What Changed In This Task

- **Created Public Synthetic PDF String Assignment Fixtures**:
  - `generated_pdf_dense_string_assignment_safe.pdf`: Dense string spacing (14.0pt line spacing) and all fret candidates systematically shifted vertically by +4.0pt (resolved/safe).
  - `generated_pdf_dense_string_assignment_ambiguous.pdf`: Borderline vertical string placement with a fret candidate exactly equidistant (+7.0pt midpoint shift) between two strings (refused).
  - Created `tests/fixtures/pdf/make_dense_string_assignment_pdfs.py` to compile these fixtures deterministically.
- **Implemented Robust String Proximity & Systematic Offset Heuristics**:
  - Added systematic vertical offset calibration per system in `src/score2gp/pdf.py`. We calculate the median vertical offset among all well-aligned fret candidates (within `0.36 * line_spacing` of any staff line) and apply this calibration offset to adjust all candidates' Y coordinates before evaluating string proximity.
  - Refined the string vertical distance assignment threshold in `string_for_y` to `tolerance = max(4.5, self.line_spacing * 0.42)`.
  - Playable fret candidates in tight layouts are successfully calibrated and mapped to their correct string lines, clearing `pdf_string_assignment_missing` and `ambiguous` blockers.
- **Added Comprehensive Pytest Coverage**:
  - Added `test_pdf_dense_string_assignment_safe` and `test_pdf_dense_string_assignment_ambiguous` in `tests/test_pdf.py` to assert the successful calibration of systematic shifts and the safe rejection of truly equidistant midpoints.
- **Tasks & Handoff Update**:
  - Updated `TASKS.md` Next and Done sections.
  - Fully updated branch metadata, checks, and E2E findings in `HANDOFF.md`.

## Known Limitations

- Genuinely equidistant candidate placements (exactly at the midpoint between two strings) are mathematically unsafe and will continue to be refused.

## Remaining Risks

- Real private layouts could contain multiple distinct shift directions across columns or custom spacing; however, our system-wide median offset calibration is highly robust.

## Next Recommended Task

- **Private-Safe Smoke Refresh**: Execute a private-safe E2E smoke review using `scripts/private_e2e_smoke.py` to evaluate the combined impact of vertical overlap resolution and robust string proximity calibration on real private inputs (e.g. `private_input_1`).

## Explicit Scope Boundaries

- **No new automatic grouping or bar-box repair** implemented.
- **No altering of edge-boundary fallback or build-ir compiler gates**.
- **No private scores, diagnostic overlays, or raw XML/PDF snippets committed**.
