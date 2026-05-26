# HANDOFF

## Metadata
- **Current Branch**: `bugfix/pdf-left-bracket-barline-alignment`
- **Base Branch**: `main`
- **Current PR**: #129 (https://github.com/tticom/score2gp/pull/129)
- **Latest Local Commit**: `fc41908` ("bugfix: accept left-edge overarching system bracket barlines in layout compiler")
- **Latest Pushed Commit**: `fc41908` ("bugfix: accept left-edge overarching system bracket barlines in layout compiler")
- **Working Tree Status**: Modified `TASKS.md` and `HANDOFF.md` are uncommitted.
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Tests and Checks Run
- `python -m pytest` -> All 387 tests passed successfully (100% success rate, including the new regression test `test_left_bracket_barline_alignment_acceptance` proving acceptance of the overarching left-edge system bracket).
- `python -m score2gp.cli export-schema --out schemas` -> schemas exported cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid and compliant.
- `git diff --check` -> passed cleanly with zero whitespace errors.
- `git diff -- schemas` -> in sync, no diff.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under private/work paths.

## What Changed in the Task
- **Left-Edge Bracket Barline Acceptance (`src/score2gp/pdf.py`)**: Refactored the vertical line classification loops in `_detect_tab_systems` to explicitly accept left-edge vertical brackets that align horizontally with the system start (`x_val` matching `x0` within 6.0 pt) and vertically with the bottom baseline of the TAB staff (`y_max` matching `y1` within 4.0 pt). If these criteria are met, the candidate bypasses the strict height/relative staff-crossing checks and is marked as an accepted structural left boundary.
- **Regression Test (`tests/test_left_bracket_alignment.py`)**: Implemented a geometric unit test modeling a TAB staff from `Y: 624.102` to `655.992` and a vertical line at `X: 28.346` with a height of `82.833` (whose bottom matches `y1` and top spans upward above the notation staff). Verified that this overarching bracket is successfully accepted as a valid barline boundary with zero rejections.

## Known Limitations
- None.

## Remaining Risks
- None.

## Next Recommended Task
- Merge `bugfix/pdf-left-bracket-barline-alignment` into `main` after checks pass.

## Explicit Scope Boundaries
- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.