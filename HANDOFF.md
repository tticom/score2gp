# HANDOFF

## Metadata
- **Current Branch**: `feature/roundtrip-quality-gate-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft PR to be created (associated with PR #135 / #136 context)
- **Latest Local Commit**: `cafa360` ("docs: update HANDOFF.md and TASKS.md with quality gate details and tests")
- **Latest Pushed Commit**: `cafa360` ("docs: update HANDOFF.md and TASKS.md with quality gate details and tests")
- **Working Tree Status**: Clean
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Tests and Checks Run
- `python -m pytest` -> All 387 tests passed successfully (100% success rate, including mock quality gate note count mismatch and GP robust bar queries).
- `python -m score2gp.cli export-schema --out schemas` -> schemas exported cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid and compliant.
- `git diff --check` -> passed cleanly.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked.

## E2E Results on Private Case (Derek Trucks BB King)
- **Strict-Mode Result**: Refused conversion because of unsafe grouping on page 2 system 6 (`partial_pdf_grouping`). `ScoreIR` and `GP` files are not written.
- **Permissive/Round-Trip Result**: Diagnostic `ScoreIR` and `GP` are written using unboxed system skipping and fallbacks (`allow_remediation=True`), but the quality gate blocks the output from being treated as successful.
- **Semantic Round-Trip Status**: `failed_alignment_quality`
- **Failure Category**: `failed_alignment_quality` (poor=13, unknown=3).
- **Semantic Comparison**: Fret match rate `0.0`, string match rate `0.0117`, all 16 bars have count mismatches.
- **Remaining Blocker**: Page 2, system 6 has less than two valid barlines detected (bar boxes not constructible); and layout/string matching vertical offsets causing 0% fret agreement.
- **Recommended Next Action**: `inspect-poor-or-unknown-bars-before-conversion`

## What Changed in the Task
- **Round-Trip Quality Gate Verdicts (`scripts/gp_roundtrip_eval.py`)**:
  - Implemented explicit verdict fields: `whether_scoreir_written`, `whether_gp_written`, `whether_semantic_comparison_ran`, `semantic_roundtrip_status`, `semantic_roundtrip_passed`, `diagnostic_only`, `failure_category`, `primary_failure_reason`, and `recommended_next_action`.
  - Defined explicit statuses: `not_run`, `passed`, `failed_note_count_mismatch`, `failed_string_fret_mismatch`, `failed_alignment_quality`, and `diagnostic_only`.
- **Acceptance Thresholds**:
  - String, fret, and full match rates must be >= 0.90.
  - Note counts must be within 2% tolerance.
  - No bars may have `unknown` or `poor` quality.
  - Any conversion that does not meet these is reported as failed / diagnostic-only.
- **Private-Safe Semantic Diagnostics**:
  - Added flags for string concentration on string 1, zero fret matching rate, measure count mismatches, and unboxed system barlines.
- **Hybrid Note Extraction**:
  - Refactored `extract_native_gp_notes` to be a hybrid parser. It checks the GP file structure: if it is a flat GP7 file, it parses `Bars`/`Voices`/`Beats`/`Notes`. If it is a score2gp nested package, it falls back to `extract_score_ir_from_gp` + `extract_recovered_notes`.
- **GP Package Parser Queries (`src/score2gp/gp_package.py`)**:
  - Made the `Bars` and `MasterBars` querying in `_extract_score_ir_from_gpif_root` robust to both nested score2gp elements and native flat XML elements.
- **Public Synthetic Regression Tests (`tests/test_pdf_confidence_ambiguity.py`)**:
  - Added `test_gp_package_robust_bars_querying` to verify robust GPIF element lookups.
  - Added `test_round_trip_quality_gate` validating:
    - 1. Positive passing case where recovered matches oracle exactly.
    - 2. Negative failing case due to poor/unknown bar quality (`failed_alignment_quality`).
    - 3. Negative failing case due to low match rates/string-fret mismatch (`failed_string_fret_mismatch`).
    - 4. Negative failing case due to note count mismatch (`failed_note_count_mismatch`).

## Known Limitations
- The private GP-exported PDF case currently fails the semantic round-trip gate due to alignment offsets and geometry failures.

## Remaining Risks
- Tuning string/fret layout mappings remains to be addressed in future tasks.

## Next Recommended Task
- Move to the next branch (e.g., `bugfix/string-layout-geometry-matching-v0.1`) to diagnose and resolve the string offset / fret snapping failures.

## Explicit Scope Boundaries
- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.