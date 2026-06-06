# Input Requirements

This document outlines the strict structural and geometric requirements for input files to ensure successful processing by the `score2gp` pipeline.

## PDF Requirements

The extraction engine relies on vector geometry and text elements embedded directly in digital PDF files.

### 1. Vector and Selectable Text Layer
* The PDF must be **born-digital** (exported directly from notation software like MuseScore, Sibelius, or Guitar Pro).
* It must contain selectable text elements representing fret numbers, chord symbols, and technique text, rather than flat image pixels.
* Barlines and staff lines must be vector path drawing primitives (lines/rectangles), not rasterized lines.

### 2. Recoverable TAB Systems
* The page must feature six near-horizontal vector staff lines grouped vertically to define a tab system staff.
* Systems must not vertically interleave or overlap.

### 3. Recoverable String Lines and Measure Structure
* Vertical vector paths representing barlines must cross the tab staff completely to form closed measure boundaries.
* Fret digit text must Snug-Fit within measure boxes and align closely (vertically) with one of the six staff lines to be mapped to a specific string.

### 4. No Scanned or Raster Image Support
* Scanned sheets, photos of scores, or PDFs composed purely of image layers are unsupported. The tool does not perform image-based OCR or line-detection on raster grids.

---

## MusicXML Requirements

The MusicXML sidecar serves as the source of truth for the musical rhythm, measures, voices, and standard notation elements.

### 1. Structure Matching
* The bar/measure count and order of the MusicXML sidecar must align exactly with the system/measure boundaries of the PDF score.
* The number of parts and staff layouts must correspond to the PDF track being processed.

### 2. Clean Timing and voice-timelines
* Active voice timelines must be mathematically consistent. The sum of note and rest durations in each voice must exactly match the measure's time signature duration.
* No duration overlaps are permitted within a single voice timeline.
* No cross-voice timing overlaps are allowed (ScoreIR polyphony gate restricts conflicting multi-voice overlapping events in the same track).

### 3. Guitar Technical Data
* Guitar-specific pitch information, tuning details, and string/fret details (for tab voices) must be correctly specified in the XML.

### 4. Ornaments, Tuplets, and Grace Notes
* **Grace Notes**: Supports pitched grace notes preceding host notes. TAB-voice grace notes containing string/fret data are merged into standard notation grace notes.
* **Tuplets**: Supports standard triplets as well as preflight validation for quadruplets (4:3) and quintuplets (5:3).

---

## Unsupported Inputs and Safe Refusals

If an input does not meet the criteria, the pipeline safely refuses to generate a `ScoreIR` model:
* **Scanned/Raster PDFs**: Lack vector paths and text layers.
* **ASCII Tab without Alignment**: ASCII character grids lack musical timing. They are blocked unless accompanied by an explicit `ascii_musicxml_alignment.json` sidecar.
* **Drawn/Vector Tab without MusicXML**: Drawn vector tab contains fret numbers and string layout but lacks duration/timing information. A matching MusicXML sidecar is always required to compile the notes into timed measures.
* **Missing or Malformed Sidecar**: If the sidecar is absent, or fails timing preflight, the conversion is halted.
