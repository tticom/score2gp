# Handoff

## Metadata

- **Current Branch**: `feature/gpif-grace-and-spans-v0.1`
- **Base Branch**: `main`
- **Current PR**: N/A (Draft PR to be created)
- **Latest Local Commit**: `4181fe5` ("Implement GPIF XML serialization for grace notes, let-ring spans, and palm-mute spans")
- **Working Tree Status**: Clean.

- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 320 passed (100% success, including new synthetic test `test_gpif_grace_and_spans` and all existing tests).
- `python -m score2gp.cli export-schema --out schemas` -> passed cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/test_gpif_grace_and_spans.ir.json` -> valid.
- `git diff --check` -> passed cleanly.
- `git diff -- schemas` -> empty (no schema differences).
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.

## What Changed In This Task

- **Grace Notes Serialization**:
  - Implemented `<GraceNotes>` element under `<Event>` in `src/score2gp/gpif.py`'s `_event()`. Dynamically maps ScoreIR grace timing and grace techniques to `"OnBeat"` or `"BeforeBeat"` string text values.
  - Removed obsolete warning for `grace` in `gpif_warnings()`.
- **Note Spans Serialization (LetRing & PalmMute)**:
  - Implemented `_find_span_notes()` in `gpif.py` to pre-calculate all note coordinates `(bar_index, onset_ticks, string)` that fall inside let-ring or palm-mute spans, using absolute start ticks for each bar to robustly track spans extending across multiple bars.
  - Dynamically serialize `<LetRing />` and `<PalmMute />` elements under `<Note>` in `_note()` for all notes inside the respective spans.
  - Added `"grace"`, `"let-ring"`, and `"palm-mute"` to `SUPPORTED_MINIMAL_TECHNIQUES` to prevent any warnings from being emitted.
- **Added Public Synthetic Fixtures & Tests**:
  - Created `fixtures/public/test_gpif_grace_and_spans.ir.json` modeling grace notes (before beat and on-beat), let-ring spans, and palm-mute spans.
  - Added unit test `test_gpif_grace_and_spans` in `tests/test_gp_writer.py` asserting correct generated XML tags and attributes.
  - Updated `test_write_gp_warns_for_unsupported_scoreir_fields` to warn for `"unsupported"` instead of the now-supported `"let-ring"`.
- **E2E Private Smoke Test Results**:
  - Verified with `scripts/private_e2e_smoke.py` that `private_input_1` compiles cleanly to `ScoreIR` and `Guitar Pro 7 package` (`smoke.gp`) with zero failure reasons, correctly mapping all contiguous bars and reporting ignored skipped events only on the unboxed/skipped Page 2 System 6.

## Known Limitations

- Scanning is limited to digital PDF vector layouts; no scanned-PDF, image-based OCR, or layout ML is supported.

## Remaining Risks

- None.

## Next Recommended Task

- **Milestone 4 & 5 Expansion (Multi-voice Events)**: Support multi-voice events serialization in the GPIF writer `gpif.py` to completely finalize all multi-voice notation.

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
