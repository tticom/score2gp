# Handoff

## Metadata

- **Current Branch**: `feature/pdf-vertical-system-overlap-resolution-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #57](https://github.com/tticom/score2gp/pull/57) (Draft)
- **Latest Local Commit**: `02dd1751e78cf118da3db712bc8e3932f736253e`
- **Latest Pushed Commit**: `02dd1751e78cf118da3db712bc8e3932f736253e`
- **Latest Commit Subject**: `chore: sync handoff SHA in HANDOFF.md`
- **Working Tree Status Before Handoff Update**: Clean
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 303 passed.
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` -> empty.

## What Changed

- **Implemented Column-Aware Sorting Heuristics**: Added a robust column-aware system ordering algorithm in `_tab_line_groups` in `src/score2gp/pdf.py`. It partitions horizontal staff lines into vertical columns, sorts columns left-to-right, and sorts systems within each column top-to-bottom.
- **Refined Vertical Overlap Check**: Refined the vertical overlap warning check in `pdf.py` to require horizontal overlap too. This prevents vertical overlap warnings on clean multi-column layouts where X ranges are disjoint.
- **Created Public Synthetic Fixtures**: Added a generator script `tests/fixtures/pdf/make_generated_vertical_overlap_tab_pdf.py` and generated PDF `tests/fixtures/pdf/generated_pdf_vertical_overlap_resolved.pdf` representing a two-column staff layout with vertically overlapping Y-ranges but disjoint X-ranges.
- **Comprehensive Unit Testing**: Added `test_refined_vertical_overlap_resolved_diagnostics` in `tests/test_pdf.py` to assert that layout ambiguity warnings are completely absent, and verify the correct column-aware system and bar numbering order.
- **Executed Private Smoke Refresh**: Ran `scripts/private_e2e_smoke.py` to evaluate the impact on real private inputs (results were clean and verified).
- **Tasks Checklist**: Marked the task as completed under the `## Done` section in `TASKS.md`.

## Known Limitations

- Overlapping staves that reside within the same column and horizontally overlap will correctly trigger vertical overlap warnings to protect timing integrity.

## Remaining Risks

- Complex multi-system visual overlaps on page 1 of `private_input_1` require vertical layout resolution.

## Next Recommended Task

- Run a private-safe smoke refresh after this recovery merges to verify whether unboxed edge systems (like system 6 of private_input_1) are successfully recovered under this conservative edge-boundary policy.

## Explicit Scope Boundaries

- Do not implement automatic grouping or bar-box repair of internal measures.
- Do not use MusicXML pitch or tuning data to infer PDF layout.
- Do not alter timing mapping or weaken the final `build-ir` compiler safety gates.
- Do not use, tune to, or track private scores, private overlays, or `work/` artifacts.
- Do not implement OCR, scanned-PDF support, or ML layout recognition.