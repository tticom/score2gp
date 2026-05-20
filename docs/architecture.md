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
