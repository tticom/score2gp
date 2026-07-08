# Semantic Interpretation Boundary Research

**Date**: 2026-07-08
**Author**: Architect
**Status**: PROPOSAL

## 1. Context and Objective

With the completion of Epic B (Geometry Candidate Extraction), `Score2GP` now successfully produces isolated geometric candidates (`left_margin_primitives` and `x_aligned_clusters`) in the `GeometryCandidateSet` payload without inferring musical semantics. 

The objective of this research document is to define the **smallest safe semantic interpretation boundary** that can be attempted next (Epic C), ensuring we do not over-extend into complex multi-variable inferences (like pitch or rhythm) prematurely.

## 2. Geometric Evidence (Fact)

An analysis of the exported `GeometryCandidateSet` across our four standard-staff public fixtures reveals the following facts:

1. **Left Margin Primitives**:
   - The left margin bounding box successfully isolates primitives that occur before the first rhythmic note cluster.
   - Identified primitive kinds include `vertical_stroke`, `text_span`, and `curve`.
   - `dense_margin` contains 7 left margin primitives, whereas `sparse` and `complex_cluster` contain only 1.
2. **X-Aligned Clusters**:
   - The staff body successfully isolates horizontal clusters of overlapping primitives.
   - Identified primitive kinds include `vertical_stroke`, `text_span`, `curve`, `rectangle`, and `horizontal_stroke`.
   - These clusters represent complex polyphonic events, rests, and bar lines.

## 3. Analysis and Hypothesis

**Hypothesis**: The safest, most isolated first semantic unit to extract is the **Logical Clef**.

**Inference/Reasoning**:
- **Geometrically Isolated**: Clefs consistently appear in the `left_margin_primitives` region, physically separated from the dense, high-variance `x_aligned_clusters`.
- **Structurally Foundational**: Pitch inference (a deferred capability) is mathematically impossible without first establishing an anchored clef. Extracting the clef first builds the necessary context layer for later pitch tasks.
- **Low Variance**: Clefs are typically represented as well-known `text_span` characters (e.g., standard music fonts) or consistent bounding box `curve` profiles.

**Unknowns**:
- Whether all treble and bass clefs across our target corpora map to stable, predictable `text_span` characters or if OCR-style curve heuristics will be immediately necessary.

## 4. Proposal: Smallest Safe Semantic Unit

We recommend proceeding with **Logical Clef Recognition** as the first semantic interpretation task.

- **Semantic Unit**: `LogicalClef` (e.g., Treble, Bass).
- **Valid Inputs**: `GeometryCandidateSet.staves[i].left_margin_primitives`
- **Proving Fixtures**: 
  - `generated_standard_staff_dense_margin.json`
  - `generated_standard_staff_sparse.json`
  - `generated_standard_staff_wide_curves.json`
  - `generated_standard_staff_complex_cluster.json`

## 5. Explicitly Deferred Semantics

To maintain strict boundaries, the following semantics must remain **explicitly deferred** during the next implementation phase:
- **Pitch Inference**: No staff-line y-coordinate mapping to MIDI pitches.
- **Rhythm / Duration**: No stem/flag/notehead aggregation for time values.
- **Other Left-Margin Symbols**: Key signatures and time signatures must remain un-interpreted.
- **Rests**: Quarter rests and whole rests in `x_aligned_clusters` must remain un-interpreted.

## 6. Gates and Acceptance Criteria

### Continue / Stop / Pivot Gates
- **CONTINUE**: If the developer can map `text_span` or `curve` primitives from `left_margin_primitives` to a semantic `LogicalClef` class with >90% reliability on public standard-staff fixtures.
- **STOP/PIVOT**: If the left margin primitives do not reliably contain the clef due to upstream bounding-box truncation, we must pivot back to refining the `left_margin` extraction heuristics in Epic B before attempting semantic interpretation.

### Measurable Acceptance Criteria (For Developer)
1. A new Pydantic schema model (`LogicalClefCandidate` or similar) is defined.
2. A new processing step maps `left_margin_primitives` to this schema.
3. The original `GeometryCandidateSet` remains structurally unchanged (the clef is added as a new independent output layer, e.g., `SemanticCandidateSet`).
4. Unit tests prove the clef is correctly identified in the `dense_margin` and `sparse` fixtures.

## 7. Required Validation Commands

Any subsequent Developer task implementing this proposal must pass the following checks before merging:

```bash
# Verify no product code broke existing tests
.venv/bin/python -m pytest

# Verify schema snapshots remain backward compatible
.venv/bin/python scripts/make_pdf_staff_geometry_schema_snapshot.py
git diff --check -- fixtures/public/

# Verify no private/copyrighted data leaked
.venv/bin/python scripts/artifact_audit.py
```

## 8. Conclusion

The geometry candidate layer provides sufficient, stable evidence to support a **Logical Clef** extraction as the first semantic boundary. It is recommended to authorize the Developer to implement the semantic boundary validation gate (Req-112) and logical clef recognition (Req-113) tasks based on this proposal.
