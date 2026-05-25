# TASKS

## Next

- [ ] Support visual note-level pitch bend variations and tremolo bar curve configurations inside the GPIF XML generator to further complete the guitar techniques pipeline.

## Done

- [x] Implement ScoreIR parsing/schema expansion and GPIF XML generation for note-level trill techniques (interval or auxiliary fret parameters) in the Guitar Pro writer (`src/score2gp/gpif.py`), verified with public synthetic fixtures and unit tests (`feature/gpif-trills-and-ornaments-v0.1`).

- [x] Implement ScoreIR parsing/schema expansion and GPIF XML generation for beat-level performance symbols—specifically fermatas, rolled arpeggios (up/down chord rollers), and brush directions (downstroke/upstroke indicators)—in the Guitar Pro writer (`src/score2gp/gpif.py`), verified with public synthetic fixtures and unit tests (`feature/gpif-beat-symbols-and-articulations-v0.1`).

- [x] Implement ScoreIR parsing/schema expansion and GPIF XML generation for dynamic hairpins (crescendo and decrescendo/diminuendo span markers) and note-level accent articulations (staccato, accent, marcato, tenuto) in the Guitar Pro writer (`src/score2gp/gpif.py`), verified with public synthetic fixtures and unit tests (`feature/gpif-dynamics-and-articulations-v0.1`).

- [x] Implement ScoreIR parsing/schema expansion and GPIF XML generation for pickup measures (incomplete initial bars with custom duration lengths) and custom visual barline configurations (double, end, section lines, repeat marks) in the Guitar Pro writer (`src/score2gp/gpif.py`), verified with public synthetic fixtures and unit tests (`feature/gpif-pickup-measures-and-barlines-v0.1`).

- [x] Implement ScoreIR parsing/schema expansion and GPIF XML generation for global page settings (page margins, page width, page height, layout scaling factors) and multi-track layout structures (stacked track order and visibility layouts) in the Guitar Pro writer (`src/score2gp/gpif.py`), verified with public synthetic fixtures and unit tests (`feature/gpif-notation-layout-formatting-v0.1`).

- [x] Implement ScoreIR parsing/schema expansion and GPIF XML generation for custom beat-level text annotations (arbitrary performance strings anchored to events) and visual layout breaks (explicit system/line breaks and page breaks) in the Guitar Pro writer (`src/score2gp/gpif.py`), verified with public synthetic fixtures and unit tests (`feature/gpif-annotations-and-layout-breaks-v0.1`).

- [x] Implement defensive payload sanitization and structural validation preflight gates inside ScoreIR models (`src/score2gp/ir.py`) to clamp anomalous time/pitch/fret/string/voice values and raise targeted failures for malformed structural arrays (`feature/pipeline-defensive-sanitization-v0.1`).

- [x] Implement ScoreIR support and GPIF XML generation for custom string counts/tunings (pitches per string) and track-level visual customisations (color tags and layout views) in the Guitar Pro writer (`src/score2gp/gpif.py`) and ScoreIR (`feature/gpif-tuning-and-track-formatting-v0.1`).

- [x] Implement ScoreIR support and GPIF XML generation for track-level mixer controls (volume, pan, mute, solo) and master tempo changes/automation across the timeline in the Guitar Pro writer (`src/score2gp/gpif.py`) and ScoreIR (`feature/gpif-mixer-and-tempo-automation-v0.1`).

- [x] Implement ScoreIR support and GPIF XML generation for tremolo picking and percussive/tapping articulations in the Guitar Pro writer (`src/score2gp/gpif.py`), mapping these properties from ScoreIR models into valid GP7-compatible XML tags and property structures (`feature/gpif-tremolo-picking-and-percussive-articulations-v0.1`).

- [x] Implement ScoreIR support and GPIF XML generation for chord diagrams and vibrato speed/depth curves in the Guitar Pro writer (`src/score2gp/gpif.py`), mapping these properties from ScoreIR models into valid GP7-compatible XML tags and property structures (`feature/gpif-chord-diagrams-and-vibrato-curves-v0.1`).

- [x] Implement ScoreIR support and GPIF XML generation for dead notes and tremolo bar expressions in the Guitar Pro writer (`src/score2gp/gpif.py`), mapping these properties from ScoreIR models into valid GP7-compatible XML tags (`feature/gpif-dead-notes-and-tremolo-v0.1`).

