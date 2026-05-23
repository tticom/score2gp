# Handoff

## Metadata
- **Current Branch**: `feature/pdf-layout-public-fixtures-v0.3`
- **Base Branch**: `main`
- **Current PR**: Draft (to be created)
- **Latest Local Commit**: Pending (after handoff commit)
- **Latest Pushed Commit**: Pending (after feature branch push)
- **Commit Subject**: Add PDF layout blocker fixtures v0.3
- **Working Tree Status**: Clean (once committed)
- **Tests & Checks Run**:
  - `python -m pytest` -> 197 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Refined PDF Blocker Taxonomy**: Integrated complete set of Phase 4/8 warning codes in `pdf.py`, `report.py`, and `build_ir.py` (e.g. `pdf_text_geometry_present_but_no_safe_system`, `pdf_tab_candidates_present_but_system_not_detected`, `pdf_drawn_geometry_present_but_staff_unresolved`, `pdf_tab_staff_lines_fragmented`, `pdf_candidates_unassigned_to_string`, `pdf_candidates_unassigned_to_bar`, `pdf_candidates_unassigned_to_system`, `pdf_system_order_ambiguous`, `pdf_system_bbox_ambiguous`, `pdf_partial_grouping_with_playable_candidates`, `pdf_grouping_confidence_below_threshold`, `pdf_missing_pdf_grouping_blocks_build_ir`, `pdf_layout_detection_requires_manual_review`).
- **Added Public Synthetic PDF Fixtures**: Created seven new born-digital synthetic PDF blocker fixtures under `tests/fixtures/pdf/` mimicking unresolved staff lines, missing systems, fragmented staves, candidates between systems, unassigned string lines, visually close system overlaps, and mixed prose text.
- **Strict build_ir Blocking Gates**: Enforced strict refusal in `build_ir` for any playable fret candidate with unsafe or ambiguous PDF grouping, raising `BuildIrInputRiskError` with detailed failure diagnostics.
- **Improved PDF HTML Grouping Diagnostics**: Enriched `write_grouping_diagnostics_html` to output text/geometry status, candidate/system/staff/bar/string detection stats, block status, warning lists, and clear remediation hints:
  *`PDF layout grouping is unsafe; use a clearer born-digital fixture, improve public layout heuristics, or review manually.`*
- **Regression Tests**: Added comprehensive tests verifying all 14 layout blocker requirements in Phase 8 to `tests/test_pdf.py` (197 tests passing successfully).

## Private Smoke Blocker Classification Used
- **`private_input_1`** (`pdf-tab-musicxml`):
  - text/geometry detected: Yes
  - playable candidates: 203 (non-playable: 126, total: 329)
  - secondary grouping reason: `missing_pdf_grouping`
- **`private_input_2`** (`pdf-tab-only`):
  - text/geometry detected: Yes
  - playable candidates: 54 (non-playable: 17, total: 71)
  - secondary grouping reasons: `missing_pdf_grouping`, `pdf-tab-system-not-detected`

## Known Limitations
- Unsafe PDF grouping still blocks build-ir.
- Text/geometry extraction alone is not enough for ScoreIR.
- No private PDFs are used as fixtures.
- No OCR, scanned-PDF support, ML layout recognition, MusicXML repair, or GPIF expansion.

## Remaining Risks
- Real private scores will continue to trigger blockers until OCR, scanned-PDF, or heuristics calibration are implemented in future milestones.

## Recommended Next Branch / Task
- **Next Task**: Refresh the private smoke workflow after the layout public fixtures v0.3 milestone under a new feature branch `feature/private-smoke-refresh-after-layout-v0.3` to evaluate if real inputs are correctly classified and verified by the new warning codes.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
