# Handoff

## Metadata

- **Current Branch**: `docs/partial-to-recovery-design-note-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #54](https://github.com/tticom/score2gp/pull/54) (Draft)
- **Latest Local Commit**: `10a7092bb469622d1df7b0dfcf7ee7d4dfbf7032`
- **Latest Pushed Commit**: `10a7092bb469622d1df7b0dfcf7ee7d4dfbf7032`
- **Latest Commit Subject**: `docs: add public partial-to-recovery design note`
- **Working Tree Status Before Handoff Update**: Clean
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays tuning_outside.tabraw.json warnings.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 302 passed.
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays tuning_outside.tabraw.json warnings.json` -> empty.

## What Changed

- **Created docs/partial-to-recovery.md**: Formulated a public-safe architectural design document detailing:
  - **Context**: Summarizes the strict rejections (like `pdf_bar_box_one_boundary_rejected` and `pdf_partial_grouping_one_system_unboxed`) at the compiler gates.
  - **Proposed Boundaries**: Outlines mathematically-implied recovery boundaries, specifying constrained edge-boundary fallback tolerances.
  - **Strict Exclusions**: Excludes guess-based internal barlines partitioning and blocks using MusicXML pitch/tuning to infer OMR layout matching.
  - **Public Fixture Strategy**: Requires all future grouping recovery algorithms to be proven via public synthetic born-digital regression tests before any local/private file runs.
- **Documentation References**: Linked the new design note within `README.md` and `docs/workflow.md` to ensure discoverability for developers.
- **Tasks Checklist**: Marked the task as completed under the `## Done` section in `TASKS.md`.

## Known Limitations

- This branch is **documentation-only**. No automatic layout repair or timeline mutation has been implemented.
- Programmatic OMR decisions continue to reside entirely inside JSON TabRaw schemas.

## Remaining Risks

- Any future layout repair must be extremely conservative to avoid introducing timing drift or false-positive measure splits.

## Next Recommended Task

- Add a public partial-to-recovery design note task is completed. The next logical step is to attempt automatic edge-boundary or bar-box recovery following the strict public fixture-driven design note constraints, or to address broader Audiveris MXL/XML imports.

## Explicit Scope Boundaries

- Do not implement automatic grouping or bar-box repair in this branch.
- Do not alter edge-boundary fallback, timing mapping, or `build-ir` compiler gates.
- Do not use, tune to, or track private scores, private overlays, or `work/` artifacts.
- Do not propose OCR, scanned-PDF support, or ML layout recognition.