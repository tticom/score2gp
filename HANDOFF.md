# HANDOFF

## Metadata
- **Current Branch**: `feature/gp-originated-pdf-roundtrip-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #135](https://github.com/tticom/score2gp/pull/135)
- **Latest Local Commit**: `a2f3d8c` ("feat: implement GP flat XML parsing and E2E round-trip evaluation tool")
- **Latest Pushed Commit**: `a2f3d8c`
- **Working Tree Status**: Clean (committed and pushed)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Tests and Checks Run
- `python -m pytest` -> All 386 tests passed successfully (100% success rate, including the new `tests/test_pdf_confidence_ambiguity.py` proving robust GP XML parsing and roundtrip evaluation).
- `python -m score2gp.cli export-schema --out schemas` -> schemas exported cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid and compliant.
- `git diff --check` -> passed cleanly with zero whitespace issues.
- `git diff -- schemas` -> passed cleanly with zero changes.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked.

## E2E Round-Trip Evaluation Result
- **Target**: `Derek Trucks BB King.pdf` (private_input_1)
- **ScoreIR Written**: Yes (`score.ir.json` generated)
- **GP Written**: Yes (`smoke.gp` package compiled)
- **Extraction Candidate Counts**:
  - Playable Fret Candidates: 187
  - Playable Candidates with System: 178
  - Playable Candidates with Bar: 178
  - Playable Candidates with String: 178
- **Refusal Reason Codes**: `missing_pdf_grouping` (under default safety constraints, due to 9 unassigned candidates from unboxed trailing System 6 on Page 2).
- **Symmetric Oracle GP Semantic Comparison**:
  - Expected Notes (First 16 bars): 85
  - Recovered Notes: 93
  - String Matches: 1
  - Fret Matches: 0
  - Matching Rate: 0% fret matching due to a string layout indexing offset (recovered on high E string index 1 instead of B/G/D/A strings).

## What Changed in the Task
- **GP XML Parser Hardening (`src/score2gp/gp_package.py`)**:
  - Resolved `ValidationError` on `Tuning.strings` by implementing a standard 6-string guitar tuning fallback if the track lacks explicit `<String>` elements (e.g. keyboard/piano tracks in GP).
  - Resolved `ValidationError` on `ScoreIR.bars` unique bar indexes check by implementing 0-based `id` attributes parsing fallback for native GP7 flat `<Bar>` elements alongside 1-based `index` attributes.
  - Hardened `<Bars>` and `<MasterBars>` resolution by implementing XML element fallbacks that check for the presence of child `<Bar>` and `<MasterBar>` nodes, preventing nested master-bar tags from incorrectly overriding the root lists.
- **E2E Round-Trip Evaluation Tool (`scripts/gp_roundtrip_eval.py`)**:
  - Implemented `gp_roundtrip_eval.py` command line script executing the full E2E pipeline and parsing native GP7 flat XML format (`Notes`, `Beats`, `Voices`, `Bars`) to extract oracle notes.
  - Performs sequence-based notes matching across all measures, reporting private-safe matching statistics for strings, frets, and onsets.
- **Verification & Tests (`tests/test_pdf_confidence_ambiguity.py`)**:
  - Added unit tests verifying XML robust fallbacks for flat and nested GPIF formats, alongside test assertions for recovered notes extraction on public synthetic fixtures.

## Known Limitations
- Fret matching rate is currently 0% because the PDF extractor maps pitches to string 1 instead of string 5.
- Upstream trailing system is unboxed under standard global height/aspect ratios.

## Remaining Risks
- Trailing system unboxing and string index mapping need tuning for GP Qt-exported engraving dimensions.

## Next Recommended Task
- **Branch**: `feature/pipeline-gp-qt-engraving-tolerances-v0.1`
- **Goal**: Implement visual alignment parameters (vertical staff lines distance, digit vertical offset tolerance) to correctly map QT-engraved PDF geometry to strings 2-6 and resolve the trailing unboxed system without lowering safety bounds.
- **Explicit Scope Boundaries**: Preserve all strict grouping/timing safety gates, no scanned PDF support, no ML or OCR.