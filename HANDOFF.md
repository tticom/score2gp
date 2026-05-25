# Handoff

## Metadata

- **Current Branch**: `feature/gpif-core-techniques-v0.1`
- **Base Branch**: `main`
- **Current PR**: N/A (Draft PR to be created)
- **Latest Local Commit**: `9e732ca` ("Implement GPIF XML serialization for slides, bends, hammer-ons, and pull-offs")
- **Working Tree Status**: Clean.

- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays warnings.json tuning_outside.tabraw.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 319 passed (100% success, including new synthetic test `test_gpif_core_techniques` and all existing tests).
- `python -m score2gp.cli export-schema --out schemas` -> passed cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/test_gpif_core_techniques.ir.json` -> valid.
- `git diff --check` -> passed cleanly.
- `git diff -- schemas` -> empty (no schema differences).
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.

## What Changed In This Task

- **Core Guitar Techniques Serialization**:
  - Implemented direct XML tags (`<Slide>`, `<Bend>`, `<HO>`, `<PO>`) under `<Note>` in `src/score2gp/gpif.py`'s `_note()`.
  - Implemented exact GP7 property blocks (`Slide`, `HopoOrigin`, `HopoDestination`, `Bended`, and float bended details) under `<Properties>` child of `<Note>`.
  - Added `"bend"` to `SUPPORTED_MINIMAL_TECHNIQUES` to prevent any warnings from being emitted for bends.
  - Implemented `_find_hopo_destinations` to pre-compute HO/PO destination notes on matching strings.
- **Added Public Synthetic Fixtures & Tests**:
  - Created `fixtures/public/test_gpif_core_techniques.ir.json` modeling slides, bends, hammer-ons, and pull-offs.
  - Added unit test `test_gpif_core_techniques` in `tests/test_gp_writer.py` asserting correct generated XML tags and properties.
  - Updated `test_write_gp_warns_for_unsupported_scoreir_fields` to warn for `"let-ring"` instead of the now-supported `"bend"`.
- **E2E Private Smoke Test Results**:
  - Verified with `scripts/private_e2e_smoke.py` that `private_input_1` compiles cleanly to `ScoreIR` and `Guitar Pro 7 package` (`smoke.gp`) with zero failure reasons, correctly mapping all contiguous bars and reporting ignored skipped events only on the unboxed/skipped Page 2 System 6.

## Known Limitations

- Scanning is limited to digital PDF vector layouts; no scanned-PDF, image-based OCR, or layout ML is supported.

## Remaining Risks

- None.

## Next Recommended Task

- **Milestone 4 & 5 Expansion (Grace Notes and Spans)**: Serialize remaining GP7/GPIF elements like grace notes, let-ring spans, and palm-mute spans in `gpif.py` once they are represented in ScoreIR.

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
