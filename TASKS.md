# TASKS

## Next

- [ ] Add developer-facing HTML styling and compact thumbnails for grouping diagnostics.
- [ ] Add public reproductions for more Audiveris timing patterns before another private run.
- [ ] Design a public timing/alignment contract for ASCII-tab character positions before allowing ASCII TabRaw into ScoreIR.
- [ ] Attach PDF-derived chord symbols and technique text to ScoreIR events once timing calibration exists.
- [ ] Add HTML conversion report styling and unsupported-technique summaries.
- [ ] Add a public partial-to-recovery design note before attempting any automatic grouping repair.

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
- [x] PDF grouping v0.1 diagnostic boundary for generated born-digital tab fixtures.
- [x] Grouped/partial/missing extraction reports with inferred staff, string-line, barline, and bar-box overlays.
- [x] Low-confidence/partial-grouping public fixtures for missing barlines, incomplete staff geometry, ambiguous string assignment, and ambiguous bar assignment.
- [x] `partial_pdf_grouping` warning boundary with specific public diagnostic codes.
- [x] ASCII-tab PDF detection as a separate born-digital text input class.
- [x] Public synthetic ASCII-tab fixtures for complete rows, inline technique markers, legends, and malformed row grouping.
- [x] Conservative `ascii_tab_timing_unavailable` and `partial_ascii_tab_grouping` refusal boundaries.
