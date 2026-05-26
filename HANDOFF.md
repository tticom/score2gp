# HANDOFF

## Metadata
- **Current Branch**: `feature/pdf-confidence-ambiguity-public-fixtures-v0.1`
- **Base Branch**: `main`
- **Current PR**: #134 (https://github.com/tticom/score2gp/pull/134)
- **Latest Local Commit**: `840688049df3b680fe0cf9e34e56598c92bdfdb9` ("docs: update HANDOFF.md with latest commit metadata for ambiguity feature branch")
- **Latest Pushed Commit**: `840688049df3b680fe0cf9e34e56598c92bdfdb9` ("docs: update HANDOFF.md with latest commit metadata for ambiguity feature branch")
- **Working Tree Status**: Clean.
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Tests and Checks Run
- `python -m pytest` -> Executed suite including the new `tests/test_pdf_confidence_ambiguity.py`. Assertions successfully prove the layout engine strictly refuses unsafe geometries and correctly emits ambiguity warnings.
- `python -m score2gp.cli export-schema --out schemas` -> schemas exported cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid and compliant.
- `git diff --check` -> passed cleanly.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked.

## What Changed in the Task
- **Diagnostic Regression Coverage (`tests/test_pdf_confidence_ambiguity.py`)**: Added small, synthetic, deterministic public fixtures and tests to isolate and reproduce the remaining private-safe confidence blockers.
- **Isolated Warning Classes**:
  - `pdf_fret_digit_symbol_overlap_ambiguous`
  - `pdf_fret_digits_not_merged_gap_too_large`
  - `pdf_string_assignment_compact_staff_ambiguous`
  - `pdf_fret_optical_bounds_confidence_below_threshold`
- **Safe Counterpart Validation**: Added a baseline test proving that safe, well-spaced geometries still successfully achieve a `"grouped"` status without loosening existing gates.

## Known Limitations
- The system remains a strict, conservative recognizer. Files with heavy engraving noise, symbol overlap, or extreme font kerning will continue to be safely rejected to prevent corrupt musical output.

## Remaining Risks
- Conversion of highly expressive or condensed layout PDFs will require manual review or future explicit notation mapping capabilities.

## Next Recommended Task
- Merge `feature/pdf-confidence-ambiguity-public-fixtures-v0.1` into `main`. With the ambiguity blockers properly covered by public diagnostics, assess which warnings represent valid musical features (e.g., standard layout overlapping conventions) vs. actual extraction noise, and plan targeted, deterministic feature support for them.

## Explicit Scope Boundaries
- **No private files or work/ outputs committed**.
- **No tuning of thresholds to pass private examples**.
- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No loosening of grouping/string/fret/timing/build-ir gates**.