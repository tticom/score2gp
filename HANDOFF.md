# Handoff

## Metadata

- **Current Branch**: `feature/private-smoke-refresh-after-unboxed-recovery-v0.1`
- **Base Branch**: `main`
- **Current PR**: N/A (Draft PR will be created next)
- **Latest Local Commit**: `fe7dffea3b80b7e28dbdf7231498b82c668615b8`
- **Latest Pushed Commit**: `fe7dffea3b80b7e28dbdf7231498b82c668615b8`
- **Latest Commit Subject**: `Merge pull request #61 from tticom/feature/unboxed-system-recovery-v0.1`
- **Working Tree Status Before Handoff Update**: Modified `TASKS.md` and untracked temporary smoke outputs.
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

- **Executed E2E Private-Safe Smoke Refresh**:
  - Run the diagnostic pipeline against local private inputs (`scripts/private_e2e_smoke.py`) with unboxed skips and zero-barline fallback recovery fully integrated.
  - Verified that all inputs complete the diagnostic pass cleanly.
- **Anonymized Blocker & Skip Taxonomy Results**:
  - **`private_input_1`**:
    - **Timing Status**: `passed` (remediation resolved all timing risk).
    - **Unboxed System 6 (Page 2)**: Contained rejected short barlines (`pdf_barline_too_short`) and ambiguous barlines, and was thus successfully **skipped** under `--allow-skip-unboxed-systems`.
    - **Compilation Gate Refused**: Compilation is still refused because of other severe visual layout/grouping ambiguities.
    - **Primary Blocker**: Severe vertical system layout overlap ambiguities on both Page 1 and Page 2: `pdf_multi_system_order_ambiguous`, `pdf_system_order_ambiguous`, `pdf_tab_staff_ambiguous`, `pdf_system_bbox_ambiguous`.
    - **Secondary Blocker**: String assignment ambiguities (`pdf_string_assignment_not_enough_for_build_ir`, `pdf_string_assignment_missing`).
  - **`private_input_custom` & `private_input_2`**:
    - Complete the extract-tab phase cleanly without timing data, waiting for matching MusicXML files (`provide-matching-musicxml-before-build-ir`).
- **Tasks & Handoff Update**:
  - Added smoke refresh task to `TASKS.md` under Done.
  - Fully documented E2E findings and branch metadata in `HANDOFF.md`.

## Known Limitations

- Real private layouts with complex column formatting or visual overlap will require specialized spatial heuristics (like horizontal/vertical column separation) to group safely.

## Remaining Risks

- Overlapping visual staff boundaries on `private_input_1` prevent complete grouping and ScoreIR generation until columns/overlaps are resolved.

## Next Recommended Task

- **Horizontal/Vertical Overlap Heuristics**: Build a feature branch (e.g. `feature/pdf-vertical-overlap-heuristics-v0.1`) to resolve vertical staff system overlap ordering and clustering ambiguities through spatial clustering or column separation.

## Explicit Scope Boundaries

- **No new automatic grouping, bar-box repair, or timing mapping** implemented.
- **No altering of edge-boundary fallback or build-ir compiler gates**.
- **No private scores, diagnostic overlays, or raw XML/PDF snippets committed**.
