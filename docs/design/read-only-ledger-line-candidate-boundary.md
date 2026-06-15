# Design: Read-Only Ledger-Line Candidate Boundary

**Task:** Product Task 161
**Date:** 2026-06-15

## Context
Product Task 160 successfully introduced an explicit opt-in `--assume-treble-clef` pitch mapping for read-only note candidates. This mapping safely omitted pitches for `staff_position_index` values less than 0 or greater than 8, effectively limiting pitch recognition to natural notes on the five-line staff.

To support pitch inference for notes outside the staff, we must eventually extract ledger lines and map them. This discovery task identifies how ledger lines exist within the raster diagnostic output, if and how they can be semantically attached to note candidates, and proposes a design for a `ledger_line_candidate` output boundary.

## Inspection Record
**Files Inspected:**
- `src/score2gp/pdf_raster_staff_diagnostics.py`
- `src/score2gp/pdf_staff_notation_diagnostics.py`
- `src/score2gp/pdf_staff_geometry.py`
- `src/score2gp/pdf_geometry_candidates.py`
- `src/score2gp/whole_note_recogniser.py`
- `tests/fixtures/pdf/make_standard_staff_diagnostics_pdfs.py`
- `fixtures/public/generated_standard_staff_complex_cluster.json`

**Commands Run:**
- `grep -rin "primitive" src/score2gp/`
- `grep -rn "ledger" src tests scripts`
- `grep -n -B2 -A5 "horizontal_stroke" src/score2gp/pdf_staff_notation_diagnostics.py`

## Current Evidence

1. **Existence in Diagnostics:** Current diagnostics *do* expose ledger lines. They are classified as `non_staff_horizontal` during morphology classification and are serialized as `horizontal_stroke` primitives within `XAlignedPrimitiveClusterEvidence`.
2. **Filtering:** Ledger lines are not filtered out. They successfully make it to the `x_aligned_cluster_candidate` outcomes.
3. **Representation:** They are currently available as raw `horizontal_stroke` primitives within `x_aligned_cluster_candidates` (alongside notehead rects and vertical stem strokes).
4. **Association:** They are implicitly associated with `page_index`, `system_index`, and `staff_index` via their parent cluster. They are **not** explicitly associated with `note_candidate` outcomes.
5. **Distinguishability:** Ledger lines are available as candidate evidence but are ambiguous with beam-like horizontal strokes until disambiguated. Current `non_staff_horizontal` primitives have two exposure paths:
   - `horizontal_stroke` evidence inside `x_aligned_cluster_candidate`;
   - `beam_candidate` through `flag_beam_candidates` when the stroke is wide enough.
6. **Fixture Support:** Current public fixtures (e.g., `generated_standard_staff_complex_cluster.json`) contain primitives that represent ledger lines above the staff. Additional fixtures will be needed for multiple stacked ledger lines.

## Recommended Boundary Shape

Ledger lines should be represented as standalone **generic read-only candidates**, with optional references to associated note candidates. A standalone entity prevents tightly coupling the semantic pipeline at the diagnostic boundary, allowing future tasks to calculate overlapping geometries before inferring pitch.

**Proposed Schema:**
```json
{
  "candidate_id": "ledger_line_candidate_001",
  "symbol_type": "ledger_line_candidate",
  "page_index": 1,
  "system_index": 1,
  "staff_index": 1,
  "bbox": [298.0, 94.0, 310.0, 94.0],
  "source": "diagnostic_candidate_evidence",
  "associated_note_candidate_ids": ["whole_note_candidate_001"] // Optional
}
```

*Note: `staff_position_index` and `ledger_line_role` are omitted from the boundary design, as calculating them requires inferring semantics that violate the fail-closed boundary of this component.*

## Proposed Fail-Closed Behaviour
* Do not emit `ledger_line_candidate` if a `horizontal_stroke` is suspiciously wide, thick, or does not horizontally overlap with a known notehead primitive.
* Ambiguous lines should remain as `x_aligned_cluster_candidate` primitives and not be promoted.
* **Beam Avoidance:** The implementation task must avoid double-emitting the same primitive as both `beam_candidate` and `ledger_line_candidate`. The recommended approach is to suppress matching beam candidates when a stroke is successfully promoted to `ledger_line_candidate`, or classify/reclassify the horizontal primitive before beam shaping.

## Fixtures Needed for Implementation
A new `generated_standard_staff_ledger_lines.json` fixture is required to test stacked ledger lines above and below the staff, ensuring bounding boxes are accurately reported and separated from standard staff lines.

## Known Limitations and Risks
* **Grouping Complexity:** Multiple notes sharing the same ledger line (e.g., chords) will require many-to-one mapping in `associated_note_candidate_ids`. 
* **Noise:** Fret numbers or textual lines might be misidentified as `horizontal_stroke` primitives in some noisy PDFs.

## Non-Goals Confirmed
This task strictly adhered to the design and discovery boundary.
* No ledger-line extraction was implemented.
* No pitch mapping, assumed-treble mapping, or generic pitch inference was changed.
* No ScoreIR, MusicXML, Guitar Pro output, rests, or clef inferences were added.
* No new fixtures or artifacts were generated or committed.

## Recommended Next Task
**Product Task 162 — Implement read-only ledger-line candidate extraction**

### Full Self-Contained Prompt for Product Task 162

```markdown
Title: Product Task 162 — Implement read-only ledger-line candidate extraction

Context:
You are the product agent working in `tticom/score2gp`.
Product Task 161 discovered that ledger lines are currently represented as `horizontal_stroke` primitives inside `x_aligned_cluster_candidate` outcomes. 
The design document `docs/design/read-only-ledger-line-candidate-boundary.md` outlines a standalone `ledger_line_candidate` output boundary.

Goal:
Implement `ledger_line_candidate` extraction from diagnostic evidence and emit it in the read-only recognition report.

Scope:
- Work in `tticom/score2gp`.
- Create a new public fixture with stacked ledger lines (e.g. `generated_standard_staff_ledger_lines.pdf/json`).
- Update the candidate shaping logic in `src/score2gp/whole_note_recogniser.py` to identify `horizontal_stroke` primitives inside note clusters and emit them as `ledger_line_candidate` objects.
- Ensure the implementation avoids double-emitting the same primitive as both `beam_candidate` and `ledger_line_candidate` (e.g. by duplicate suppression or reclassification against existing `beam_candidate` output).
- Use the schema defined in `docs/design/read-only-ledger-line-candidate-boundary.md`.
- `associated_note_candidate_ids` is optional.
- Ensure the reporting script `scripts/note_candidate_recognition_report.py` correctly passes through the new candidate.
- Add tests to `tests/test_note_candidate_recognition_report.py` proving ledger lines are successfully emitted.
- Add tests proving a ledger-line primitive is not also emitted as a beam candidate.
- Add tests proving eighth-note composition is not changed by ledger-line promotion.

Fail-Closed Rules:
- If a horizontal stroke does not overlap with a notehead or stem, do not emit it as a ledger line.
- Do NOT implement pitch inference.
- Do NOT alter `staff_position_index` logic.
- Do NOT emit ScoreIR, MusicXML, or GP output.
- Do NOT commit private fixtures, diagnostic dumps, or logs.
```
