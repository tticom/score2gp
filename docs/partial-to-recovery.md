# Design Note: PDF Layout Partial-to-Recovery Strategy

## Context

The `score2gp` pipeline adopts a highly conservative, diagnostic-first approach to PDF layout grouping. PDF-derived playable fret candidates are matched with MusicXML event structures only if they can be unambiguously assigned to a complete layout geometry: a detected system, staff line, and a validated bar measure box.

Currently, any deviation from complete, fully-boxed layout structures results in immediate rejection at the `build-ir` compiler gate. If a system contains barlines but lacks constructible, closed bar boxes (for instance, when one of the enclosing barlines is missing or rejected under strict relative crossing rules), it triggers specific warning/refusal codes such as:
- `pdf_bar_box_one_boundary_rejected`: Triggered when a system has one validated boundary but its sister edge boundary is rejected or missing.
- `pdf_partial_grouping_one_system_unboxed`: Triggered when one or more staff systems on a page cannot be fully boxed.
- `pdf_bar_box_construction_not_enough_for_build_ir`: Blocks intermediate representation compilation due to incomplete measure boundaries.

Under the current strict gate policy, these partial structures are categorized as `partial_pdf_grouping` or `missing_pdf_grouping` and fail immediately. While this guarantees absolute safety, visual inspection often shows that these cases represent highly structured born-digital layouts where only a single outer boundary is missing, or an edge boundary fallback was rejected due to strict vertical margins.

This document outlines the proposed strategy, structural constraints, and public fixture requirements for any future automatic grouping recovery.

---

## Proposed Boundaries for "Safe" Recovery

Any future automatic recovery logic must operate under strict, highly constrained geometry boundaries. We define a recovery as "safe" only when the missing layout information is mathematically implied by the existing vector barlines and staff geometry with a near-zero probability of false positives.

### 1. Constrained Edge-Boundary Fallbacks
- **Definition**: Inferring a missing outer edge boundary (leftmost or rightmost system edge) only when:
  - Exactly one accepted internal/middle barline exists.
  - The system start (`x0`) and end (`x1`) points are cleanly defined by the horizontal staff vector lines.
  - The visual candidate distribution is strictly bounded within the inferred boundaries.
  - The distance between the accepted boundary and the staff edge matches standard spacing tolerances (within a tight threshold, e.g., $\ge 30.0$ points to avoid narrow/malformed measures).
- **Geometry Checks**: The edge-boundary must align perfectly with the staff ends (`x0` or `x1`) and be strictly vertical. No angled or skewed lines can be assumed.
- **Ambiguity Margins**: Fallback must be rejected if there are any rejected barlines, noise lines, or candidate text boxes residing near the inferred boundary coordinates (e.g. within an ambiguity margin of $0.45 \times$ line spacing).

### 2. Isolated Missing Internal Barlines (Strict Non-Guessing)
- Internal measures must **never** be divided or reconstructed by guessing or assuming a fixed beat width.
- However, if an internal barline is mathematically collinear with accepted barlines in adjacent vertical systems (e.g. system 1 and system 3 have aligned barlines, and system 2 is missing one due to text crossing), we can evaluate **collinear projection**.
- Collinear projection must only be allowed if:
  - The system spacing is perfectly uniform across the page.
  - No text candidate overlaps the projected line coordinates.
  - The candidate distribution on both sides of the projected boundary is clearly segregated with a wide empty horizontal channel.

---

## Strict Exclusions & Invariants (Scope Boundaries)

To prevent the pipeline from decaying into a guessing engine, the following practices are strictly excluded and must **never** be implemented:

1. **No Internal Barline Guessing**: We must never infer or place an internal barline based on "beat duration" or "even division" assumptions. Doing so would mask OMR structural issues and produce quiet timing drift.
2. **No MusicXML Pitch/Tuning Layout Inference**: MusicXML pitch data (e.g., standard tuning `EADGBE`) must **never** be used to assign PDF candidate fret text to strings or barlines. The PDF geometry matching must remain purely spatial. Bypassing spatial gates using pitch hints violates the architectural separation of concerns.
3. **No OCR or Scanned-PDF Support**: The automatic recovery must rely exclusively on vector drawing primitives and born-digital text blocks. Guessing layouts on rasterized/scanned PDFs is blocked.
4. **No ML Layout Recognition**: The recovery rules must be transparent, deterministic, and inspectable. Black-box ML layout predictions are explicitly out of scope.

---

## Public Fixture Strategy & Invariants

Any implementation of layout recovery logic must strictly adhere to a **public fixture-first development workflow**:

1. **Synthetic Public Fixtures**: Before writing a single line of recovery code, a synthetic born-digital PDF fixture representing the failure mode must be generated and committed under `tests/fixtures/pdf/`.
2. **Regression Assertions**: We must write failing tests demonstrating that without the recovery logic, the compiler correctly refuses the fixture, and that with the recovery logic enabled, the compiler recovers the grouping safely.
3. **Pre-recovery Warning Preservation**: The recovered output must still write the warning/remediation codes to the diagnostics sidecar to ensure developers can inspect that a recovery took place. A recovered state must be clearly demarcated from an natively perfect state (e.g. `grouping_status = "recovered"`).
4. **Private-Safety Isolation**: No private files or local OMR sheets may be used for testing the recovery heuristics. The implementation must be proven 100% using the public synthetic test suite.