- [x] Implement ScoreIR support and GPIF XML generation for text directions and slide style variants in the Guitar Pro writer (`src/score2gp/gpif.py`), mapping these properties from ScoreIR models into valid GP7-compatible XML tags and property structures (`feature/gpif-text-directions-and-slides-v0.1`).

- [x] Implement ScoreIR support and GPIF XML generation for dynamic expressions and vibrato techniques in the Guitar Pro writer (`src/score2gp/gpif.py`), mapping these properties from ScoreIR models into valid GP7-compatible XML tags (`feature/gpif-dynamics-and-vibrato-v0.1`).

- [x] Implement the unified CLI convert orchestration command in the CLI (`src/score2gp/cli.py`) that sequentially executes extraction, alignment, IR generation, and GP packaging, aggregating stage warnings and generating conversion diagnostics reports (`feature/convert-orchestration-v0.1`).

- [x] Implement GPIF XML generation for multi-voice events in the Guitar Pro writer (`src/score2gp/gpif.py`), correctly separating and nesting events inside `<Voice>` containers per measure/beat based on ScoreIR voice IDs (`feature/gpif-multi-voice-v0.1`).

- [x] Implement ScoreIR support and GPIF XML generation for grace notes, let-ring spans, and palm-mute spans in the Guitar Pro writer (`src/score2gp/gpif.py`), mapping these properties from ScoreIR models into valid GP7-compatible XML tags (`feature/gpif-grace-and-spans-v0.1`).

- [x] Implement GPIF XML generation for core guitar techniques (slides, bends, hammer-ons, and pull-offs) in the Guitar Pro writer (`src/score2gp/gpif.py`), mapping these properties from ScoreIR models into valid GP7-compatible XML tags and property structures (`feature/gpif-core-techniques-v0.1`).

- [x] Implement GPIF XML generation for tied notes and tuplets (triplets) in the Guitar Pro writer (`src/score2gp/gpif.py`), mapping tie and tuplet properties from ScoreIR models into valid GP7-compatible XML tags (`feature/gpif-ties-and-tuplets-v0.1`).

- [x] Perform a structural and auditory validation of the successfully compiled Guitar Pro package (`private_input_1.gp`), identify, synthetically reproduce, and fix dynamic default time signature inference in MusicXML and robust, octave-invariant, continuous skipped-system synchronization in build-ir alignment (fix/gpif-rendering-fidelity-v0.1).

- [x] Address the remaining 24 string assignment gaps and 5 bar assignment gaps on the valid systems of `private_input_1` to completely pass the grouping phase (feature/pdf-fret-snapping-refinement-v0.1).

- [x] Implement measure synchronization logic in `build-ir` to safely align TabRaw measures with the MusicXML timeline even when an entire PDF system (or measure block) has been safely skipped during extraction (feature/musicxml-alignment-skipped-system-sync-v0.1).

- [x] Execute a private-safe E2E smoke review using `scripts/private_e2e_smoke.py` to evaluate the combined impact of vertical overlap resolution and robust string proximity calibration on real private inputs (chore/private-smoke-refresh-after-string-assignment-v0.1).


- [x] Implement same-column vertical string assignment heuristics to resolve `pdf_string_assignment_not_enough_for_build_ir` and `pdf_string_assignment_missing` blockers, using robust vertical proximity heuristics and systematic offset calibration (feature/pdf-string-assignment-heuristics-v0.1).

- [x] Implement Same-Column Vertical Overlap and Ambiguous Staff BBox Overlap public synthetic PDF fixtures and advanced vertical partitioning heuristics to safely resolve dense adjacent systems while keeping refusal for truly ambiguous layouts (feature/pdf-system-overlap-public-fixtures-v0.2).

- [x] Execute a private-safe smoke refresh using scripts/private_e2e_smoke.py with Skipping and Recovery heuristics, analyzing unboxed system status and remaining layout blockers (feature/private-smoke-refresh-after-unboxed-recovery-v0.1).

- [x] Implement Single-Measure System-Wide Recovery (Zero-Barline Fallback) and Opt-In System-Skipping Compiler Progression, verified completely with public synthetic born-digital PDF fixtures (feature/unboxed-system-recovery-v0.1).

- [x] Perform a localized private smoke test review under `allow_remediation=True` and draft a public design note (`docs/unboxed-system-recovery.md`) outlining unboxed system recovery and skips (docs/unboxed-system-recovery-design-v0.1).

