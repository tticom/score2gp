# Handoff

## Metadata

- **Current Branch**: `feature/unboxed-system-recovery-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #61](https://github.com/tticom/score2gp/pull/61) (Draft)
- **Latest Local Commit**: `c05f25d304a0ccfc3aee5be92cd712c98d63a8a3`
- **Latest Pushed Commit**: `c05f25d304a0ccfc3aee5be92cd712c98d63a8a3`
- **Latest Commit Subject**: `feat: implement unboxed system recovery and skipping v0.1`
- **Working Tree Status Before Handoff Update**: Modified `HANDOFF.md` only (clean workspace)
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 306 passed (100% success).
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` -> empty.

## What Changed In This Task

- **Implemented Single-Measure System-Wide Recovery (Zero-Barline Fallback)**:
  - Updated Pydantic candidate preprocessing logic inside `build_ir.py`.
  - When `allow_skip_unboxed=True` is enabled, clean unboxed systems (exactly 0 detected barlines and 0 rejected barlines) are recovered into a single system-wide measure by mapping candidate `bar_index` to 1.
  - Clears all corresponding missing bar grouping warnings and appends telemetry info warnings: `pdf_system_recovered_as_single_measure` and `pdf_bar_box_system_wide_fallback`.
- **Implemented Opt-In System-Skipping Compiler Progression**:
  - When `allow_skip_unboxed=True` is enabled, unboxed systems containing rejected barlines (warnings starting with `pdf_barline_`) are cleanly skipped.
  - Skips candidate assignment for these systems and filters out all corresponding warnings while logging `pdf_unboxed_system_skipped`.
- **Structured Warning Diagnostics**:
  - Added `page_index` and `system_index` keys to unboxed warnings (`pdf_barlines_not_detected_in_system`, `pdf_bar_boxes_not_constructible`, and `pdf_bar_detection_not_enough_for_build_ir`) inside `pdf.py` for structured parsability.
- **Added Public Synthetic Fixtures & Pytest Verification**:
  - Created public synthetic unboxed staff tab PDF (`generated_unboxed_system_tab.pdf`) and its generator script.
  - Wrote comprehensive coverage in `tests/test_pdf.py` (`test_synthetic_unboxed_system_recovery` and `test_synthetic_unboxed_system_skipper`) asserting that both fallbacks function exactly as designed.
- **Enabled Skipper in CLI and Local Smoke Pass**:
  - Wired `--allow-skip-unboxed-systems` to the CLI and enabled it in `scripts/private_e2e_smoke.py`.
  - Executed private-safe smoke refresh showing correct execution and private-safe summary metrics.

## Known Limitations

- Layout geometry parsing remains strictly conservative. Recovery and skips are strictly opt-in parameters.

## Remaining Risks

- Ambiguous visual layout blockers (e.g. overlapping visual staff systems, compact spacing, fragmented staffs) will still block compiler progression, which is correct and maintains strict safety gates.

## Next Recommended Task

- Run a full private-safe E2E smoke review following the PR merge to evaluate and classify the remaining visual/timing blockers across other private inputs.

## Explicit Scope Boundaries

- **No MusicXML Timing Slicing**: Slicing PDF geometry using MusicXML structure is forbidden to preserve spatial layout independence.
- **No Guessing Missing Internal Barlines**: Spatially partitioning system gaps is forbidden.
- **No loosening of default compiler safety gates**: Skipping/recovery are strictly opt-in.
- **No ML or OCR layout recognition** used.
- **No private musical scores or overlays committed**.
