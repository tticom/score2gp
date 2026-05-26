# HANDOFF

## Metadata
- **Current Branch**: `feature/roundtrip-quality-gate-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft PR to be created (associated with PR #135 / #136 context)
- **Latest Local Commit**: `060a0e3` ("feat: implement hard round-trip quality gate and hybrid flat/nested GP note extractor")
- **Latest Pushed Commit**: Pending push to origin
- **Working Tree Status**: Clean
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Tests and Checks Run
- `python -m pytest` -> All 387 tests passed successfully (100% success rate, including mock quality gate and GP robust bar queries).
- `python -m score2gp.cli export-schema --out schemas` -> schemas exported cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid and compliant.
- `git diff --check` -> passed cleanly.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked.

## Round-Trip Evaluation on Private E2E Case
- **PDF File**: `fixtures/private/Derek Trucks BB King.pdf`
- **ScoreIR/GP Written**: Yes (`ScoreIR` and `smoke.gp` packages written).
- **Semantic Round-Trip Passed**: No.
- **Verdict Status**: `failed_alignment_quality` (fret match rate `0.0`, string match rate `0.0117`, all 16 bars have count mismatches).
- **Exact Failure Category**: `poor_bar_quality` (poor=13, unknown=3).
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
    - Positive passing case where oracle matches exactly.
    - Negative failing case due to poor bar quality.
    - Negative failing case due to low string/fret match rates.

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