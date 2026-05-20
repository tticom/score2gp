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

`extract-tab` owns the PDF grouping diagnostic boundary. It writes `tab_raw.json` for candidate evidence, `warnings.json` for extraction warnings, and `grouping-diagnostics.html` plus `overlays/page-*-grouping.png` when grouping is missing or partial. The report is intentionally observational: it says extraction succeeded, grouping failed, and alignment/ScoreIR output should remain blocked until geometry is understood.
