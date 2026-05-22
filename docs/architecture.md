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

The current build-ir path refuses known-unsafe input before writing ScoreIR. MusicXML timing risks such as overfull bars and same-voice overlaps produce `build-ir-failure-diagnostics.v0.1`. PDF-derived TabRaw with playable fret candidates but no usable system/string/bar grouping produces `missing_pdf_grouping` instead of allowing ungrouped text to become musical notes.

`extract-tab` owns the PDF grouping diagnostic boundary. Its current PDF grouping v0.1 is deliberately conservative and public-fixture driven: it uses born-digital PDF drawing geometry to find six near-horizontal tab lines, groups them as a tab staff, detects vertical barlines that cross the staff, assigns fret text to the nearest string line, and assigns candidates to bar boxes by x-position. The grouping evidence remains extraction metadata in TabRaw candidate `raw` payloads and the HTML report; it is not part of ScoreIR.

For playable PDF evidence, `extract-tab` writes `tab_raw.json`, `warnings.json`, `grouping-diagnostics.html`, and `overlays/page-*-grouping.png`. The report distinguishes grouped, partial, and missing grouping. The overlays show candidate boxes, inferred staff boxes, string lines, barlines, and bar boxes where available. If any playable candidate lacks required system/string/bar grouping, `build-ir` refuses the input rather than treating uncertain text as music.

Partial grouping is explicit. Public fixtures cover tab text with missing barlines, incomplete five-line staff geometry, ambiguous string assignment, and ambiguous bar assignment. These cases emit `partial_pdf_grouping` plus a specific warning code such as `missing_pdf_barlines`, `incomplete_tab_staff`, `ambiguous_string_assignment`, or `ambiguous_bar_assignment`. Partial evidence is useful for debugging extraction, but it is not safe input for ScoreIR generation.

ASCII-tab PDFs are a separate input class from drawn tab staff geometry. Some born-digital PDFs contain text rows such as string labels followed by a pipe and ASCII tab characters rather than vector string lines. `extract-tab` detects these with `ascii-tab.v0.1`, groups nearby six-row blocks, assigns string numbers by row order, extracts fret numbers from character spans, and preserves inline markers such as slides, hammer-ons, pull-offs, bends, releases, and vibrato as non-playable technique-text evidence.

ASCII-tab timing evidence is a separate `ascii-timing.v0.1` diagnostic contract stored in TabRaw candidate raw payloads. It records row labels, character spans, column indexes, normalized row/segment positions, aligned bar-separator columns, measure segment IDs where available, a timing status (`timing_unavailable`, `timing_partial`, or reserved `timing_safe`), confidence, and warnings. Character columns are not musical timing by themselves: aligned `|` separators can support weak measure segmentation, but they do not define durations or trustworthy onsets. `build-ir` therefore refuses ASCII-tab candidates with `ascii_tab_timing_unavailable`, `partial_ascii_tab_timing`, `ambiguous_ascii_tab_timing`, or `partial_ascii_tab_grouping` instead of writing ScoreIR from timing guesses.

`ascii-musicxml-alignment.v0.1` is a diagnostic sidecar that compares ASCII-tab column evidence with MusicXML onsets in controlled public fixtures. It keeps the ASCII parser evidence, MusicXML timing evidence, candidate mapping attempts, onset distance, confidence, and warning codes outside ScoreIR. The sidecar can classify the proof as `compatible`, `partial`, `ambiguous`, `incompatible`, or `unavailable`, but compatibility is only a precondition for writing.

`ascii-scoreir-gate.v0.1` is the explicit writing boundary for ASCII TabRaw. It allows ScoreIR output only for a tiny controlled public fixture where ASCII parser evidence, ASCII timing evidence, a compatible ASCII/MusicXML alignment sidecar, safe MusicXML timing, monophonic MusicXML notes, string/fret candidate evidence, and one-to-one candidate mappings all agree. Durations and rests come from MusicXML; strings and frets come from ASCII TabRaw. The gate refuses missing sidecars, partial/ambiguous/incompatible/unavailable alignment, unsupported techniques, symbols, chords, polyphony, tuplets, ties, grace notes, missing string/fret evidence, risky MusicXML timing, and anything beyond the narrow public proof shape.

Gate refusal diagnostics are part of the architecture, not an exceptional afterthought. `build-ir` reports `ascii_scoreir_gate_status`, a primary reason code, secondary reason codes, candidate/alignment/rejection counts, MusicXML timing safety, alignment sidecar status, whether ScoreIR was written, and a short remediation hint. Public refusal codes include `missing_ascii_alignment_sidecar`, `ascii_alignment_status_unavailable`, `ascii_alignment_status_partial`, `ascii_alignment_status_ambiguous`, `ascii_alignment_status_incompatible`, `ascii_alignment_candidate_missing`, `ascii_alignment_not_one_to_one`, `ascii_candidate_missing_string`, `ascii_candidate_missing_fret`, `ascii_candidate_unmapped_measure`, `ascii_candidate_unmapped_onset`, `ascii_unsupported_technique_required`, `ascii_unsupported_chord_symbol`, `ascii_polyphony_not_supported`, `ascii_musicxml_timing_risk`, `ascii_duration_source_missing`, and `ascii_outside_tiny_gate_scope`.

## HTML Diagnostics for ASCII Gate Refusal

To make gate refusal easy to understand for developers, `build-ir` generates a developer-facing HTML diagnostics report (`ascii-scoreir-gate-diagnostics.html`) alongside the JSON diagnostics sidecar when an ASCII gate refusal occurs.
- **Developer-Facing Explanations**: The HTML report provides a human-readable layout of why the input was refused, primary and secondary reason codes, and remediation advice.
- **JSON as Source of Truth**: The JSON diagnostics payload remains the programmatic source of truth for the pipeline and downstream automated checks.
- **Scope Limits**: Refusal is the expected, deterministic behavior for unsupported ASCII inputs. The HTML report does not broaden the ASCII success path, and does not imply broader ASCII-to-ScoreIR conversion support, scanned-PDF support, OCR, or symbol/technique attachment, all of which remain strictly out of scope.
