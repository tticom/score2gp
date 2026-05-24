# Architecture

`score2gp` is a staged pipeline. Each stage writes inspectable artefacts so recognition mistakes can be found and fixed.

1. PDF ingestion
   - Determine whether a PDF appears born-digital/vector or scanned/raster.
   - Render pages to images.
   - Extract embedded text blocks and coordinates when available.
   - Write diagnostics under a work directory.

2. Page and system segmentation
   - Detect staff systems, notation staves, tablature staves, barlines, tab lines, chord symbols, and technique text.
   - Write overlay images for human inspection.
   - When grouping fails, write a small HTML report plus candidate-box overlays so extraction evidence can be inspected without promoting it to musical events.

3. Symbolic recognition
   - Use Audiveris optionally for standard notation to MusicXML/MXL.
   - Parse plain `.musicxml`/`.xml` and compressed `.mxl` packages through the same MusicXML importer and timing preflight.
   - Compressed `.mxl` intake reads `META-INF/container.xml` and the declared rootfile directly from the zip package; it does not extract private files to disk.
   - Extract guitar tab separately, preferring PDF vector text coordinates before OCR.
   - Associate fret numbers by y-position/string and x-position/beat.

4. ScoreIR
   - Normalize recognised material into strict JSON.
   - Preserve confidence, source stage, warnings, and bounding boxes.

5. GP writer
   - Generate GPIF XML with XML APIs.
   - Package GPIF into a GP7-style zip.
   - Preserve template package members where possible.

6. Validation and comparison
   - Validate zip structure and XML well-formedness.
   - Inspect GP semantic features.
   - Compare expected and actual scores semantically, not byte-for-byte.

## Current Diagnostic Boundaries

The current build-ir path refuses known-unsafe input before writing ScoreIR. MusicXML timing risks such as overfull bars and same-voice overlaps produce `build-ir-failure-diagnostics.v0.1`. PDF-derived TabRaw with playable fret candidates but no usable system/string/bar grouping produces `missing_pdf_grouping` or `pdf_grouping_not_safe_for_build_ir` warnings instead of allowing ungrouped text to become musical notes.

`extract-tab` owns the PDF grouping and system layout diagnostic boundary. Its PDF grouping is deliberately conservative and public-fixture driven: it uses born-digital PDF drawing geometry to find horizontal tab lines, groups them as a tab staff using a gap-cluster search to handle vertically interleaved/overlapping tab systems, detects vertical barlines that cross the staff, assigns fret text to the nearest string line, and assigns candidates to bar boxes by x-position. The grouping evidence remains extraction metadata in TabRaw candidate `raw` payloads and the HTML report; it is not part of ScoreIR.

For playable PDF evidence, `extract-tab` writes `tab_raw.json`, `warnings.json`, `grouping-diagnostics.html`, and `overlays/page-*-grouping.png`. The report distinguishes grouped, partial, missing, ambiguous, or unsupported grouping. The overlays show candidate boxes, inferred staff boxes, string lines, barlines, and bar boxes where available. If any playable candidate lacks required system/string/bar grouping, or if severe layout anomalies are found, `build-ir` refuses the input with a `BuildIrInputRiskError` rather than treating uncertain text as music.

