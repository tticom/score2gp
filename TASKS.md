# TASKS

## Next

- [ ] Improve PDF system detection using public fixtures that resemble the private grouping failure.
- [ ] Add structured per-page extraction diagnostics for missing grouping and low-confidence system candidates.
- [ ] Add developer-facing HTML styling and compact thumbnails for grouping diagnostics.
- [ ] Add public reproductions for more Audiveris timing patterns before another private run.
- [ ] Attach PDF-derived chord symbols and technique text to ScoreIR events once timing calibration exists.
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
- [x] Score-like public generated PDF fixture with multiple systems, chord symbols, technique text, candidate text, and spacing variation.
- [x] Heuristic tab system/string/bar inference for vector six-line tab PDFs.
- [x] PDF-derived TabRaw to MusicXML to ScoreIR smoke path with per-bar and per-system diagnostics.
- [x] X-to-onset diagnostics for controlled generated PDFs, including an uneven-spacing warning fixture.
- [x] Public-safe private diagnostic workflow with sanitized count/quality summaries.
- [x] Public Audiveris-like MusicXML timing-risk fixtures.
- [x] Preflight overfull MusicXML before writing invalid ScoreIR.
- [x] Public generated PDF fixture for extraction succeeded/grouping failed diagnostics.
- [x] Native compressed `.mxl` parsing in the main MusicXML importer.
- [x] `build-ir` refusal for PDF-derived playable candidates with missing system/string/bar grouping.
- [x] HTML and overlay report for extraction succeeded/grouping failed cases.