- [x] Address the `musicxml_timing_risk` (specifically the 66 overfull or overlapping events blocking `private_input_1`) by implementing conservative timeline resolution or bounded tolerance heuristics in the MusicXML preflight logic (feature/musicxml-timing-risk-remediation-v0.1).

- [x] Refresh E2E private smoke blocker summary after vertical overlap resolution v0.1 to evaluate the impact on multi-system visual overlaps on page 1 of private_input_1.

- [x] Resolve vertical system overlap ambiguities and implement column-aware system ordering.

- [x] Execute a private-safe smoke refresh after conservative edge-boundary recovery to verify safety heuristics and blocker taxonomy updates.

- [x] Implement conservative edge-boundary recovery v0.1 with public synthetic born-digital PDF fixtures, dynamic recovered status, and compiler compile-safety integration.

- [x] Add a public partial-to-recovery design note before attempting any automatic grouping repair.

- [x] Add developer-facing HTML styling and compact thumbnails for grouping diagnostics.

- [x] Run a private-safe smoke refresh after `pdf-timing-refinement.v1.0` merges, reporting only timing/layout counts and categories.

- [x] Add public-safe `pdf-timing-refinement.v1.0` diagnostics to distinguish invalid MusicXML timing, unsupported-but-valid polyphony, and safe/partial/ambiguous/incompatible vector x-to-onset evidence without implementing timing repair.
- [x] Add public synthetic PDF fixtures and conservative diagnostics/heuristics for born-digital PDF fret-number extraction, optical bounds, and digit horizontal/vertical grouping, preserving strict compiler gates (feature/pdf-fret-refinement-v0.5).
- [x] Improve public-safe reporting, telemetry, and diagnostics for edge-boundary fallback rejection, compiling `pdf-edge-boundary-report.json`, premium standalone `pdf-edge-boundary-report.html`, and integrating references to them in both grouping overlays and compiler gates (feature/pdf-edge-boundary-reporting-v0.9).

- [x] Refresh E2E private smoke blocker summary after PDF edge system boundary fixtures v0.8 to verify that the conservative boundary inference policy correctly rejects unsafe fallback and reports `pdf_bar_box_one_boundary_rejected` for system 6 on page 2 of `private_input_1` (`feature/private-smoke-refresh-after-pdf-edge-system-boundary-v0.1`).

- [x] Add public synthetic PDF layout fixtures and conservative diagnostics/heuristics for edge systems where one accepted bar boundary exists and the other boundary is missing or rejected (feature/pdf-edge-system-boundary-public-fixtures-v0.8).

- [x] Refresh E2E private smoke blocker summary after PDF bar-box edge case fixtures v0.7 to verify whether the unboxed system 6 on page 2 of private_input_1 is correctly identified and classified under the new taxonomy (feature/private-smoke-refresh-after-pdf-bar-box-edge-cases-v0.1).
- [x] Refresh E2E private smoke blocker summary after PDF bar-box construction v0.6 to verify whether the new bar-box construction heuristics, taxonomy codes, and candidate boundary checks are accurately reported for real private layouts (feature/private-smoke-refresh-after-pdf-bar-box-construction-v0.1).
- [x] Add public synthetic PDF fixtures and conservative diagnostics/heuristics for bar-box construction and candidate assignment after barline validation succeeds (feature/pdf-bar-box-construction-public-fixtures-v0.6).
- [x] Add private-safe unrecoverable MusicXML timing diagnostic reports and user-facing remediation advice for unrecoverable timeline cursor overlaps (feature/musicxml-unrecoverable-timing-report-v0.1).
- [x] Refresh E2E private smoke blocker summary after PDF barline validation v0.5 to evaluate whether the relative crossing rules accept compact barlines on the real inputs (feature/private-smoke-refresh-after-pdf-barline-validation-v0.1).
- [x] Add public synthetic PDF barline validation fixtures and heuristics to refine vertical candidate rejection thresholds (feature/pdf-barline-validation-public-fixtures-v0.5).

- [x] Refresh E2E private smoke blocker summary after PDF bar detection fixtures v0.4 to verify that real private inputs report detailed barline candidates, accepted/rejected, and sub-blocker telemetry (feature/private-smoke-refresh-after-pdf-bar-detection-v0.1).

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