### PDF Layout and Grouping Diagnostics
PDF layout diagnostics are public-fixture driven, with private smoke testing only identifying safe counts, statuses, and taxonomy codes without using private score data. The project implements a robust warning taxonomy for layout/grouping anomalies, ensuring that unsafe groupings are blocked from `build_ir`:
- **System and Bar Detection as Distinct Stages**: The pipeline clearly separates *system detection* (locating the tab staff line structure) from *bar detection* (finding vertical barlines and measure boundaries). If system detection succeeds but barlines are missing, it is reported as a bar-detection blocker (`pdf_system_detected_bar_detection_missing`, `pdf_input_class_drawn_tab_requires_barlines`), rather than conflating the two.
- **Refined Barline Validation Limits**: A refined barline-validation taxonomy distinguishes absolute vs relative height thresholds, staff crossing, insufficient gaps, partial crossing, etc. Specifically, a barline candidate is accepted even if it is compact (below the 40pt absolute threshold, but at least 20pt) when it has safe relative staff-crossing evidence (crosses all gaps on the detected tab staff). Short or non-crossing lines remain strictly rejected as `pdf_barline_does_not_cross_staff` or `pdf_barline_too_short_absolute`. Details of gaps crossed, staff coverage, absolute/relative decisions, and final verdict are stored in telemetry.
- **Bar-Box Construction and Safety Heuristics**: Validating barlines is independent of constructing bar boxes. Accepted barlines are not guaranteed to form safe bar boxes. The construction stage enforces width restrictions (adjacent barlines < 30.0pt trigger `pdf_bar_box_too_narrow`), boundary system horizontal checks (out-of-bounds triggers `pdf_bar_box_outside_system_bounds`), overlap checks (`pdf_bar_box_overlaps_neighbor`), and page-level system boxed checks (`pdf_partial_grouping_one_system_unboxed` when boxed and unboxed systems are mixed). Candidates exactly or nearly on a bar box boundary are rejected as ambiguous (`pdf_candidate_on_bar_boundary` or `pdf_bar_box_boundary_ambiguous`), and candidates outside constructed boxes remain unassigned (`pdf_candidate_unassigned_to_bar`). Build-ir enforces that any layout warning blocks the `pdf_grouped` status, forcing `partial_pdf_grouping` and raising a strict `BuildIrInputRiskError` to prevent compilation.
- **Edge System Boundary Fallback Heuristics**: In tightly constrained cases where a system has exactly one accepted barline and the other boundary is missing, a conservative fallback policy evaluates whether a system edge can be safely inferred:
  - **Left Edge Fallback**: If playable candidates exist to the left of the accepted barline, fallback is allowed only if there are no rejected barlines to the left, the width `mid_x - self.x0 >= 30.0pt`, and no candidates lie too close to `self.x0` (distance < `ambiguous_bar_tolerance`).
  - **Right Edge Fallback**: If playable candidates exist to the right, fallback is allowed only if there are no rejected barlines to the right, the width `self.x1 - mid_x >= 30.0pt`, and no candidates lie too close to `self.x1`.
  - **Provenance and Telemetry**: Inferred boundaries are marked in telemetry as `pdf_bar_box_inferred_edge_boundary` (`pdf_bar_box_inferred_left_boundary` / `pdf_bar_box_inferred_right_boundary`) and output with info warning codes rather than silently promoting them to observed barlines.
  - **Strict Rejections**: If any rejected barlines exist in the inference direction (making boundaries ambiguous), if the width is too narrow, or if a candidate is near the edge, fallback is rejected (`pdf_bar_box_edge_boundary_fallback_rejected`, `pdf_bar_box_edge_boundary_ambiguous`, `pdf_bar_box_inferred_boundary_too_narrow`, etc.).
  - **Compiler Gating**: Safe fallbacks are whitelisted to allow build-ir compilation to proceed *only* if grouping remains complete (all playable candidates have valid system/bar/string assignments). Any fallback rejection or unassigned candidate strictly blocks compilation and raises `BuildIrInputRiskError`.
- **Separate System Input Classes**: Drawn-tab and ASCII-tab are treated as entirely distinct system classes:
  - **Drawn Tab**: Expects vector staff geometry. Standard blockers include `pdf_drawn_system_not_detected`, `pdf_drawn_system_ambiguous`, or `pdf_drawn_staff_lines_unresolved`.
  - **ASCII Tab**: Identified as six-row character blocks (`pdf_ascii_system_detected`). Standard blockers include `pdf_ascii_system_measure_boundaries_missing` and `pdf_ascii_system_timing_unavailable`.
