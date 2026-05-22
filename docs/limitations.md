# Limitations

PDF-to-GP conversion is not solved by this project yet.

Known limitations:

- Generic OMR tools may miss guitar-specific tab, bends, slides, vibrato, let-ring marks, and fingering details.
- Born-digital PDF text extraction works only when fret numbers and symbols are encoded as extractable text.
- Current system/string/bar inference is heuristic and proven only on controlled public generated fixtures, including a two-system score-like page, not arbitrary score layouts.
- PDF grouping v0.1 requires born-digital vector-like tab geometry: six visible horizontal tab lines and vertical barlines. It does not infer systems from text-only layouts, scanned images, hidden staff lines, or arbitrary commercial engraving.
- Partial grouping is intentionally unsafe. Missing barlines, incomplete tab staff geometry, ambiguous string assignment, or ambiguous bar assignment produce `partial_pdf_grouping` and block `build-ir`; the overlays make the problem visible but do not repair it.
- ASCII-tab PDF support is diagnostic/extraction-level only. It recognises born-digital text rows and extracts fret/technique evidence, but it does not infer musical durations or convert ASCII character positions into trustworthy timing.
- `ascii-timing.v0.1` records character-column evidence, normalized row/segment positions, and aligned bar separators when present. This is alignment evidence, not duration evidence.
- `ascii-musicxml-alignment.v0.1` compares ASCII column evidence with MusicXML onsets in controlled public fixtures only. It can report compatible, partial, ambiguous, incompatible, or unavailable evidence, but it is a diagnostic proof sidecar, not a conversion engine.
- `ascii-scoreir-gate.v0.1` allows ScoreIR output only for one tiny controlled public ASCII/MusicXML proof shape. It is not general ASCII-tab conversion.
- The ASCII ScoreIR gate requires safe MusicXML timing, a compatible `ascii-musicxml-alignment.v0.1` sidecar, one-to-one candidate mappings, string/fret evidence from ASCII TabRaw, durations/rests from MusicXML, and no unsupported techniques, symbols, chords, polyphony, tuplets, ties, or grace notes.
- Complete ASCII-tab blocks without usable bar separators produce `ascii_tab_timing_unavailable` and `ascii_tab_measure_boundary_missing`. Barred/equal-width examples currently produce `partial_ascii_tab_timing`, while uneven or inconsistent rows produce `ambiguous_ascii_tab_timing`. Incomplete ASCII-tab row grouping produces `partial_ascii_tab_grouping`.
- Grouped reports and overlays show what the extractor inferred; they do not mean the musical timing is trustworthy without MusicXML timing and x-to-onset diagnostics.
- X-to-onset diagnostics now measure playable fret x groups against MusicXML onset groups, but this is not full optical calibration and does not repair bad geometry automatically.
- MusicXML timing preflight catches overfull bars and same-voice overlaps before ScoreIR output, but it does not make ambiguous Audiveris exports correct.
- Native `.mxl` intake is supported only for normal compressed MusicXML packages with a safe rootfile declared in `META-INF/container.xml`; malformed packages and unsafe rootfile paths are rejected.
- 12/8 and other compound-meter input is represented through exact MusicXML divisions and flagged as an assumption; it still needs human review when produced by OMR.
- If PDF extraction finds fret text but no system/string/bar grouping, the project reports `missing_pdf_grouping` and `build-ir` refuses to write ScoreIR rather than fabricating positions.
- The grouping HTML report and overlay images make grouping success and failure inspectable; they do not solve arbitrary PDF grouping or make unstructured fret text safe to align.
- A `good` x-to-onset quality label only means the current simple alignment looks internally consistent for the inspected controlled input.
- `warning`, `poor`, or `unknown` x-to-onset quality means the conversion should be inspected before trusting any automatic result.
- Chord symbols and technique text extracted from PDF-derived TabRaw are preserved and reported, but not yet aligned into ScoreIR events.
- Candidate text near tab systems is preserved as non-playable evidence; it is not interpreted musically.
- Scanned PDFs require OCR/image recognition that is not complete in the first milestone.
- The generated PDF regressions demonstrate controlled born-digital PDF producer paths; they do not mean private or commercial scores will convert cleanly.
- Private diagnostic runs are evidence-gathering only. Their summaries report counts and quality buckets, not copyrighted score content, and private artifacts must stay under ignored paths.
- GPIF support is minimal and may not cover every Guitar Pro feature.
- Unsupported or uncertain notation must be reported in warnings and conversion reports.

This tool is for files the user owns or has permission to process. It must not be used to bypass DRM or copy protected scores from unauthorised sources.
