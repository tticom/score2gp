# Handoff

## Metadata

- **Current Branch**: `feature/private-smoke-refresh-after-edge-recovery-v0.1`
- **Base Branch**: `main`
- **Current PR**: TBD
- **Latest Local Commit**: TBD
- **Latest Pushed Commit**: TBD
- **Latest Commit Subject**: TBD
- **Working Tree Status Before Handoff Update**: Modified
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 302 passed.
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` -> empty.

## What Changed

- **Executed E2E Private Smoke Refresh**: Ran `scripts/private_e2e_smoke.py` to evaluate the impact of the conservative edge-boundary recovery on real private fixtures.
- **Analyzed Safe Blockers & Taxonomy Shift**:
  - `private_input_1`: Correctly maintained `"partial_pdf_grouping"` because system 6 on page 2 failed the edge boundary fallback due to vertical staff/barline layout ambiguities. This proves our conservative design: fallback is safely rejected (`pdf_bar_box_edge_boundary_fallback_rejected`) rather than making unverified layout guesses. The primary refusal reason was surfaced as `"musicxml_timing_risk"` due to 66 overfull/overlapping events.
  - `private_input_custom`: Surfaced as `"partial_pdf_grouping"` with `"missing_pdf_grouping"` warning, waiting for matching MusicXML.
  - `private_input_2`: Surfaced as `"missing_pdf_grouping"` with `"pdf-tab-system-not-detected"`, waiting for matching MusicXML.
- **Tasks Checklist**: Marked the task as completed under the `## Done` section in `TASKS.md`.

## Known Limitations

- Conservative edge-boundary fallback is only applied when exactly one accepted barline candidate is present on an edge system.
- Layouts with significant visual ambiguities or overlapping bounding boxes correctly trigger fallback rejection to protect timing integrity.

## Remaining Risks

- Complex multi-system visual overlaps on page 1 of `private_input_1` require vertical layout resolution.

## Next Recommended Task

- Focus on resolving vertical staff system overlapping/ordering ambiguities (`pdf_multi_system_order_ambiguous` / `pdf_system_order_ambiguous`) to safely resolve layout grouping blockers.

## Explicit Scope Boundaries

- Do not implement automatic grouping or bar-box repair of internal measures.
- Do not use MusicXML pitch or tuning data to infer PDF layout.
- Do not alter timing mapping or weaken the final `build-ir` compiler safety gates.
- Do not use, tune to, or track private scores, private overlays, or `work/` artifacts.
- Do not implement OCR, scanned-PDF support, or ML layout recognition.