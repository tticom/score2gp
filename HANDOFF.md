# Handoff

## Metadata

- **Current Branch**: `feature/pdf-timing-refinement-v1.0`
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
- **Current PR**: [PR #50](https://github.com/tticom/score2gp/pull/50) (Draft)
- **Latest PR #49 Merge Commit on Main**: `edb80eacf78a282073afed135f91fa20627be29a`
- **Latest Implementation Commit**: `8224fdf Add PDF timing refinement diagnostics v1.0`
- **Latest Handoff Commit**: this file is the final handoff update for the branch; use `git log -1` for the exact post-commit hash.
- **Working Tree Status Before Handoff Update**: Clean after implementation commit and push.
- **GitHub Check Status at PR Creation**: Pending (`test` jobs started for PR #50).
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, private summaries, overlays, logs, diagnostic outputs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays tuning_outside.tabraw.json warnings.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 301 passed.
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays tuning_outside.tabraw.json warnings.json` -> empty.

## What Changed

- Added `pdf-timing-refinement.v1.0` diagnostics metadata.
- Added public-safe MusicXML timing refinement classification:
  - `invalid_timing_refused`
  - `unsupported_polyphony_refused`
  - `mixed_invalid_timing_and_unsupported_polyphony_refused`
  - `timing_warning_or_info_only`
  - `timing_safe`
- Added private-safe timing summary counts for issue codes, severities, affected measures, affected voices, affected events, primary reasons, and secondary reasons.
- Added vector x-to-onset refinement classifications:
  - `safe`
  - `partial`
  - `ambiguous`
  - `incompatible`
  - `unavailable`
  - `refused`
- Updated `pdf-timing-mapping-diagnostics.html` to show timing refinement version, classification, reason codes, and the mapping sidecar's per-bar evidence.
- Added public synthetic tests proving:
  - valid chord stacks are not same-voice overlap;
  - same-voice overlap remains refused;
  - rest/note overlap remains refused;
  - overfull MusicXML remains refused;
  - valid multi-voice/polyphony is refused as unsupported, not invalid timing;
  - safe, partial, ambiguous, and incompatible vector layout evidence are classified clearly.
- Added `docs/timing-refinement-v1.0.md` design note and updated architecture, workflow, limitations, tasks, and plan docs.

## Known Limitations

- No automatic MusicXML timing repair.
- No silent MusicXML timeline mutation to make invalid inputs pass.
- No OCR, scanned-PDF support, ML layout recognition, or broad score conversion.
- No MusicXML pitch/tuning inference to bypass PDF geometry gates.
- No inference of missing durations, events, strings, or frets.
- Vector x-to-onset evidence remains diagnostic and cannot repair unsafe PDF grouping or unsafe MusicXML timing.
- Non-monotonic vector layout timing evidence remains refused.

## Remaining Risks

- The v1.0 taxonomy is intentionally conservative and may need additional public fixtures as new OMR timing patterns are observed.
- The HTML report is explanatory only; JSON remains the programmatic source of truth.
- Valid but unsupported polyphony is still blocked until ScoreIR/build-ir explicitly model a safe polyphonic path.
- Warning-quality x-to-onset evidence can still accompany successful controlled public builds; developers must inspect the diagnostics before trusting broader inputs.

## Next Recommended Task

After PR #50 has passing CI and is reviewed, run a private-safe smoke refresh using ignored `work/` outputs to compare the new timing-refinement counts and categories against real diagnostic inputs. Report only counts, statuses, warning categories, and artifact paths.

## Explicit Scope Boundaries

- Do not tune to private examples.
- Do not commit private files or `work/` outputs.
- Do not weaken timing/grouping/string/fret/build-ir gates.
- Do not implement automatic MusicXML timing repair without a future explicit, public-fixture-proven gate.
- Do not infer strings or frets from MusicXML pitch/tuning.
- Do not use tuning evidence to bypass geometry gates.
- Do not implement OCR, scanned-PDF support, ML layout recognition, GPIF expansion, or broad score conversion in this branch.
