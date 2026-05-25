# Handoff

## Metadata

- **Current Branch**: `feature/gpif-dead-notes-and-tremolo-v0.1`
- **Base Branch**: `main`
- **Current PR**: N/A (draft PR will be created)
- **Latest Local Commit**: `5caebfc` ("Implement GPIF XML dead notes and tremolo whammy curves")
- **Latest Pushed Commit**: N/A (will be pushed)
- **Working Tree Status**: Clean.

- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. No root generated artifacts tracked.

## Tests And Checks Run

- `python -m pytest` -> 326 passed (100% success, including new synthetic test `test_gpif_dead_notes_and_tremolo`).
- `python -m score2gp.cli export-schema --out schemas` -> passed cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/test_gpif_dead_notes_tremolo.ir.json` -> valid.
- `git diff --check` -> passed cleanly.
- `git diff -- schemas` -> passed with updated schema.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `python scripts/private_e2e_smoke.py` -> passed cleanly against all private PDF inputs.

## What Changed In This Task

- **ScoreIR Schema Integration**:
  - Integrated `is_dead: bool = False` into the `Note` model (`src/score2gp/ir.py`).
  - Added `TremoloBarPoint` and `TremoloBarTechnique` classes, and registered `TremoloBarTechnique` under standard `Technique` union.
  - Re-exported the JSON schema cleanly to `schemas/scoreir.v0.1.schema.json`.
- **GPIF Dead Notes Serialization**:
  - Updated `_note` in `src/score2gp/gpif.py` to write GP7-compliant XML tag `<DeadNote />` under `<Note>` if `note.is_dead` is True.
- **GPIF Tremolo Bar Whammy Curves Serialization**:
  - Added support for `"tremolo-bar"` in `SUPPORTED_MINIMAL_TECHNIQUES` and updated `_note()` in `src/score2gp/gpif.py` to write GP7-compliant XML tag `<TremoloBar>` and its point table under `<Note>` when a tremolo-bar technique is present, mapping offset scale (0 to 100 percentage) and pitch value (semitones multiplied by 50).
- **Synthetic Testing & Validation**:
  - Authored a dedicated public synthetic fixture `fixtures/public/test_gpif_dead_notes_tremolo.ir.json` modeling dead notes and whammy dips.
  - Wrote comprehensive unit tests in `tests/test_gp_writer.py` verifying that `<DeadNote />` and `<TremoloBar>` tags are correctly structured and parsed in the generated GPIF XML.
- **E2E Private Smoke Test Results**:
  - Ran the smoke compiler against real private inputs (including `Derek Trucks BB King.pdf`) to verify zero regressions or crashes. All inputs compiled successfully with no builder issues.

## Known Limitations

- Scanning is limited to digital PDF vector layouts; no scanned-PDF, image-based OCR, or layout ML is supported.

## Remaining Risks

- None.

## Next Recommended Task

- ** Auditory & visual ornaments (Milestone 5)**: Expand coverage for further expressive/ornament tags (such as visual slide variations, chord-diagram formatting, text-directions, or vibrato speed/depth curves).

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
