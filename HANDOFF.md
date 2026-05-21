# Handoff

## Current Branch

- Branch: `feature/pdf-partial-grouping-diagnostics-main-v0.1`
- Base: `main`
- PR #1 has been merged into `main`.
- This branch re-applies the partial PDF grouping diagnostics work that was previously in closed PR #2.
- Partial grouping diagnostics are committed on this branch.

## Current Capability

- Public PDF grouping v0.1 remains public-fixture-only and born-digital/generated-fixture focused.
- Fully grouped public fixtures can infer systems, tab staff lines, bar boxes, string assignments, and bar assignments.
- Partial grouping fixtures cover missing barlines, incomplete tab staff geometry, ambiguous string assignment, and ambiguous bar assignment.
- Ungrouped and partially grouped playable PDF-derived fret candidates are blocked before ScoreIR output.
- `build-ir` remains conservative and must not write ScoreIR from unsafe grouping.

## Verification Expected

Run before pushing or review:

- `python -m pytest`
- `python -m score2gp.cli export-schema --out schemas`
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json`
- `git diff --check`

## Private Safety

- Do not commit `work/` outputs.
- Do not commit private PDFs, GP files, MXL files, private diagnostic HTML, private overlays, logs, or temporary smoke outputs.
- The only intended tracked private-path item is `fixtures/private/.gitkeep`.

## Known Limitations

- No OCR.
- No scanned-PDF support.
- No ML layout recognition.
- No arbitrary commercial score conversion.
- Partial grouping remains diagnostic-first and conservative.
- `build-ir` blocks partial playable grouping rather than guessing.

## Next Recommended Task

After this branch has passing CI and is ready for human review, the next implementation task should be a narrow public-fixture-only symbol attachment branch:
attach chord symbols and technique text from TabRaw to ScoreIR events with conservative geometry and explicit warnings.
