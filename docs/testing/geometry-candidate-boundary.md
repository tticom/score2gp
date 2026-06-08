# Geometry Candidate Boundary

The `PdfStaffNotationGeometryDiagnostics` system sits at the lowest level of extraction. Its responsibility is to represent raw geometry directly pulled from the PDF instructions, filtered only by basic spatial relationship to the detected staff lines. 

It does **not** interpret the musical meaning of these primitives.

## Why Musical Names are Deferred
Musical names (like `Notehead`, `Stem`, `Clef`) are explicitly deferred because predicting musical semantics from raw geometry is context-dependent and error-prone at the lowest parsing layer. By forcing a strict boundary between geometry extraction and semantic interpretation, the system ensures that parsing logic remains stable and decoupled from the complexities of musical notation rules. If a `CircularMarkerCandidate` is incorrectly reconstructed as a notehead instead of a staccato dot, the semantic reconstruction layer fails—but the underlying parsing layer remains correct.

## Allowed Geometry Candidate Terms
When referencing geometry extracted by this system, only terms that describe physical shapes without assuming musical function may be used. The allowed candidate terms are:
* `CircularMarkerCandidate`: Represents roughly circular shapes, which may later become noteheads, dots, or ornaments.
* `VerticalStrokeCandidate`: Represents tall, narrow lines or rectangles, which may later become stems or barlines.
* `HorizontalStrokeCandidate`: Represents wide, short lines or rectangles, which may later become ledger lines or beams.
* `CurveMarkerCandidate`: Represents bezier curves, which may later become slurs, ties, or parts of clefs/rests.
* `RectangleMarkerCandidate`: Represents generic rectangular regions.
* `TextMarkerCandidate`: Represents a span of rendered text.
* `XAlignedPrimitiveCluster`: Represents a group of primitive geometry aligned roughly along the same X coordinate.

## Required Diagnostics Fields
The diagnostic data structures (such as `NotationStaffMorphology` and `XAlignedClusterAggregateDiagnostics`) map primitives to geometry candidates using strict spatial and dimensional checks. The required diagnostics fields are:
* `circle_candidate` / `circle_candidates_total`
* `vertical_stroke_candidate` / `vertical_stroke_candidates_total`
* `horizontal_stroke_candidate` / `horizontal_stroke_candidates_total`
* `curve_candidate` / `curve_candidate_count`
* `rectangle_candidate` / `rectangle_candidate_count`
* `text_span_by_font` / `text_span_count`

## Explicitly Forbidden Semantic Terms
The diagnostic layer must never emit models, fields, or labels that assume musical function. The following semantic terms are explicitly forbidden in the notation geometry output layer:
* `NoteheadCandidate`
* `StemCandidate`
* `ClefCandidate`
* `PitchCandidate`
* `DurationCandidate`
* `VoiceCandidate`
* `ChordCandidate`

Any logic that assigns these semantic labels belongs in higher-level reconstruction systems, not in the lowest diagnostic layer.
