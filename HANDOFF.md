# Handoff

## Metadata

- **Current Branch**: `feature/musicxml-alignment-skipped-system-sync-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft PR to be created (`feature/musicxml-alignment-skipped-system-sync-v0.1`)
- **Latest Local Commit**: `27fcc89d9df7e4180cdad6538b43566a59adba51` ("Implement skipped system measure synchronization and offset alignment heuristics")
- **Working Tree Status**: Modified HANDOFF.md and TASKS.md.

- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 314 passed (100% success, including new synthetic test `test_skipped_system_sync_logic`).
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` -> empty.

## What Changed In This Task

- **Robust Unboxed System Skipping Classification**:
  - Refined `has_rejected_barlines` in `src/score2gp/build_ir.py` to check page/system index warning keys and fall back to parsing warning message strings if keys are missing (such as for `pdf_barline_too_short`).
  - Added explicit `page_index` and `system_index` keys to all barline and bar-box warnings generated in `src/score2gp/pdf.py` to ensure complete telemetry data integrity.
- **Skipped Candidate Filtering**:
  - Updated the unboxed systems skipping loop in `src/score2gp/build_ir.py` to always filter out candidates with `system_index is None` when `allow_skip_unboxed` is active, cleanly skipping unassigned layout fragments.
- **Measure Synchronization & Offset Alignment Heuristics**:
  - Implemented `_synchronize_skipped_system_measures` in `src/score2gp/build_ir.py` to automatically align candidates' `bar_index` values with continuous MusicXML measures using MIDI pitch-matching and a tie-breaking penalty that prefers the previous offset.
  - Successfully shifts downstream candidate bar indices to map them to the correct MusicXML measures when an entire system is skipped.
- **Created Synthetic Skipped System Sync Test**:
  - Added `tests/test_skipped_system_sync.py` proving that a 3-measure synthetic score compiles perfectly to ScoreIR even when its intermediate system is skipped and its downstream system index is offset by 1 measure.
- **E2E Private Smoke Test Verification**:
  - Executed `scripts/private_e2e_smoke.py` proving that `private_input_1` Page 2 System 6 is now successfully skipped (45 candidates excluded) and the remaining candidates on Page 2 are correctly aligned, resolving the system-skipping gap.

## Known Limitations

- Real private scores may still fail compilation due to real, genuine visual layout ambiguity warnings on other pages (e.g. `private_input_1` has 5 missing bar box assignments and 24 missing string assignments on valid systems).

## Remaining Risks

- Dense chords or complex polyphony on edge systems may require more advanced snapping thresholds if they lie outside standard staff lines.

## Next Recommended Task

- **Fret snaps and string calibration**: Address the remaining 24 string assignment gaps and 5 bar assignment gaps on the valid systems of `private_input_1` to completely pass the grouping phase.

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
