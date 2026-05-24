# Design Note: PDF Layout Unboxed System Recovery and Skipping Strategy

## Context

During visual grouping and layout construction, `score2gp` processes the tab staff systems on each page. A staff system is considered "fully boxed" only when all of its measure boundaries (bar boxes) can be successfully constructed using validated vertical barlines.

However, in certain born-digital scores, a system may be safely detected but lack any internal or external vertical barlines (e.g., a solo system or a free-form section). Under strict gates, this results in the entire score being rejected because of the following warning/refusal codes (discovered in private smoke E2E testing):
- `pdf_barlines_not_detected_in_system`: Triggered when no vertical barlines are detected within the horizontal span of a detected staff system.
- `pdf_bar_boxes_not_constructible`: Triggered when the builder cannot form complete, enclosed measure boundary boxes.
- `pdf_bar_detection_not_enough_for_build_ir`: Blocks `build-ir` compilation because the measure geometry is incomplete.
- `pdf_candidate_unassigned_due_to_unboxed_system`: Fret digit candidates inside the system are dropped or flagged as unassigned.
- `pdf_partial_grouping_one_system_unboxed`: Blocks compiler progression at the page-level layout safety gate because at least one detected system is unboxed.

To address these scenarios without compromising our core safety guarantees or introducing noisy layout heuristics, we propose two distinct paths: **Single-Measure System Recovery** and **Opt-In System-Skipping Compiler Progression**.

---

## Proposed Strategies

### 1. Single-Measure System-Wide Recovery (Zero-Barline Fallback)
When a system is completely unboxed but clearly forms a valid, contiguous musical section:
- **Heuristic**: If **exactly zero barlines** are detected or validated in a system, but a valid staff box is detected and contains playable candidate fret text, we can infer a **single system-wide bar box** using the staff's own bounding box coordinates:
  - Left boundary ($x_0$): Bounded by the left end of the horizontal staff lines.
  - Right boundary ($x_1$): Bounded by the right end of the horizontal staff lines.
  - Top and Bottom ($y_0, y_1$): Bounded by the vertical limits of the staff lines.
- **Strict Bounds**:
  - This recovery is active **only** if the total number of detected barlines in the system is exactly $0$. If there is even a single barline (e.g., a starting line or an end double-bar), this fallback is rejected to avoid overlapping/malformed measure definitions.
  - The system-wide measure must span at least a minimum reasonable width (e.g., $width \ge 100.0$ points) to be considered stable.
  - All fret text candidates residing within the staff's bounding box are assigned to this single recovered measure.
- **Diagnostics**: The resulting `warnings.json` sidecar must flag this with `pdf_system_recovered_as_single_measure` to ensure full inspectability.

### 2. Opt-In System-Skipping Compiler Progression
In cases where a system lacks barlines and cannot be safely boxed or recovered, we propose an opt-in compiler argument `--allow-skip-unboxed-systems` (or similar parameter `allow_skip_unboxed: bool = False`):
- **Behavior**:
  - When enabled, `build_ir` will cleanly skip any unboxed systems instead of aborting the compilation with a `BuildIrInputRiskError`.
  - Playable fret candidates inside the skipped system are discarded from the output `ScoreIR`.
  - The compiler outputs valid `ScoreIR` compiled solely from the remaining fully-boxed and safe measures on the page.
- **Safety Gate**:
  - The skipped systems must be explicitly logged in the diagnostics report sidecar with the warning `pdf_system_skipped_unboxed`.
  - A summary status (e.g., `skipped_system_count`) must be reported in the output JSON metadata.

---

## Strict Exclusions & Invariants

To keep the pipeline robust, deterministic, and free of guessing, the following limitations are strictly enforced:

1. **No MusicXML Timing Slicing**: We must **never** slice an unboxed system into multiple measures by using the durations or barlines in the MusicXML score. Slicing the PDF geometry based on the MusicXML's time signature/bar structures violates the spatial independence of the layout engine. The PDF geometry matching must remain purely layout-driven.
2. **No Guessing Missing Internal Barlines**: If a system has $N \ge 1$ barlines but lacks others, we must **never** partition the empty space into equal portions based on average measure widths or signature expectations.
3. **No String/Fret Ambiguity Bypassing**: Recovery of a system's bar boundaries does not waive string assignment constraints. Every fret candidate within the recovered measure must still cleanly map to a horizontal staff line using spatial margins.

---

## Public Fixture Strategy

Any implementation of the unboxed system recovery or system-skipping progression must follow the **public fixture-first development workflow**:

1. **Synthetic Public Fixture**: Before any code modification, generate a synthetic born-digital PDF fixture representing a score with an unboxed staff system (e.g., `tests/fixtures/pdf/generated_unboxed_system.pdf`) and commit it.
2. **Failing Baseline**: Write tests proving that without recovery/skipping active, compilation fails with `pdf_partial_grouping_one_system_unboxed`.
3. **Passing Verification**: Show that:
  - Enabling the single-measure recovery compiles successfully into a single-measure `ScoreIR` block.
  - Enabling the skipping progression compiles successfully into a `ScoreIR` block containing only the remaining boxed measures.
4. **Warning Integrity**: Ensure the appropriate warnings (`pdf_system_recovered_as_single_measure` or `pdf_system_skipped_unboxed`) are written to the output diagnostics sidecars.
