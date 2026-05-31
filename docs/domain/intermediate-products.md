# Intermediate Products in the score2gp Pipeline

This document defines the expected intermediate products, stage boundaries, and domain invariants of the `score2gp` conversion pipeline.

---

## Stage 1: PDF Evidence Extraction

*   **Stage Name:** PDF Evidence Extraction
*   **Producing Command / Function:** `score2gp inspect-pdf` / `score2gp.pdf.inspect_pdf()`
*   **Expected Input:** Source PDF score file (`.pdf`)
*   **Expected Output:** JSON representation of visual elements, coordinates, and extracted text blocks (`inspect_pdf.json`).
*   **Domain Invariants:**
    *   `Verified domain fact`: Extracted visual evidence must preserve exact coordinate ranges and spatial relation to source pages.
    *   `Project decision`: Coordinate bounds use standard PDF points (72 points per inch) from page origin.
*   **Validation Checks:**
    *   Page count is positive.
    *   Visual element boxes (x0, y0, x1, y1) are ordered correctly (x0 <= x1, y0 <= y1).
*   **Known Failure Modes:**
    *   Scanned raster-only PDFs with no text blocks or vector elements.
*   **Current Evidence:** verified via synthetic page filtering and PDF layout tests in `test_pdf.py`.
*   **Unresolved Questions:** how to handle non-standard embedded font encodings.

---

## Stage 2: Tablature Segment Extraction

*   **Stage Name:** Tablature Segment Extraction
*   **Producing Command / Function:** `score2gp extract-tab` / `score2gp.pdf.extract_tab()`
*   **Expected Input:** Source PDF score file (`.pdf`)
*   **Expected Output:** A raw list of grouped character/symbol candidates and lines (`extracted.tabraw.json` or `tab_raw.json`).
*   **Domain Invariants:**
    *   `Verified domain fact`: A valid standard guitar tablature segment consists of exactly 6 horizontal line paths (representing the six strings).
    *   `Verified domain fact`: Numeric character sequences representing frets must be correctly parsed and associated with a specific line number.
*   **Validation Checks:**
    *   All tab candidates contain a parsed fret integer (0 to 24) or dead note representation.
    *   Candidate string number is within 1 to 6.
*   **Known Failure Modes:**
    *   OCR / text block reading concatenates consecutive fret numbers (e.g. reading 1 and 0 as separate instead of `10`).
*   **Current Evidence:** covered by candidate extraction tests in `test_tabraw.py`.
*   **Unresolved Questions:** how to resolve vertical alignments when system lines are warped.

---

## Stage 3: ASCII Tab to MusicXML Alignment

*   **Stage Name:** ASCII Tab to MusicXML Alignment
*   **Producing Command / Function:** `score2gp align-ascii-musicxml` / `score2gp.ascii_alignment.align_ascii_musicxml_files()`
*   **Expected Input:** TabRaw file (`extracted.tabraw.json`) + Ingested MusicXML file (`.musicxml` or `.xml`)
*   **Expected Output:** Diagnostic onset alignment compatibility mapping file (`ascii_musicxml_alignment.json`).
*   **Domain Invariants:**
    *   `Verified domain fact`: Events that occur at the same moment in time (simultaneous) must be assigned the same onset timestamp.
*   **Validation Checks:**
    *   Compatibility warning list is populated upon onset mismatches.
*   **Known Failure Modes:**
    *   Score timing drift where note onsets mismatch by small tick increments.
*   **Current Evidence:** covered by ASCII alignment tests in `test_ascii_alignment.py`.
*   **Unresolved Questions:** how to map multi-voice timing streams without explicit voice tags.

---

## Stage 4: ScoreIR Model Compilation

*   **Stage Name:** ScoreIR Model Compilation
*   **Producing Command / Function:** `score2gp build-ir` / `score2gp.build_ir.build_ir_with_diagnostics_from_files()`
*   **Expected Input:** MusicXML path + TabRaw path + (Optional) ASCII alignment path
*   **Expected Output:** Semantic ScoreIR model representation (`score.ir.json`).
*   **Domain Invariants:**
    *   `Verified domain fact`: Every note's physical sounding pitch must correspond exactly to standard string tuning pitch plus its fret value.
    *   `Verified domain fact`: A standard 6-string guitar in standard tuning can only play notes within `[E2, E6]` (MIDI 40 to 88).
    *   `Verified domain fact`: Measures cannot be overfull (exceeding time signature capacity).
*   **Validation Checks:**
    *   Pydantic schema validation.
    *   Pitch range validation checks (`ScoreIR.semantic_errors()`).
*   **Known Failure Modes:**
    *   Timing overlaps causing overfull voice bars.
*   **Current Evidence:** verified by pitch bounds and alignment tests in `test_ir.py` and `test_build_ir.py`.
*   **Unresolved Questions:** none.

---

## Stage 5: Guitar Pro Output Writing

*   **Stage Name:** Guitar Pro Output Writing
*   **Producing Command / Function:** `score2gp write-gp` / `score2gp.gp_package.write_gp()`
*   **Expected Input:** ScoreIR model (`score.ir.json`) + (Optional) template file (`.gp`)
*   **Expected Output:** Standard zip-compressed Guitar Pro-compatible package file (`smoke.gp` or `.gp`).
*   **Domain Invariants:**
    *   `Verified domain fact`: The written octaves displayed on the treble clef must be exactly 1 octave higher than sounding pitches (Octave-transposing Treble 8vb clef reality).
    *   `Project decision`: Flat relational GP8 database layout must match XML schema sequencing constraints to prevent application crashes.
*   **Validation Checks:**
    *   Guitar Pro zip package validation (`validate_gp()`).
    *   XML well-formedness and relational tag order sorting.
*   **Known Failure Modes:**
    *   Sequential parser rejection due to out-of-order relational elements under `<Score>`.
*   **Current Evidence:** covered by comprehensive packaging tests in `test_gp_writer.py`.
*   **Unresolved Questions:** none.
