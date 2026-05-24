# Handoff

## Metadata

- **Current Branch**: `feature/pdf-horizontal-staff-partition-v0.1`
- **Base Branch**: `main`
- **Current PR**: N/A (Will be created next using `gh pr create --draft --fill`)
- **Latest Local Commit**: `c3b5dba`
- **Latest Pushed Commit**: N/A (Will push current branch next)
- **Latest Commit Subject**: `Implement horizontal staff partitioning heuristics to safely resolve multi-column layouts`
- **Working Tree Status Before Handoff Update**: Clean implementation and tests committed. Update of `TASKS.md` and `HANDOFF.md` in progress.
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 313 passed (100% success).
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` -> empty.

## What Changed In This Task

- **Updated AGENTS.md Ground Rules**:
  - Enforced a strict ground rule stating that code and tests must be written before any PR is raised (no markdown-only or tests-only PRs).
- **Horizontal Line Deduplication**:
  - Implemented horizontal drawing line segment deduplication in `_detect_tab_systems` inside `src/score2gp/pdf.py` to merge duplicate/overlapping lines. This completely prevents ghost/duplicate staves from causing false-positive vertical overlap blocks.
- **Refined Column Overlap Ratio Check**:
  - Increased the horizontal overlap threshold ratio from `0.45` to `0.75` in `src/score2gp/pdf.py` to ensure that vertical overlap checks are decoupled between independent columns.
- **Restricted Horizontal Barline Search Range**:
  - Reduced the horizontal candidate search margin for barlines from `50.0` to `25.0` in `src/score2gp/pdf.py`. This prevents cross-column barline collection, eliminating false-positive `pdf_barline_outside_system_bounds` warnings on neighboring columns.
- **Created Multi-Column Layout Synthetic PDF Fixture**:
  - Wrote a python script `tests/fixtures/pdf/make_multi_column_layout_pdf.py` and compiled a public born-digital PDF fixture `generated_pdf_multi_column_layout.pdf` simulating a multi-column guitar score page where left and right systems overlap vertically.
- **Appended Pytest Test Coverage**:
  - Added the `test_pdf_multi_column_layout_safe` unit test case in `tests/test_pdf.py` proving that clean multi-column layouts parse cleanly without any vertical overlap blockers and compile successfully to ScoreIR.
- **E2E Private Smoke Test Verification**:
  - Ran `scripts/private_e2e_smoke.py` showing that Page 1 vertical system overlap ambiguity blockers (`pdf_multi_system_order_ambiguous`, `pdf_system_order_ambiguous`, `pdf_tab_staff_ambiguous`, `pdf_system_bbox_ambiguous`) have been completely and cleanly cleared on real private inputs (Page 1 grouping successfully resolved!).

## Known Limitations

- Real private scores may still contain local timing-alignment risks or partial grouping warnings on other pages (e.g. Page 2 system 6 has short barlines).

## Remaining Risks

- Complex multi-system pages with severe vertical overlapping text outside of staff bounds may require further refinement if they span both column ranges.

## Next Recommended Task

- **MusicXML Timing and Alignment Review**: Evaluate and address remaining timing-alignment blockers on Page 2 of real private scores, or merge the current branch first.

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No altering of the build-ir compiler gates or the edge-boundary fallback**.
