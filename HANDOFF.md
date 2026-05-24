# Handoff

## Metadata

- **Current Branch**: `docs/unboxed-system-recovery-design-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #60](https://github.com/tticom/score2gp/pull/60) (Draft)
- **Latest Local Commit**: `9e5276dc5df2937f9863b3b913dddc61967c57aa`
- **Latest Pushed Commit**: `9e5276dc5df2937f9863b3b913dddc61967c57aa`
- **Latest Commit Subject**: `docs: add unboxed system recovery design note v0.1`
- **Working Tree Status Before Handoff Update**: Clean
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 304 passed.
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` -> empty.

## What Changed In This Task

- **Executed E2E Private Smoke Review**:
  - Executed `scripts/private_e2e_smoke.py` local runner to evaluate layout blocker taxonomy under `allow_remediation=True`.
  - Confirmed `private_input_1`'s timing risk is resolved (0 timing issues in `build_error.json`).
  - Extracted the exact layout warning codes currently blocking the unboxed Page 2 System 6: `pdf_barlines_not_detected_in_system`, `pdf_bar_boxes_not_constructible`, `pdf_bar_detection_not_enough_for_build_ir`, `pdf_candidate_unassigned_due_to_unboxed_system`, and `pdf_partial_grouping_one_system_unboxed`.
- **Created Public Design Note (`docs/unboxed-system-recovery.md`)**:
  - Detailed the unboxed system scenario and its layout warning codes.
  - Proposed a mathematically bounded **Single-Measure System-Wide Recovery (Zero-Barline Fallback)** that constructs a system-wide bar box when exactly zero barlines are detected in the system staff bounding box.
  - Proposed an **Opt-In System-Skipping Compiler Progression** (`--allow-skip-unboxed-systems` / `allow_skip_unboxed: bool`) that skips unboxed systems and compiles only the remaining safe boxed measures on the page.
  - Mandated a public fixture-first testing strategy (synthetic born-digital PDF fixtures).
  - Outlined strict exclusions (no MusicXML duration slicing, no guessing internal barlines).
- **Linked Design Note**:
  - Updated `README.md` to link to the new design note.
- **Updated Tasks**:
  - Marked the design note task as completed in `TASKS.md`.

## Known Limitations

- Layout geometry parsing remains strictly conservative. Skips or system-wide fallbacks will be strictly opt-in parameters.

## Remaining Risks

- **Unboxed Page 2 System 6**: Until the recovery or skipping design is implemented in a future branch, the system remains unboxed and prevents final compilation under standard gates.

## Next Recommended Task

- **Implement Unboxed System Recovery & Skipper**: Create a feature branch (e.g. `feature/unboxed-system-recovery-v0.1`) to implement the Single-Measure System-Wide Recovery (Zero-Barline Fallback) and the Opt-In System-Skipping Compiler Progression, verified completely with public synthetic born-digital PDF fixtures.

## Explicit Scope Boundaries

- **Documentation and review only**. Do not implement any automatic grouping or bar-box repair in this branch.
- Do not use MusicXML pitch or tuning data to infer PDF layout.
- Do not alter edge-boundary fallback, timing mapping, or `build-ir` compiler gates.
- Do not guess or infer missing internal (inter-measure) barlines.
- Do not use, tune to, or track private scores, private overlays, or `work/` artifacts.
- Do not implement OCR, scanned-PDF support, or ML layout recognition.
