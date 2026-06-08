# Staff Geometry Diagnostics Glossary

This document outlines the geometric diagnostic fields exported by `PdfStaffNotationGeometryDiagnostics`. These fields provide structural layout data for standard staves before any musical semantics are assigned.

## Strictly Geometric Meaning
These fields describe bounding boxes, structural counts, and positional groupings of shapes (like curves, rectangles, horizontal, and vertical strokes). 
**Important**: You must not use these fields to infer musical semantics yet. None of these fields represent or imply any of the following forbidden concepts:
- Musical tones or frequencies
- Musical timing values or fractions
- Initial staff marker symbols indicating register
- Margin symbols indicating accidental sets
- Rhythmic grouping constraints

## Fields

### staves
A list containing `NotationStaffDiagnostics` objects, one for each staff found on the page.

### staff
A `NotationStaffGeometry` object.
**Meaning**: The geometric bounding box and basic horizontal line coordinates for the current staff.

### primitives
A `LocalPrimitivesSummary` object.
**Meaning**: Raw geometric shape counts strictly within the staff bounding box.
**Fixture Example**: In `sparse`, counts are zero. In `dense-margin`, text spans and curves are highly populated.

### morphology
A `NotationStaffMorphology` object.
**Meaning**: Initial morphological classification of shapes into strokes, rectangles, or curves, before any clustering occurs.

### clustering
An `XAlignedClusterAggregateDiagnostics` object.
**Meaning**: Geometric statistics for vertically aligned clusters of shapes (e.g. circular markers grouped with vertical strokes). This layer does not assign semantic meaning, only spatial grouping.
**Fields included**:
- `x_aligned_cluster_count`: Number of vertically aligned groups found.
- `max_primitives_per_x_aligned_cluster`: The maximum number of individual shapes in any single vertically aligned group. (e.g., in `complex-cluster`, this is >= 4).
- `cluster_primitive_count_summary`: Summary of all shapes contained within any vertically aligned cluster.

### left_margin
A `StaffLeftMarginAggregateDiagnostics` object.
**Meaning**: Diagnostics for shapes falling within the extreme left margin of the staff, typically used for initial margin marker shapes.
**Fields included**:
- `text_span_count`: The number of text blocks found in the left margin.
- `curve_candidate_count`: The number of curved shapes found in the left margin.
- `vertical_stroke_candidate_count`: The number of vertical strokes found in the left margin.
- `rectangle_candidate_count`: The number of rectangular blocks found in the left margin.

## Schema Snapshot
The schema for these diagnostics is tracked in `fixtures/public/pdf_staff_geometry_diagnostics_schema.json`.
A snapshot test asserts that this schema does not drift or unintentionally leak semantic names. 

**How to update the schema snapshot intentionally:**
If you make an approved geometric addition to the schema, you must intentionally update the snapshot by running the helper script (available once Task 8 / PR #204 is merged):
```bash
python tests/fixtures/pdf/make_pdf_staff_geometry_schema_snapshot.py
```