- **ASCII Blocks Insufficient for Timing**: While ASCII blocks provide fret and string evidence, character positions or columns alone are never sufficient to infer note durations or musical onset timing. They must be validated against a MusicXML timing source via an alignment sidecar (`pdf_input_class_ascii_tab_requires_alignment`).
- **Detected Systems Insufficient for ScoreIR**: Merely detecting systems or staff geometry is not enough to compile ScoreIR. A safe conversion requires that systems, bars, and strings are all safely grouped and assigned (`pdf_system_detection_not_enough_for_build_ir`). If any grouping layer is unsafe, `build_ir` strictly refuses compilation.
- **No OCR/Scanned-PDF/ML Support**: The pipeline relies purely on born-digital vector geometry and explicit text coordinates. Scanned pages or rasterized images cannot be parsed, and no OCR or machine-learning layout recognition is added.

- **System Detection Issues**: `pdf_no_systems_detected` (no horizontal tab systems found), `pdf_partial_system_detection` (only some systems found), `pdf_tab_staff_missing` (staff lines missing/not detected), `pdf_tab_staff_incomplete` (partial tab staff with fewer than six string lines), `pdf_tab_staff_ambiguous` (systems layout is ambiguous due to vertical overlap).
- **Barline & Bar Issues**: `pdf_barlines_missing` (staff inferred but barlines not detected), `pdf_barlines_ambiguous` (candidates too close to barlines to assign safely), `pdf_bar_boxes_missing` (measure bar boxes could not be inferred), `pdf_candidate_outside_bar` (candidate is located outside system barlines).
- **String Issues**: `pdf_string_lines_missing` (string lines completely missing), `pdf_string_assignment_missing` (string lines not detected or candidate too far to assign), `pdf_string_assignment_ambiguous` / `pdf_candidate_between_strings` (candidate too far from a single string line to assign safely).
- **Other Layout/Grouping Anomaly Warning Codes**: `pdf_candidate_outside_system` (candidate located horizontally outside the system), `pdf_multi_system_order_ambiguous` (multiple systems with vertically overlapping ranges), `pdf_page_layout_unsupported` (unsupported page layout), `pdf_text_candidate_without_geometry` (candidate text lacks geometry), `pdf_ascii_and_drawn_layout_conflict` (both ASCII blocks and drawn systems exist on page), and `pdf_grouping_not_safe_for_build_ir` (general unsafe grouping flag).

### PDF Fret Refinement, Digit Grouping, and Bounding Box Heuristics
Fret number optical bounds, digit extraction, and grouping heuristics are fully integrated as a distinct diagnostic stage before system/bar/string consumption:
- **Proportional Mixed-Word Splitting**: Fret digits written near or touching technique markers (such as `7h9`, `5/7`, or `8b`) are split into separate playable digit candidates and non-playable technique markers. Bounding boxes are estimated proportionally based on character length relative to the overall word width. Pure technique characters are marked as non-playable and excluded using `pdf_fret_technique_marker_excluded`.
- **Conservative Horizontal Grouping**: Multi-digit frets split across separate text spans are merged on a per-string-band basis. Horizontally adjacent digits are merged only if they are vertically aligned (`vertical_offset <= 2.0pt`) and horizontally tight (`0.0 <= gap <= 5.0pt`), generating `pdf_fret_digits_merged` and `pdf_fret_split_text_span_merged` warnings.
- **Granular Grouping Rejections**: Digits that are vertically misaligned (`vertical_offset > 2.0pt`) or horizontally too far apart (`5.0pt < gap <= 12.0pt`) are rejected from merging, flagging `pdf_fret_digits_not_merged_vertical_misalignment` or `pdf_fret_digits_not_merged_gap_too_large` and blocking downstream.
- **Fret Value and Bounding Box Size Gates**: Playable fret candidates must be numeric and within a valid physical range (`0 <= fret <= 24` or else flagged as `pdf_fret_outside_valid_range`). Candidates must also respect tight bounding box size constraints:
  - Height must not exceed `1.2 * line_spacing` or `18.0pt` (`pdf_fret_bbox_too_tall`).
  - Width must not exceed `2.5 * line_spacing` or `35.0pt` (`pdf_fret_bbox_too_wide`).
  - Width or height below `2.0pt` triggers `pdf_fret_bbox_too_small` (noisy candidates).
  - Candidates with optical confidence below `0.70` trigger `pdf_fret_optical_bounds_confidence_below_threshold`.
