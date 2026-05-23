# TASKS

## Next

- [ ] Add public reproductions for more Audiveris timing patterns before another private run.
- [ ] Add developer-facing HTML styling and compact thumbnails for grouping diagnostics.
- [ ] Add a public partial-to-recovery design note before attempting any automatic grouping repair.

## Done

- [x] Refresh E2E private smoke blocker summary after PDF system detection fixtures v0.4 to verify distinct layout stages and blocker taxonomies (feature/private-smoke-refresh-after-pdf-system-v0.4).

- [x] Add public synthetic PDF fixtures for unresolved staff lines and scanned-tab system boundaries, separating system detection from bar detection and drawn from ASCII input classes (feature/pdf-system-detection-public-fixtures-v0.4).

- [x] Refresh the E2E private smoke blocker summary after PDF layout diagnostics v0.3 to evaluate real inputs and identify detailed layout warning codes (PR #28).

- [x] Add public synthetic PDF layout fixtures and diagnostics for the remaining missing_pdf_grouping / system-not-detected blocker classes (feature/pdf-layout-public-fixtures-v0.3).

- [x] Refresh the private smoke blocker summary after MusicXML calibration-boundary diagnostics to confirm calibration feasibility on real inputs (PR #26).

- [x] Add public synthetic MusicXML fixtures and diagnostics for unrecoverable invalid timing / non-safe calibration scenarios, refining calibration boundary feasibility telemetry and blocking reasons (PR #25).

- [x] Re-run the E2E private smoke workflow to verify that the new same-voice invalid timing and overfull measure diagnostics accurately classify and report the exact counts and calibration feasibility on the private inputs (PR #24).

- [x] Add public synthetic MusicXML fixtures and tests for invalid same-voice timing / overfull measures, refining preflight diagnostics, calibration boundaries, and developer-facing reports (PR #23).
- [x] Refresh private smoke blocker summary after voice cursor model (PR #22).
- [x] Implement a deterministic MusicXML voice cursor/timeline model that correctly interprets backup/forward/chord/rest/voice cursor movement, separating same-voice overlaps (timing risk) from valid but unsupported cross-voice polyphony (polyphony gate refusal).
- [x] Refresh private smoke blocker summary after MusicXML timing public fixtures v0.3 (PR #19).
- [x] Add a third round of public synthetic MusicXML timing fixtures (v0.3) focused on remaining voice cursor alignment, backup/forward movement, and Audiveris-like timing risks, with refined preflight diagnostics and tests.
- [x] Refresh private smoke blocker summary after MusicXML timing public fixtures (PR #17).
- [x] Add public synthetic MusicXML timing blocker fixtures for compound meter (12/8) and backup/forward voice cursor movements, with refined preflight diagnostics and error taxonomy.
- [x] Refresh private-safe diagnostic smoke blocker summary after recent PDF layout and MusicXML preflight timing diagnostics work.
- [x] Improve PDF grouping and system layout diagnostics based on private-smoke warning classes without tuning to private files, adding public synthetic fixtures for layout failure modes and blocking unsafe grouping in build_ir.
- [x] Improve public MusicXML timing/overlap diagnostics, error taxonomy, and developer-facing HTML reports.
- [x] Local private-safe E2E diagnostic smoke workflow to evaluate real private score fixtures and generate anonymized master summaries.
- [x] Public end-to-end PDF-to-GP conversion proof slice targeting a controlled public ASCII-tab PDF + compatible MusicXML.
- [x] Attach PDF-derived chord symbols and technique text to ScoreIR events once timing calibration exists.
- [x] Developer-facing HTML rendering for attached and unattached chord/technique evidence in generated ScoreIR.
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
- [x] Public `ascii-timing.v0.1` contract for character-column, bar-separator, and normalized segment evidence.
- [x] Conservative `partial_ascii_tab_timing`, `ambiguous_ascii_tab_timing`, and measure-boundary warning boundaries.
- [x] Public `ascii-musicxml-alignment.v0.1` proof sidecar comparing ASCII timing evidence with MusicXML onsets.
- [x] Conservative `compatible`, `partial`, `ambiguous`, `incompatible`, and `unavailable` ASCII/MusicXML alignment diagnostics.
- [x] `build-ir` refusal boundary for ASCII alignment sidecars, including compatible sidecars until ScoreIR writing is explicitly designed.
- [x] Tiny public `ascii-scoreir-gate.v0.1` success path for ASCII TabRaw plus compatible MusicXML alignment.
- [x] Conservative ASCII ScoreIR gate refusal diagnostics for missing sidecars, unsafe sidecars, unsupported techniques, missing string/fret evidence, broad polyphony, and MusicXML timing risk.
- [x] Public ASCII ScoreIR gate refusal taxonomy for missing mappings, non-one-to-one mappings, unsupported chord symbols, missing measure/onset evidence, missing MusicXML duration source, and failure diagnostics sidecars.
- [x] Developer-facing HTML rendering for ASCII ScoreIR gate refusal diagnostics.
