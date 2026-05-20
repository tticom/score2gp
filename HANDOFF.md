# Handoff

## Current Branch

- Branch: `feature/pdf-partial-grouping-diagnostics-v0.1`
- This is a stacked branch based on `feature/scoreir-v0.1-contract`.
- Base PR: PR #1, `feature/scoreir-v0.1-contract -> main`
- Stacked PR: PR #2, `feature/pdf-partial-grouping-diagnostics-v0.1 -> feature/scoreir-v0.1-contract`
- Base branch includes CI workflow fix commit: `e3f3a7a Fix CI test workflow`
- Partial grouping diagnostics are committed on this stacked branch, not uncommitted.

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

Expected current local result before this conflict resolution was:

- `python -m pytest` -> `74 passed`
- schema export -> passed
- validate-ir -> valid
- `git diff --check` -> passed, with CRLF warnings only

## Private Safety

- Do not commit `work/` outputs.
- Do not commit private PDFs, GP files, MXL files, private diagnostic HTML, private overlays, logs, or temporary smoke outputs.
- The only intended tracked private-path item is `fixtures/private/.gitkeep`.

## Known Limits

- No OCR.
- No scanned-PDF support.
- No ML layout recognition.
- No arbitrary commercial score conversion.
- Partial grouping is diagnostic-first and conservative.
- Chord symbols and technique text are preserved but not yet musically attached to ScoreIR events.
- GPIF output remains minimal.

## Next Recommended Task

After both PRs have passing CI and are ready for human review, the next implementation task should be a narrow public-fixture-only symbol attachment branch:
attach chord symbols and technique text from TabRaw to ScoreIR events with conservative geometry and explicit warnings.