- **Chord and Page/Legend Exclusions**: Digit-like text in chord symbols or section headings above the staff (`A7`, `Verse 2`) or page/legend numbers outside tab systems (`Legend: 1 = Ring`) are preserved as non-playable candidates but strictly excluded from playable fret evidence using `pdf_fret_chord_text_digit_excluded` or `pdf_fret_page_or_legend_number_excluded` warnings.
- **Diagnostics Reporting**: Diagnostic payloads and HTML reports are enriched with fret refinement counts, classification metrics, bounding box averages, vertical misalignment deltas, horizontal gap metrics, and tailored remediation advice.
- **Strict Scope Boundaries**: The refinement logic is purely synthetic and vector-based. OCR, scanned-PDF support, and machine-learning layout recognition remain strictly out of scope. Fret values are never inferred from MusicXML pitch or tuning.

These warnings block `build_ir` immediately. Partially grouped real examples are not made to pass, and missing bars or strings are never inferred from note pitch.

ASCII-tab PDFs are a separate input class from drawn tab staff geometry. Some born-digital PDFs contain text rows such as string labels followed by a pipe and ASCII tab characters rather than vector string lines. To ensure the detectors do not conflate them, drawn and ASCII tab geometry remain strictly separate. If both are detected on the same page, the layout is flagged as unsupported via `pdf_ascii_and_drawn_layout_conflict`, blocking `build_ir` and ScoreIR generation. `extract-tab` detects these with `ascii-tab.v0.1`, groups nearby six-row blocks, assigns string numbers by row order, extracts fret numbers from character spans, and preserves inline markers such as slides, hammer-ons, pull-offs, bends, releases, and vibrato as non-playable technique-text evidence.

ASCII-tab timing evidence is a separate `ascii-timing.v0.1` diagnostic contract stored in TabRaw candidate raw payloads. It records row labels, character spans, column indexes, normalized row/segment positions, aligned bar-separator columns, measure segment IDs where available, a timing status (`timing_unavailable`, `timing_partial`, or reserved `timing_safe`), confidence, and warnings. Character columns are not musical timing by themselves: aligned `|` separators can support weak measure segmentation, but they do not define durations or trustworthy onsets. `build-ir` therefore refuses ASCII-tab candidates with `ascii_tab_timing_unavailable`, `partial_ascii_tab_timing`, `ambiguous_ascii_tab_timing`, or `partial_ascii_tab_grouping` instead of writing ScoreIR from timing guesses.

`ascii-musicxml-alignment.v0.1` is a diagnostic sidecar that compares ASCII-tab column evidence with MusicXML onsets in controlled public fixtures. It keeps the ASCII parser evidence, MusicXML timing evidence, candidate mapping attempts, onset distance, confidence, and warning codes outside ScoreIR. The sidecar can classify the proof as `compatible`, `partial`, `ambiguous`, `incompatible`, or `unavailable`, but compatibility is only a precondition for writing.

`ascii-scoreir-gate.v0.1` is the explicit writing boundary for ASCII TabRaw. It allows ScoreIR output only for a tiny controlled public fixture where ASCII parser evidence, ASCII timing evidence, a compatible ASCII/MusicXML alignment sidecar, safe MusicXML timing, monophonic MusicXML notes, string/fret candidate evidence, and one-to-one candidate mappings all agree. Durations and rests come from MusicXML; strings and frets come from ASCII TabRaw. The gate refuses missing sidecars, partial/ambiguous/incompatible/unavailable alignment, unsupported techniques, symbols, chords, polyphony, tuplets, ties, grace notes, missing string/fret evidence, risky MusicXML timing, and anything beyond the narrow public proof shape.

