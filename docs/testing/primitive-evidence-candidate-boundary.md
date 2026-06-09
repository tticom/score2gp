# Primitive Evidence Candidate Boundary

## 1. Purpose
This document defines the data contracts and architectural boundaries between primitive-level geometric diagnostics and future candidate extraction layers.

## 2. Current baseline after PR #227
PR #227 (`feat(pdf): expose primitive-level geometry diagnostics`) successfully established the required diagnostics layer. Real serialized primitive-level bounds and metadata are now available, completely replacing the previous reliance on aggregate counts for potential candidate synthesis.

## 3. Source-of-truth diagnostics
The following objects and diagnostic outputs are the mandatory and only permitted source of truth for candidate definition and extraction:
* `StaffLeftMarginAggregateDiagnostics.evidence`
* `XAlignedClusterAggregateDiagnostics.evidence`
* `PrimitiveGeometryEvidence`
* `XAlignedPrimitiveClusterEvidence`

## 4. Allowed candidate boundary
Candidates mapped from primitive evidence must adhere strictly to geometry-only taxonomy. No functional or semantic labels are permitted. Permitted candidate concept names include:
* `PrimitiveEvidenceCandidate`
* `LeftMarginPrimitiveCandidate`
* `XAlignedPrimitiveClusterCandidate`
* `TextSpanPrimitiveCandidate`
* `CurvePrimitiveCandidate`
* `VerticalStrokePrimitiveCandidate`
* `HorizontalStrokePrimitiveCandidate`
* `DiagonalStrokePrimitiveCandidate`
* `RectanglePrimitiveCandidate`

## 5. Required provenance and data preservation
Any future candidate model instantiated from diagnostics must strictly preserve all of the following data without mutation:
* `page_index`
* `system_index`
* `staff_index`
* `x0`
* `y0`
* `x1`
* `y1`
* `kind`
* optional safe font metadata for text spans
* provenance: explicitly identifying whether the evidence originated from left-margin evidence or x-aligned cluster evidence
* source cluster membership where applicable

## 6. Forbidden semantics and forbidden inference
Any naming, schema field, or logic that attempts to imply musical functionality or extract candidates using pre-PR #227 inference is explicitly forbidden.

The following practices are explicitly forbidden:
* aggregate-count-derived candidates
* placeholder coordinates
* inferred plausible coordinates
* fake geometry
* semantic candidate names
* musical interpretation
* private PDF examples

Forbidden semantic terms for candidate boundaries (unless explicitly used to flag violations in testing): notehead, stem, clef, pitch, duration, voice, chord, key_signature, time_signature, beat, rhythm, ScoreIR.

## 7. Stop conditions
Implementation sequences must stop and flag for review if:
* Evidence arrays are missing, incomplete, or unreconciled with their parent aggregate counts.
* The correct action upon discovering missing evidence is to abort candidate tasks and create a prerequisite diagnostics task. Data must never be synthesized to bridge a gap.

## 8. Fixture and empirical proof required before extraction
Before proceeding to extractor implementations, tasks must provide robust validation demonstrating that candidate models can be successfully hydrated from real PR #227 diagnostics evidence arrays, and that no schema leakage has occurred.

## 9. Relationship to future tasks
This document binds subsequent candidate modelling tasks. Candidate structures must be defined, frozen, and structurally validated via an anti-semantic test gate before any active extraction operations are permitted.

## 10. Explicit non-approval of extraction
This specification defines boundaries only. It does not constitute approval to begin candidate extraction implementation, nor does it approve the integration of extractor functions into the product pipeline. Extractor operations remain pending subsequent governed tasks.
