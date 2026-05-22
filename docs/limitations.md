# Limitations

PDF-to-GP conversion is not solved by this project yet.

Known limitations:

- Generic OMR tools may miss guitar-specific tab, bends, slides, vibrato, let-ring marks, and fingering details.
- Born-digital PDF text extraction works only when fret numbers and symbols are encoded as extractable text.
- Current system/string/bar inference is heuristic and proven only on controlled public generated fixtures, including a two-system score-like page, not arbitrary score layouts.
- PDF grouping requires born-digital vector-like tab geometry: horizontal tab lines and vertical barlines. It does not infer systems from scanned images, raster pixels, or arbitrary commercial engraving, and ML layout recognition/OCR is not supported.
- PDF system layout diagnostics are strictly conservative. Missing barlines, incomplete tab staff geometry, ambiguous string assignment, out-of-system/out-of-bar candidates, multi-system vertical overlaps, or mixed ASCII/drawn layouts produce specific warning codes and block `build_ir`; overlays make the issues visible but do not repair them.
- Any unsafe layout warning (such as `pdf_no_systems_detected`, `pdf_multi_system_order_ambiguous`, `pdf_ascii_and_drawn_layout_conflict`, etc.) triggers `pdf_grouping_not_safe_for_build_ir` or direct layout risk categories in `build_ir`, which strictly raises a `BuildIrInputRiskError` and prevents ScoreIR file compilation.
- Drawn vector tab geometry and ASCII-tab text remain separate input classes and are never conflated. A conflict flags `pdf_ascii_and_drawn_layout_conflict` and refuses ScoreIR generation.
- Prose legend pages with no tab lines correctly fail with `pdf_no_systems_detected` and block `build_ir`, even if there are zero playable fret candidates on the page.
- ASCII-tab PDF support is diagnostic/extraction-level only. It recognises born-digital text rows and extracts fret/technique evidence, but it does not infer musical durations or convert ASCII character positions into trustworthy timing.
- `ascii-timing.v0.1` records character-column evidence, normalized row/segment positions, and aligned bar separators when present. This is alignment evidence, not duration evidence.
- `ascii-musicxml-alignment.v0.1` compares ASCII column evidence with MusicXML onsets in controlled public fixtures only. It can report compatible, partial, ambiguous, incompatible, or unavailable evidence, but it is a diagnostic proof sidecar, not a conversion engine.
- `ascii-scoreir-gate.v0.1` allows ScoreIR output only for one tiny controlled public ASCII/MusicXML proof shape. It is not general ASCII-tab conversion.
- The ASCII ScoreIR gate requires safe MusicXML timing, a compatible `ascii-musicxml-alignment.v0.1` sidecar, one-to-one candidate mappings, string/fret evidence from ASCII TabRaw, durations/rests from MusicXML, and no unsupported techniques, symbols, chords, polyphony, tuplets, ties, or grace notes.
- ASCII ScoreIR gate refusal is expected for most inputs. The diagnostic reason taxonomy distinguishes missing sidecars, unsafe alignment statuses, missing candidate mappings, missing string/fret evidence, unmapped measures/onsets, unsupported techniques/chord symbols, polyphony, MusicXML timing risk, missing duration evidence, and cases outside the tiny public gate.
- HTML diagnostics for ASCII gate refusal are developer-facing explanations. JSON diagnostics remain the programmatic source of truth. The HTML report does not imply broader ASCII-to-ScoreIR support, OCR, scanned-PDF support, or symbol/technique attachment, all of which remain strictly out of scope.
- Complete ASCII-tab blocks without usable bar separators produce `ascii_tab_timing_unavailable` and `ascii_tab_measure_boundary_missing`. Barred/equal-width examples currently produce `partial_ascii_tab_timing`, while uneven or inconsistent rows produce `ambiguous_ascii_tab_timing`. Incomplete ASCII-tab row grouping produces `partial_ascii_tab_grouping`.
- Grouped reports and overlays show what the extractor inferred; they do not mean the musical timing is trustworthy without MusicXML timing and x-to-onset diagnostics.
- X-to-onset diagnostics now measure playable fret x groups against MusicXML onset groups, but this is not full optical calibration and does not repair bad geometry automatically.
- MusicXML timing preflight catches overfull bars, same-voice/multi-voice overlap, unbalanced backup/forward cursor movements, duration anomalies, and divisions changes before ScoreIR output. It generates a developer-facing `musicxml-timing-diagnostics.html` report, but it does not make ambiguous Audiveris exports correct or loosen gates for unsafe inputs.
- MusicXML timing risk diagnostics are public-fixture driven, whereas private diagnostic smoke passes are for identifying failure classes. Unsafe or risky MusicXML strictly blocks ScoreIR. Polyphony and overlap support remains intentionally conservative.
- Native `.mxl` intake is supported only for normal compressed MusicXML packages with a safe rootfile declared in `META-INF/container.xml`; malformed packages and unsafe rootfile paths are rejected.
- 12/8 and other compound-meter input is represented through exact MusicXML divisions and flagged as an assumption; it still needs human review when produced by OMR.
- If PDF extraction finds fret text but no system/string/bar grouping, the project reports `missing_pdf_grouping` and `build-ir` refuses to write ScoreIR rather than fabricating positions.
- The grouping HTML report and overlay images make grouping success and failure inspectable; they do not solve arbitrary PDF grouping or make unstructured fret text safe to align.
- A `good` x-to-onset quality label only means the current simple alignment looks internally consistent for the inspected controlled input.
- `warning`, `poor`, or `unknown` x-to-onset quality means the conversion should be inspected before trusting any automatic result.
- Chord symbols and technique text are conservatively attached to existing, safely timed ScoreIR events and note techniques as metadata/evidence, but they cannot create notes, events, or timing. GPIF technique & chord rendering remains strictly out of scope.
- Developer-facing HTML report (`symbol-attachment-diagnostics.html`) provides a human-readable visualization of which candidates successfully attached and which remained unattached with warning codes. JSON diagnostics remain the programmatic source of truth.
- Candidate text near tab systems is preserved as non-playable evidence; it is not interpreted musically.
- Scanned PDFs require OCR/image recognition that is not complete in the first milestone.
- The generated PDF regressions demonstrate controlled born-digital PDF producer paths; they do not mean private or commercial scores will convert cleanly.
- Private diagnostic runs are evidence-gathering only. Their summaries report counts and quality buckets, not copyrighted score content, and private artifacts must stay under ignored paths.
- The private diagnostic smoke workflow (`scripts/private_e2e_smoke.py`) is an optional, local-only developer tool. It must never commit private files, private outputs, or private summaries to Git. All diagnostic outputs and master reports are placed in ignored `work/` subdirectories.
- Private examples used in the smoke workflow are purely diagnostic inputs, not regression fixtures. Failures are expected and useful to measure the pipeline's progress, and we must never weaken timing/validation gates or tune thresholds to make specific private examples pass.
- Public/synthetic fixtures remain the sole source of committed regression tests and CI validation.
- GPIF support is minimal and may not cover every Guitar Pro feature.
- Unsupported or uncertain notation must be reported in warnings and conversion reports.
- The public end-to-end PDF-to-GP proof (`tests/test_e2e_pdf_to_gp.py`) demonstrates pipeline correctness on a highly controlled, synthetic public ASCII-tab PDF and compatible MusicXML fixture. It does not prove or guarantee arbitrary commercial PDF conversion, OCR, scanned-PDF support, or general PDF-to-GP authoring.

This tool is for files the user owns or has permission to process. It must not be used to bypass DRM or copy protected scores from unauthorised sources.