Gate refusal diagnostics are part of the architecture, not an exceptional afterthought. `build-ir` reports `ascii_scoreir_gate_status`, a primary reason code, secondary reason codes, candidate/alignment/rejection counts, MusicXML timing safety, alignment sidecar status, whether ScoreIR was written, and a short remediation hint. Public refusal codes include `missing_ascii_alignment_sidecar`, `ascii_alignment_status_unavailable`, `ascii_alignment_status_partial`, `ascii_alignment_status_ambiguous`, `ascii_alignment_status_incompatible`, `ascii_alignment_candidate_missing`, `ascii_alignment_not_one_to_one`, `ascii_candidate_missing_string`, `ascii_candidate_missing_fret`, `ascii_candidate_unmapped_measure`, `ascii_candidate_unmapped_onset`, `ascii_unsupported_technique_required`, `ascii_unsupported_chord_symbol`, `ascii_polyphony_not_supported`, `ascii_musicxml_timing_risk`, `ascii_duration_source_missing`, and `ascii_outside_tiny_gate_scope`.

## HTML Diagnostics for ASCII Gate Refusal

To make gate refusal easy to understand for developers, `build-ir` generates a developer-facing HTML diagnostics report (`ascii-scoreir-gate-diagnostics.html`) alongside the JSON diagnostics sidecar when an ASCII gate refusal occurs.
- **Developer-Facing Explanations**: The HTML report provides a human-readable layout of why the input was refused, primary and secondary reason codes, and remediation advice.
- **JSON as Source of Truth**: The JSON diagnostics payload remains the programmatic source of truth for the pipeline and downstream automated checks.
- **Scope Limits**: Refusal is the expected, deterministic behavior for unsupported ASCII inputs. The HTML report does not broaden the ASCII success path, and does not imply broader ASCII-to-ScoreIR conversion support, scanned-PDF support, OCR, or symbol/technique attachment, all of which remain strictly out of scope.

## HTML Diagnostics for Symbol Attachment

To assist in visual review of the conservative TabRaw symbol and technique attachment process, `build-ir` generates a developer-facing HTML diagnostics report (`symbol-attachment-diagnostics.html`) when diagnostics are requested.
- **Visual Evidence Review**: The report provides a clear display of attached and unattached chord symbol and technique candidates, listing their target bar index, event ID, note target (string/fret), confidence, provenance ID, and refusal warnings.
- **Strict Scope Boundaries**:
  - **JSON remains the programmatic source of truth** for all symbol and technique attachments.
  - **GPIF rendering is NOT implemented**. The HTML report does not render or represent tab in a graphical guitar tab format.
  - **Symbols and techniques DID NOT create notes, events, or timing**. They are only attached as conservative metadata/evidence to existing, safely timed events.
  - Unsupported/ambiguous symbols and technique texts remain strictly as diagnostic evidence (warnings) rather than being promoted or silently dropped.

## HTML Diagnostics for MusicXML Timing & Overlap Risks

To make MusicXML timing and overlap failures easy to understand and inspect for developers, `build-ir` generates a developer-facing HTML diagnostics report (`musicxml-timing-diagnostics.html`) alongside the JSON diagnostics sidecar when a MusicXML timing risk or polyphony gate refusal occurs during the import preflight stage.
- **Voice Cursor / Timeline Model**: Uses a deterministic MusicXML voice cursor/timeline model to simulate backup, forward, chord, rest, and voice cursor movements per measure. This ensures correct interpretation of multi-voice timelines before deciding whether timing is valid, unsupported, or unsafe.
- **Detailed Timing Analysis**: The HTML report provides a human-readable table of all timing issues, showing their severity, reason codes, measure numbers, affected voices, note IDs, and detailed descriptions.
- **Verdict & Remediation Hints**: Clearly highlights the primary timing risk or polyphony refusal code and provides tailored remediation advice to guide the developer.
- **JSON as Source of Truth**: The JSON diagnostics payload remains the programmatic source of truth for downstream tools.
- **Strict Safety Gates**: MusicXML timing risks and unsupported polyphony strictly block ScoreIR generation to prevent downstream alignment and rendering failures, rather than silently dropping or flattening voices, rests, or tuplets.
- **Polyphony Gate Refusal**: Separates invalid timing (e.g., same-voice overlaps) from valid but unsupported multi-voice structures (`musicxml_scoreir_polyphony_gate_refused`), ensuring that valid polyphony is not misclassified as timing risk.
- **Refined Timing Diagnostic Codes**: The preflight catches same-voice overfull measures, accumulated small duration overflow, same-voice event overlap, rest/note overlap, backup without voice switch overlap, event extending past measure, compound meter overfull, and invalid duration grid cases using a taxonomy of precise codes.
- **Calibration Boundary & Metadata**: The diagnostics track precise metrics: calibration feasibility, overfull divisions, overlap counts, and affected event IDs. Calibration is flagged as possible only if the overfull error is small (<= 1 quarter note beat), events remain ordered, and no overlaps occur.
- **Synthetic Public Fixtures**: Public synthetic MusicXML timing blocker fixtures (v0.2, v0.3, and v0.4) are added under `tests/fixtures/musicxml/` to safely reproduce and test these specific failure modes, ensuring CI validation remains independent of any private materials.
- **Timing Refinement v1.0**: Failure diagnostics include `pdf-timing-refinement.v1.0` telemetry that classifies MusicXML timing as `invalid_timing_refused`, `unsupported_polyphony_refused`, `mixed_invalid_timing_and_unsupported_polyphony_refused`, `timing_warning_or_info_only`, or `timing_safe`. These classifications are counts/status metadata only; they do not repair MusicXML.
- **No Automatic Repair**: The current implementation does not attempt automatic timing repair or calibration, and strict timing safety gates remain fully intact.
See [Timing Refinement v1.0 Design Note](timing-refinement-v1.0.md) for the public-safe boundary.

