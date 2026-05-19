# TASKS

## Next

- [ ] Add compressed `.mxl` parsing for Audiveris exports.
- [ ] Replace simple x-order candidate matching with x-to-onset diagnostics.
- [ ] Add controlled private fixture evaluation only after public synthetic and generated fixtures are stable.
- [ ] Improve PDF line detection and overlay generation.
- [ ] Add HTML conversion report styling and unsupported-technique summaries.

## Done

- [x] Repository scaffold.
- [x] ScoreIR v0.1 contract, schema export, validation, and semantic comparison.
- [x] GP inspection command.
- [x] Minimal GPIF writer and GP zip package creation.
- [x] Validation command.
- [x] Initial docs and limitations.
- [x] Semantic GP comparison command.
- [x] Limited MusicXML importer for synthetic fixtures.
- [x] TabRaw v0.1 candidate model and born-digital text candidate extraction.
- [x] Synthetic MusicXML + TabRaw `build-ir` path.
- [x] Richer public synthetic fixtures for chords, tuplets, selected techniques, and alignment diagnostics.
- [x] `build-ir --diagnostics-out` sidecar with imported/matched/unmatched counts and per-bar summaries.
- [x] Public regression fixtures for multibar, chords, rests/voices, and invalid TabRaw inputs.
- [x] Generated public born-digital PDF fixture for real `extract-tab` regression.
- [x] Heuristic tab system/string/bar inference for vector six-line tab PDFs.
- [x] PDF-derived TabRaw to MusicXML to ScoreIR smoke path with diagnostics.
