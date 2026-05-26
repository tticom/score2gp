# HANDOFF

## Metadata
- **Current Branch**: `bugfix/pipeline-internal-barline-tolerances`
- **Base Branch**: `main`
- **Current PR**: Open draft PR
- **Latest Local Commit**: `a4aec13bd6be6f895439d5638696cf2bf2176cdd` ("feat: refactor barline classification and deduplication with new tuning parameters")
- **Latest Pushed Commit**: `a4aec13bd6be6f895439d5638696cf2bf2176cdd` ("feat: refactor barline classification and deduplication with new tuning parameters")
- **Working Tree Status**: Clean (except local untracked helper scratch scripts).
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Tests and Checks Run
- `python -m pytest` -> All 391 tests passed successfully (100% success rate), including the new regression test `test_min_barline_height_ratio_and_deduplication` in `tests/test_pdf_parsing.py`.
- `python -m score2gp.cli export-schema --out schemas` -> schemas exported cleanly (`schemas/scoreir.v0.1.schema.json`).
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> IR validates cleanly as valid scoreir schema.
- `git diff --check` -> passed cleanly with zero whitespace errors.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under private/work paths.
- **E2E Smoke Verification**: Successfully compiled `private_input_1` with relaxed internal barline tolerances and double-barline horizontal merging active (generating a fully populated `score.ir.json` containing 16 bars and 131 events, and compiling `smoke.gp` safely).

## What Changed in the Task
- **CLI Options (`src/score2gp/cli.py`)**: Added `--min-barline-height-ratio` (float, default `0.65`) and `--barline-dedup-gap` (float, default `3.0`) to the `convert` and `build-ir` subcommands.
- **Compiler Plumbing (`src/score2gp/build_ir.py`)**: Plumbed the new parameters through `build_ir_from_files` and `build_ir_with_diagnostics_from_files` to downstream modules, defaulting strictly to `None` and `0.0` to preserve strict backward compatibility.
- **Layout Measure Segmentation Snapping Engine (`src/score2gp/pdf.py`)**:
  - Updated `extract_tab`, `_extract_pdf_text_candidates`, and `_detect_tab_systems` to accept the new float parameters.
  - In `_detect_tab_systems`, if `barline_dedup_gap` > 0.0, we cluster adjacent vertical candidates horizontally and merge them into single logical boundaries.
  - Relaxed vertical height validator: Accepted barlines where `height >= staff_height * min_barline_height_ratio` and `gaps_crossed >= len(ys) - 3` (allowing slightly shorter internal barlines while rejecting noisy fragments).
- **Regression Unit Tests (`tests/test_pdf_parsing.py`)**: Added `test_min_barline_height_ratio_and_deduplication` to assert correct layout behavior on custom vertical/horizontal candidate drawing mockups.

## Known Limitations
- None.

## Remaining Risks
- None.

## Next Recommended Task
- Merge draft PR, then focus on further layout alignment logic and formatting improvements.

## Explicit Scope Boundaries
- **No private files or work/ outputs committed**.
- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.