## Unrecoverable MusicXML Timing Reports

To assist developers and users in diagnosing unrecoverable MusicXML timing failures without exposing private score content, the pipeline outputs structured reports:
- **Anonymised JSON Sidecar (`musicxml-unrecoverable-timing-report.json`)**: Serves as the programmatic source of truth. It records only private-safe, anonymised telemetry including the anonymised source label (e.g. `private_input_1`), stage reached (`musicxml-import`), timing gate status (`refused`), expected measure ticks, actual voice end ticks, overfull/underfull counts, tie continuity risks, and a list of affected note IDs. It explicitly excludes all private score details, pitch steps, note names, lyrics, chord symbols, or raw MusicXML snippets.
- **User-Facing HTML Report (`musicxml-unrecoverable-timing-report.html`)**: Renders a visually premium dark-mode summary of the unrecoverable timeline. It displays:
  - **Verdict block**: Highlighting `calibration_possible: false` and `automatic_repair_attempted: false`.
  - **Counts summary**: Of overfull measures, underfull measures, tie risks, overlaps, and affected events.
  - **Affected measures timeline breakdown**: Listing Part ID, Measure Number/Index, Voice ID, Expected Ticks, Actual Ticks, Overfull/Underfull Amount, and Reason Codes.
  - **Remediation guidance**: Providing actionable instructions to regenerate or simplify the source MusicXML before attempting ScoreIR conversion.
- **Integration**: The build-ir diagnostics payload references these report filenames (`unrecoverable_timing_report_json` and `unrecoverable_timing_report_html`). The private smoke test summary includes only their relative artifact paths within the ignored `work/` directory, preventing any private data leakage into tracked git files.

## PDF Edge-Boundary Fallback Reports

To assist developers in diagnosing edge-boundary fallback rejections without exposing private score content, the pipeline outputs structured reports when a fallback is rejected:
- **Anonymised JSON Sidecar (`pdf-edge-boundary-report.json`)**: Serves as the programmatic source of truth. It records private-safe, anonymised telemetry including the page and system index, observed/accepted/rejected/inferred boundary counts, fallback considered/accepted/rejected status, fallback rejection reason codes, missing sides, accepted/rejected boundary sides, candidate counts, candidates assigned to system/bar, candidates unassigned due to failed boundary, and remediation hints. It explicitly excludes all private score details, note names, lyrics, chord symbols, or raw PDF text.
- **Developer-Facing HTML Report (`pdf-edge-boundary-report.html`)**: Renders a visually premium dark-mode summary of the fallback rejection. It displays:
  - **Verdict block**: Highlighting fallback rejected, grouping partial, and build-ir blocked.
  - **Grid layout**: For system identification (page/system index, missing side) and boundary statistics.
  - **Fallback decision details**: Listing considered/accepted/rejected status and granular rejection reason codes.
  - **Impact table**: Showing candidate counts and playable candidates unassigned due to the failed boundary.
  - **Remediation guidance**: Providing actionable instructions to regenerate the PDF, repair barlines, or manually review layout constraints.
