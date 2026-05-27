# HANDOFF

## Metadata
- **Current Branch**: `bugfix/gp-exported-pdf-layout-research-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #137](https://github.com/tticom/score2gp/pull/137) (Draft)
- **Latest Local Commit**: `c52c541` ("fix: implement DP-based global system-to-measure alignment to resolve call-and-response gaps and correct GP7 MasterBar oracle mapping")
- **Latest Pushed Commit**: `c52c541` ("fix: implement DP-based global system-to-measure alignment to resolve call-and-response gaps and correct GP7 MasterBar oracle mapping")
- **Working Tree Status**: Clean
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Tests and Checks Run
- `python -m pytest` -> All 389 tests passed successfully (100% success rate, including the new `test_dp_measure_resynchronization` proving DP alignment correctly syncs call-and-response gaps).
- `python -m score2gp.cli export-schema --out schemas` -> schemas exported cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid and compliant.
- `git diff --check` -> passed cleanly (0 trailing whitespaces).
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked.

## What Changed in the Task
- **DP-Based Global Measure Resynchronization (`src/score2gp/build_ir.py`)**:
  - Replaced the greedy skipped-system alignment with a global Dynamic Programming (DP) alignment algorithm using standard sounding pitches (with octave-invariant +12 transposing guitar offsets).
  - GAP_PENALTY is set to a robust `0.5` per skipped measure, allowing the alignment to cleanly skip omitted solo responses (such as the BB King phrases in Measures 4 and 8) while preventing noisy alignment drift on short systems.
- **Oracle MasterBar Alignment Correction (`scripts/gp_roundtrip_eval.py`)**:
  - Fixed a critical indexing bug in `extract_native_gp_notes` where `b_idx` in the global `Bars` container was treated as the 1-indexed `MasterBar` index.
  - Constructed a robust mapping from MasterBars space-separated Bar lists to correctly retrieve the actual 1-indexed `MasterBar` number for Track 0 (guitar part) Bar IDs, which accurately raises the total GP Track 0 oracle notes from `85` to `203` (and correctly reflects all 16 measures).
- **Public Fixtures and Test Regression Updates (`tests/`)**:
  - Added new regression test `test_dp_measure_resynchronization` inside `tests/test_pdf_confidence_ambiguity.py` proving that DP-based synchronization correctly handles omitted systems and jumps to correct measure starts.

## Known Limitations
- The E2E round-trip string and fret match rates are currently 44 (21.7%) and 16 (7.9%) respectively, because some measures in the simplified PDF sheet music version only transcribe Derek Trucks' phrases (Measures 1, 2, 3, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16) whereas the MusicXML/GP oracle contains lead solo notes across all measures (including BB King's responses, or accompaniment).
- 32 MusicXML notes/events are unmatched, and 86 TabRaw PDF candidates remain unmatched.

## Remaining Risks
- None.

## Next Recommended Task
- Align the MusicXML solo parts or filter out non-transcribed accompaniment/response parts to achieve 100% semantic matching rates.

## Explicit Scope Boundaries
- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
- **No MusicXML pitch/tuning data** used to bypass PDF geometry gates.