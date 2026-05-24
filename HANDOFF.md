# Handoff

## Metadata
- **Current Branch**: `feature/ascii-scoreir-gate-refusal-diagnostics-v0.1`
- **Base Branch**: `main`
- **Current PR**: #8 (URL: https://github.com/tticom/score2gp/pull/8)
- **Latest Local Commit**: `aa9c43919f7e209eeaa7ede1536f605f4f6fa23b`
- **Latest Pushed Commit**: `aa9c43919f7e209eeaa7ede1536f605f4f6fa23b`
- **Commit Subject**: `Document routine command permissions`
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 114 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed
  - `git diff -- schemas` -> empty
- **GitHub Check Status**: Passing (All remote checks passed on PR #8 for commit `027db3e`)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL files, overlays, logs, or diagnostic outputs are tracked or staged.

## What Changed in the Task
- Added a stronger persistent project rule, planning/execution rule, and allowed routine commands in `AGENTS.md` to ensure `HANDOFF.md` is updated, committed, and pushed to the remote feature branch at the end of every task.
- Updated `HANDOFF.md` to align with the latest pushed commit status, ready-for-review status, passing remote check results, and documented routine command permissions.

## Known Limitations
- Refusal diagnostics are JSON-focused. Developer-facing HTML rendering for ASCII gate failures is a follow-up branch.
- No OCR, scanned-PDF support, or ML layout recognition.
- No arbitrary commercial score conversion.
- No symbol or technique attachment to ScoreIR events yet.
- GPIF output remains minimal.

## Remaining Risks
- None on this branch. Refusal is the deterministic and expected behavior for unsupported ASCII inputs.

## Explicit Scope Boundaries
- **Do not** start HTML rendering on this branch.
- **Do not** start symbol/technique attachment.
- **Do not** broaden ASCII-to-ScoreIR conversion.
- **Do not** use private PDFs as regression fixtures.
- **Do not** commit `work/` outputs or private files.

## Next Recommended Task
- Add developer-facing HTML rendering for ASCII ScoreIR gate refusal diagnostics in a new branch after PR #8 is merged.
