# Handoff

## Metadata

- **Current Branch**: `feature/private-smoke-refresh-after-vertical-overlap-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #58](https://github.com/tticom/score2gp/pull/58) (Draft)
- **Latest Local Commit**: `83a71ebcdcc0877e777b244039352f711deee5eb`
- **Latest Pushed Commit**: `83a71ebcdcc0877e777b244039352f711deee5eb`
- **Latest Commit Subject**: `chore: private smoke refresh after vertical overlap resolution v0.1`
- **Working Tree Status Before Handoff Update**: Clean
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 303 passed.
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` -> empty.

## What Changed In This Task

- **Executed Private Smoke Refresh**: Ran `scripts/private_e2e_smoke.py` to evaluate the impact of the newly merged column-aware vertical overlap resolution (PR #57) on real private score inputs (specifically, `private_input_1` page 1).
- **Anonymized Findings of the Smoke Refresh**:
  - **`private_input_1`**:
    - **Page 1 Overlaps**: 8 systems on page 1 were successfully grouped into bar boxes (`pdf_bar_boxes_constructed` successfully in systems 1-8). However, because these systems reside in a single column and overlap both horizontally and vertically, page-level overlap warnings `pdf_multi_system_order_ambiguous` (along with `pdf_system_order_ambiguous`, `pdf_tab_staff_ambiguous`, `pdf_system_bbox_ambiguous`) are still triggered.
    - **Page 2 Boundaries**: Systems 1-5 were successfully grouped into bar boxes. System 6 remains unboxed due to missing/ambiguous bar boundaries (`pdf_barlines_not_detected_in_system`, `pdf_bar_boxes_not_constructible`, etc.), triggering `pdf_partial_grouping_one_system_unboxed`.
    - **Primary Blocker**: The score remains blocked from writing ScoreIR by `"musicxml_timing_risk"` due to 66 overfull or overlapping events in the matching MusicXML.
  - **`private_input_custom`**:
    - Remains in `"partial_pdf_grouping"` (secondary code `missing_pdf_grouping`) and is blocked by `"provide-matching-musicxml-before-build-ir"` (no matching MusicXML).
  - **`private_input_2`**:
    - Remains in `"missing_pdf_grouping"` (secondary codes `missing_pdf_grouping`, `pdf-tab-system-not-detected`) and is blocked by `"provide-matching-musicxml-before-build-ir"` (no matching MusicXML).

## Known Limitations

- Overlapping staves that reside within the same column and horizontally overlap will correctly trigger vertical overlap warnings to protect timing integrity.

## Remaining Risks

- **MusicXML Timing Risk**: 66 overfull or overlapping events in `private_input_1` prevent ScoreIR output under the conservative preflight safety gate.
- **Unboxed Systems**: Page 2 System 6 in `private_input_1` lacks bar boxes due to missing barline geometry.

## Next Recommended Task

- **Remediate MusicXML Timing Risk**: Implement conservative timeline resolution or tolerance heuristics in `build_ir` to handle overfull or overlapping events safely, or refine the preflight gate to allow compilation where safe (next feature branch: `feature/musicxml-timing-risk-remediation-v0.1`).

## Explicit Scope Boundaries

- Do not implement automatic grouping or bar-box repair of internal measures.
- Do not use MusicXML pitch or tuning data to infer PDF layout.
- Do not alter timing mapping or weaken the final `build-ir` compiler safety gates.
- Do not use, tune to, or track private scores, private overlays, or `work/` artifacts.
- Do not implement OCR, scanned-PDF support, or ML layout recognition.