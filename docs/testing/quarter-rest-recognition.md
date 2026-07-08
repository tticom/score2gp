# Quarter Rest Recognition Research

**Date**: 2026-07-08
**Author**: Architect
**Status**: PROPOSAL

## 1. Context

Following the successful implementation of the logical clef semantic boundary, we turn our attention to the staff body. The quarter rest (crotchet rest) is a standalone symbol that sits centrally within the staff, making it a prime candidate for geometric classification without relying on full pitch or rhythmic context. 

The goal of Req-114 is to propose a method for extracting quarter rests from the existing `XAlignedPrimitiveClusterCandidate` items.

## 2. Available Evidence

The `GeometryCandidateSet` now provides `x_aligned_clusters`, which groups primitives by their horizontal overlap. 
Each `XAlignedPrimitiveClusterCandidate` contains:
- The total bounding box (`x0`, `x1`) of the cluster.
- The `primitive_count`.
- The list of `primitives` inside the cluster, each with its `x0, y0, x1, y1` bounding box and `kind` (`text_span`, `curve`, `vertical_stroke`, etc.).

## 3. Analysis of Quarter Rest Geometry

Quarter rests in standard notation are distinct because:
1. **Isolation**: They do not share their horizontal space with noteheads or stems (unless in complex polyphony, which is deferred). They usually appear in an isolated `x_aligned_cluster`.
2. **Composition**: Depending on the rendering engine/font, a quarter rest is usually rendered as a single `text_span` (if a music font is used) or a single complex `curve`. Sometimes it may be approximated by a `vertical_stroke`.
3. **Proportions**: A quarter rest is tall and narrow. It typically spans from roughly the top staff space to the bottom staff space. Its height is approximately 2.5 to 3.5 staff spaces.
4. **Vertical Position**: It is vertically centered on the staff. The vertical midpoint of the quarter rest bounding box is very close to the vertical midpoint of the staff itself.

## 4. Proposal

We propose using a **Bounding Box Heuristic Filter** on `x_aligned_clusters` to identify quarter rests.

### Heuristic Rules:
To classify an `XAlignedPrimitiveClusterCandidate` as a quarter rest, the following conditions must be met:
1. **Purity**: The cluster should ideally contain a single dominant primitive (e.g., `primitive_count == 1` and `kind` is `text_span` or `curve`). If multiple primitives exist, their bounding box union must still match the rest profile, and no obvious noteheads (`rectangle` or `ellipse` if we had them) should be present. For the initial implementation, strict isolation (`primitive_count == 1`) is safest.
2. **Height Ratio**: The primitive's height (`y1 - y0`) divided by the `staff_spacing` must be between `2.0` and `4.0`.
3. **Aspect Ratio**: The primitive's height divided by its width (`x1 - x0`) must be `> 1.5` (it is taller than it is wide).
4. **Vertical Centering**: The vertical midpoint of the primitive (`(y0 + y1) / 2`) must be within `0.5` staff spaces of the staff's vertical midpoint.

### Extraction Layer:
- Create a new module (e.g. `src/score2gp/pdf_candidate_quarter_rest.py`).
- Implement `extract_quarter_rest_candidates(geometry: GeometryCandidateSet, staff_spacing, staff_center_y) -> list[QuarterRestCandidate]`.
- The output should be a strictly typed `QuarterRestCandidate` (with fields for bounding box and reference to the original cluster).

## 5. Explicitly Deferred

- Polyphonic overlapping (e.g., a quarter rest clustered with a note from another voice).
- Multi-measure rests or other rest durations (eighth, half, whole).
- Exact semantic timestamping (this is just candidate extraction, not ScoreIR generation).

## 6. Acceptance Criteria (For Implementation)
1. A new `QuarterRestCandidate` model is defined without inferring pitch or full ScoreIR.
2. A synthetic fixture containing a quarter rest must be added or identified to test the heuristic.
3. The extraction function must successfully return the candidate for the quarter rest and ignore standard notes and barlines.
