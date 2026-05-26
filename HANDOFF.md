# HANDOFF

## Metadata
- **Current Branch**: `feature/pipeline-clustering-tolerances-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft PR (pending creation via GitHub CLI)
- **Latest Local Commit**: `b1e8cbf` ("docs: update HANDOFF.md with feature implementation and validation details")
- **Latest Pushed Commit**: Pending push to origin
- **Working Tree Status**: Clean and synchronized locally.
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Tests and Checks Run
- `python -m pytest` -> All 389 tests passed successfully (100% success rate), including the new regression tests `test_string_for_y_ambiguity_resolver` and `test_string_for_y_ambiguity_closer_snapping` in `tests/test_pdf_parsing.py`.
- `python -m score2gp.cli export-schema --out schemas` -> schemas exported cleanly (`schemas/scoreir.v0.1.schema.json`).
- `git diff --check` -> passed cleanly with zero whitespace errors.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under private/work paths.

## What Changed in the Task
- **CLI Tolerances Options (`src/score2gp/cli.py`)**: Added three new options `--max-digit-gap` (float, default `2.0`), `--string-snap-tolerance` (float, default `1.5`), and `--strip-technique-text` (bool, default `False`) to both the `convert` and `build-ir` Typer command hooks, passing them natively through compiler layers down to the layout extraction engine.
- **Compiler Core Plumb (`src/score2gp/build_ir.py`)**: Updated entry points `build_ir_from_files` and `build_ir_with_diagnostics_from_files` to accept the new configuration parameters.
- **Digit Merging and Spacing (`src/score2gp/pdf.py`)**: Refactored the adjacent horizontal digit merge check to use `max_digit_gap` (which defaults to `5.0` in the library signatures to maintain perfect backwards compatibility with existing tests).
- **Technique Stripping Filter (`src/score2gp/pdf.py`)**: Pre-filters out known non-musical technique string literals (`{"full", "b", "r", "sl", "vibrato"}` case-insensitively) if `strip_technique_text` is `True` before performing playable digit overlap checks.
- **Staff Ambiguity Snapping Resolver (`src/score2gp/pdf.py`)**: Refactored `string_for_y` to use `string_snap_tolerance` cushion. When a note falls within multiple string cushions simultaneously, absolute vertical midpoint distances are sorted, snapping cleanly to the single closest string instead of throwing an ambiguity warning or returning `None`.
- **Synthetic Test Fixture (`fixtures/public/test_clustering_tolerances.ir.json`)**: Created synthetic ScoreIR fixture representing kerned digits and tightly packed staff lines.
- **Automated Unit Tests (`tests/test_pdf_parsing.py`)**: Created unit tests verifying symmetric snapping and ambiguity resolution behavior under custom snap tolerances.

## Known Limitations
- None.

## Remaining Risks
- None.

## Next Recommended Task
- Push the branch, create the draft PR, and merge into `main` after checks pass.

## Explicit Scope Boundaries
- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.