- **Integration**: The grouping diagnostics HTML (`grouping-diagnostics.html`) includes direct links to both the JSON and HTML edge-boundary reports under the Artifacts list. Furthermore, the `BuildIrInputRiskError` failure diagnostics payload references these report filenames during a `tabraw-import` stage refusal, and the E2E smoke test summary records their relative paths within the ignored `work/` folder.

## PDF Timing Ingestion & Spacing Mapping Diagnostics

To safely evaluate physical visual spacing against musical timings, `build_ir` implements a conservative PDF-derived TabRaw x-position to MusicXML pitched onset timing mapping diagnostics module:
- **Separation of Concerns**: The mapping is purely diagnostic. It does not perform timing repair, calibrate fret widths, move candidates, or alter MusicXML durations.
- **Contract Schema Version**: Telemetry is structured under the `pdf-timing-mapping.v0.7` schema version. It populates grouping safety status, MusicXML timing safety status, whether mapping was attempted or refused, precise error reason codes, matched/unmatched group counts, absolute/relative spacing drift metrics, and monotonicity status.
- **Timing Refinement Classification**: The mapping payload also includes `pdf-timing-refinement.v1.0` fields that classify vector layout evidence as `safe`, `partial`, `ambiguous`, `incompatible`, `unavailable`, or `refused`. This makes x-to-onset evidence easier to review without treating it as repair authority.
- **HTML Visual Report (`pdf-timing-mapping-diagnostics.html`)**: Renders a visually premium dark-mode summary of the spacing alignment. It provides:
  - **Verdict block**: Highlighting quality class (`good`, `warning`, `poor`, `unknown`, `refused`), attempted/refused status, and clear refusal reason codes.
  - **Grid layout**: For grouping safety, timing source safety, and MusicXML timing preflight status.
  - **Timing refinement details**: Showing the v1.0 classification and reason codes while JSON remains the source of truth.
  - **Per-bar spacing comparison table**: Showcasing candidate counts, pitched onset counts, bar quality, absolute relative errors, and visual drift warnings.
  - **Remediation guidance**: Explicitly stating that timing mapping is diagnostic-only and cannot repair timing.
- **Strict Gating Rules**:
  - **Refusal Preconditions**: If PDF grouping is unsafe (`partial_pdf_grouping`) or MusicXML timing preflight fails, mapping is refused/not attempted.
  - **Monotonicity Check**: If candidate x-positions across bars are non-monotonic, build-ir compilation is refused with `pdf_timing_mapping_non_monotonic` and raises a `BuildIrInputRiskError`.
  - **Build-ir Gates**: Poor quality or uneven spacing triggers warnings and visual telemetry but does not block ScoreIR compilation, allowing controlled, slightly uneven born-digital inputs to succeed while reporting clear spacing risks.

## Public End-to-End PDF-to-GP Proof Slice

To demonstrate the structural integrity of the entire staged pipeline (PDF extraction, alignment, ScoreIR building, validation, GP writing, package validation, and semantic fact comparison), there is a public end-to-end integration proof.
- **Proof Coverage**: Exercises TabRaw candidate extraction from a born-digital ASCII-tab PDF, onset compatibility alignment with a matching monophonic MusicXML, ScoreIR generation using the compatible alignment sidecar, validation against schemas, minimal Guitar Pro package generation, and verification of track counts, tuning names, and note properties.
- **Honest Boundaries**: This is a narrow vertical slice on highly controlled, synthetic public fixtures. It serves to prove the pipelines are connected, but does not weaken the conservative safety gates, does not infer timing or notes from raw columns, and does not enable broad commercial or scanned-PDF score conversions.
