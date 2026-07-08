# Logical Clef Recognition Research

**Date**: 2026-07-08
**Author**: Architect
**Status**: PROPOSAL

## 1. Context

In Req-112, we implemented the Semantic Boundary Validation Gate (`SemanticGateResult`), which confirms the presence of a logical clef candidate from `left_margin_primitives` but safely fails closed to `clef_kind: "unknown"`.

The goal of Req-113 is to research and propose how to transition this `unknown` state into a concrete clef classification (e.g., Treble, Bass) using available evidence, without prematurely building optical character recognition (OCR) or modifying the underlying PDF geometry models.

## 2. Available Evidence

The `GeometryCandidateSet` currently exports:
- `x0, y0, x1, y1` bounding boxes for primitives.
- primitive `kind` (`text_span`, `curve`, `vertical_stroke`, etc.).
- `font_name` and `font_size` (for `text_span`).

Crucially, **text character payloads (e.g., 'G' or '&') are not currently exposed** in the diagnostic extraction layer.

## 3. Analysis of Classification Options

### Option A: Extract Text Characters (Not Recommended Yet)
- **Mechanism**: Modify the PDF parser to expose the exact UTF-8 character payload of `text_span` primitives. We could then map specific characters in known fonts (e.g., Sonata `&`) to specific clefs.
- **Risk**: Extremely high. PDF text extraction is notoriously brittle. Font mappings (CMAP tables) are often missing or obfuscated in engraved PDFs. Relying on text payloads would break backward compatibility and introduce a massive OCR/font-parsing scope creep.

### Option B: Bounding Box Proportional Heuristics (Recommended)
- **Mechanism**: Classify clefs based on their physical bounding box dimensions relative to the staff lines (staff height and staff space).
- **Evidence**: 
  - **Treble Clef**: Known to be very tall. Its bounding box height relative to a single staff space (`height_to_spacing`) is typically `> 3.5`. Its height relative to the full staff (`height_to_staff_height`) is `> 1.2`.
  - **Bass Clef**: Shorter and more compact. It typically spans the upper 3.5 spaces of the staff, but rarely exceeds `height_to_staff_height == 1.0`. It is also often accompanied by two distinct dots (often small `curve` or `text_span` elements) to the right.
- **Risk**: Low. Bounding boxes are stable across all rendering engines.

## 4. Proposal

We propose implementing **Option B (Bounding Box Proportional Heuristics)**.

1. **Integration**: The existing `logical_clef_candidate_classifier.py` already contains a foundational heuristic function (`classify_logical_clef_candidate`) that correctly identifies Treble Clefs based on height and width ratios.
2. **Next Steps for Developer**:
   - Integrate `classify_logical_clef_candidate` into `evaluate_logical_clef_gate`.
   - The gate should pass the `left_margin_primitives` and staff geometry (spacing, height) to the classifier.
   - If the classifier returns `treble_clef_candidate`, map this to `clef_kind="treble"`.
   - If the classifier returns `unknown`, map this to `clef_kind="unknown"`.
   - (Optional/Later) Extend the classifier with Bass Clef heuristics.
   
## 5. Explicitly Deferred

- Bass Clef heuristics can be deferred if `dense_margin` and `sparse` fixtures only contain Treble Clefs.
- We will not attempt to read the text character payload.
- We will not attempt to map pitches yet.

## 6. Acceptance Criteria (For Implementation)
1. `evaluate_logical_clef_gate` must correctly return `clef_kind="treble"` for the `dense_margin` fixture.
2. The gate must safely fail closed to `clef_kind="unknown"` if the dimensions do not match the treble heuristic.
3. No product code outside of the semantic gate layer may be modified.
