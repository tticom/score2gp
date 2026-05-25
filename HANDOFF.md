# Handoff

## Metadata

- **Current Branch**: `feature/gpif-multi-voice-v0.1`
- **Base Branch**: `main`
- **Current PR**: #73 (Draft PR: https://github.com/tticom/score2gp/pull/73)
- **Latest Local Commit**: `be4aa8b` ("feat: add script to inspect GPX file structure and element hierarchy")
- **Latest Pushed Commit**: `be4aa8b` ("feat: add script to inspect GPX file structure and element hierarchy")
- **Working Tree Status**: Clean.

- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. No root generated artifacts tracked.

## Tests And Checks Run

- `python -m pytest` -> 321 passed (100% success, including new synthetic test `test_gpif_multi_voice` and all existing tests).
- `python -m score2gp.cli export-schema --out schemas` -> passed cleanly (no differences).
- `python -m score2gp.cli validate-ir fixtures/public/test_gpif_multi_voice.ir.json` -> valid.
- `git diff --check` -> passed cleanly.
- `git diff -- schemas` -> empty (no schema differences).
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.

## What Changed In This Task

- **Multi-Voice Serialization**:
  - Refactored `_bars()` in `src/score2gp/gpif.py` to group events inside each `Bar` by their 0-indexed voice index (`event.timing.voice - 1`).
  - Serialized a `<Voices>` container tag under each `<Bar>` element.
  - Nest each active voice's events under a `<Voice id="{voice_idx}">` container tag under `<Voices>`, ensuring proper chronological sorting by onset ticks.
  - Adjusted `<Event>` tag serialization in `_event()` to write 0-indexed `"voice"` attributes (e.g. `event.timing.voice - 1`), keeping them in perfect alignment with their `<Voice>` parent tag per Guitar Pro 7 specifications.
- **Added Public Synthetic Fixtures & Tests**:
  - Created `fixtures/public/test_gpif_multi_voice.ir.json` modeling a single 4/4 measure with two distinct, non-overlapping polyphonic voices (eighth/quarter melody in voice 1, and half-note bass in voice 2).
  - Added unit test `test_gpif_multi_voice` in `tests/test_gp_writer.py` verifying correct structure and voice attributes in generated XML.
- **E2E Private Smoke Test Results**:
  - Verified with `scripts/private_e2e_smoke.py` that `private_input_1` compiles cleanly to `ScoreIR` and `Guitar Pro 7 package` (`smoke.gp`) with zero failure reasons, correctly mapping all contiguous bars and handling multi-voice tracks correctly without corrupting the `.gp` package layout.

## Known Limitations

- Scanning is limited to digital PDF vector layouts; no scanned-PDF, image-based OCR, or layout ML is supported.

## Remaining Risks

- None.

## Next Recommended Task

- **Milestone 5 & 6 Finalization**: Proceed with resolving next structural or rendering fidelity improvements or advancing to E2E packaging features once the draft PR is reviewed and merged.

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
