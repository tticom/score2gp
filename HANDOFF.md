# Handoff

## Metadata
- **Current Branch**: `feature/musicxml-invalid-timing-public-fixtures-v0.5`
- **Base Branch**: `main`
- **Current PR**: [#25](https://github.com/tticom/score2gp/pull/25) (Draft)
- **Latest Local Commit**: `245975ef172839c219e2faf474d3e2001941d849`
- **Latest Pushed Commit**: `245975ef172839c219e2faf474d3e2001941d849`
- **Commit Subject**: Add MusicXML calibration boundary fixtures and diagnostics
- **Working Tree Status**: Clean
- **Tests & Checks Run**:
  - `python -m pytest` -> 190 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Public Synthetic MusicXML Fixtures**: Added 10 public synthetic MusicXML timing fixtures under `tests/fixtures/musicxml/` to model diverse timing calibration boundary scenarios cleanly without relying on private materials:
  1. `timing_vc_drift_candidate.musicxml`: Small ordered timing drift (1 tick overfull), classified as candidate (`musicxml_timing_calibration_candidate`).
  2. `timing_vc_large_overfull.musicxml`: Large overfull measure, classified as not safe (`musicxml_overfull_too_large_for_calibration`).
  3. `timing_vc_overlap_blocks.musicxml`: Same-voice timing overlaps, blocking calibration (`musicxml_overlap_blocks_calibration`).
  4. `timing_vc_tie_continuity_blocks.musicxml`: Unresolved start tie plus timing overflow, blocking calibration (`musicxml_tie_continuity_blocks_calibration`).
  5. `timing_vc_many_risks_blocks.musicxml`: High backup/forward cursor movements, blocking calibration (`musicxml_many_risks_block_calibration`).
  6. `timing_vc_mixed_blocks.musicxml`: Mixed underfull and overfull measures, blocking global calibration (`musicxml_mixed_underfull_overfull_blocks_calibration`).
  7. `timing_vc_invalid_grid_blocks.musicxml`: Expected duration divisions do not partition cleanly, blocking calibration (`musicxml_invalid_grid_blocks_calibration`).
  8. `timing_vc_multi_affected_ordered.musicxml`: Multiple affected note events but still ordered and small overfull, candidate for future calibration.
  9. `timing_vc_unrecoverable_summary.musicxml`: Unrecoverable timing approximating the private smoke blocker shape (large overfull in one measure, overlap in another).
  10. `timing_vc_valid_counterpart.musicxml`: Clean valid counterpart measure passing without timing preflight warning/error.
- **Diagnostics Refinements**: Refined preflight checks in `src/score2gp/musicxml.py` and `src/score2gp/build_ir.py` to extract root telemetry fields:
  - `calibration_possible`
  - `calibration_candidate_reason`
  - `calibration_blocking_reasons`
  - counts for `overfull_bar_count`, `underfull_bar_count`, `affected_event_count`, `overlap_count`, `tie_continuity_risk_count`, `many_risk_summary_count`, and `invalid_grid_count`
  - `automatic_repair_attempted: false`
  - `remediation_hint`
- **Visual Inspection Enhancements**: Modified `src/score2gp/report.py` to extract these root properties and display them in the visual Calibration card in `musicxml-timing-diagnostics.html`.
- **Tests Added**: Added `test_calibration_scenarios` in `tests/test_musicxml_invalid_fixtures.py` asserting correct feasibility results and count telemetry for all 10 synthetic fixtures.
- **Refused Timing Gates Preserved**: No automatic repair or duration adjustment is attempted. Unsafe timing scenarios strictly abort build-ir, keeping timing safety gates completely locked.

## Current Blocker Classification
- **Top Blocker**: `musicxml_invalid_timing_confirmed`
- **Rationale**: The newly added synthetic fixtures fully cover and replicate all unrecoverable timing scenarios found on private inputs (large overfull measures, overlaps, unresolved ties, high-density backup/forward risk) without copying any private music data. The preflight diagnostics successfully isolate candidates from unrecoverable scenarios. The timing safety gates remain strictly locked.

## Recommended Next Task
- **Next Task**: Begin design discussion on the exact contract and boundaries for a global timing calibration pass that can safely repair `musicxml_timing_calibration_candidate` cases (e.g. small ordered overfull drift) while maintaining strict refuse gates for all unrecoverable scenarios.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** loosen timing gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
