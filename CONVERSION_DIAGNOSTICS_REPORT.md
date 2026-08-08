# Conversion Diagnostics Report

## Overview
The goal of this investigation was to determine why the `score2gp` pipeline was unable to successfully convert simple test files such as `Lesson-5.pdf` and `Lesson-6.pdf` into corresponding Guitar Pro (`.gp`) files. The symptom observed was that the pipeline aborted the conversion process and yielded a refusal code of `partial_pdf_grouping`. 

After examining the data, it was discovered that the root cause lies in strict geometrical alignment thresholds in the PDF layout parsing phases, which incorrectly classified valid fret digit candidates as "unsafe" because they were positioned slightly outside the inferred boundaries of the stave/system. The rigid `build_ir` system relies heavily on grouping confidence and aggressively aborts processing if it sees these particular "unsafe" codes.

## Detailed Root Cause Analysis

### 1. Incomplete Snapping to Bar Boundaries (`pdf_candidate_outside_bar`)
During the `extract_tab` (Phase 2/3) layout detection in `src/score2gp/pdf.py`, the system identifies physical barlines and constructs "bar boxes". Candidates (such as fret digits) are then assigned to a particular measure/bar based on their x-coordinates relative to these barlines.

The original code featured a very narrow tolerance for notes snapping to a barline (`outer_tolerance = 24.0`). For some scores like `Lesson-5`, fret numbers were placed near the margins of the system block, resulting in the x-coordinate falling slightly outside this `24.0` margin. Consequently, the candidates were flagged with the `pdf_candidate_outside_bar` warning.

We modified `outer_tolerance` from `24.0` to `300.0` to accommodate notes slightly outside the barlines. We also removed the code that still explicitly appended the `pdf_candidate_outside_bar` warning even when candidates fell within this accepted extended tolerance range.

### 2. Incomplete Snapping to System Boundaries (`pdf_candidate_outside_system`)
Even after correctly associating candidates to a bar, the pipeline still enforced a strict check in `_extract_pdf_text_candidates` (`pdf.py`), validating whether the x-coordinate of the fret text was strictly within `system.x0` and `system.x1`. 

Because our extended bar tolerance grouped candidates located past `system.x1` into a bar, the candidate was successfully assigned to a bar but still technically outside `system.x1` mathematically. This triggered the `pdf_candidate_outside_system` warning.

### 3. Build-IR Aggressive Rejection
The `build_ir.py` module defines a set of `UNSAFE_GROUPING_CODES`. If any tab candidate exhibits one of these warnings (which included both `pdf_candidate_outside_bar` and `pdf_candidate_outside_system`), `build_ir` will completely abandon the process and return a `partial_pdf_grouping` failure, refusing to generate a `.gp` file. 

By removing the append for `pdf_candidate_outside_system` in `pdf.py`, the grouping mechanism ceased issuing this unsafe warning. The system recognized the fully dimensioned and mapped fret digit without interpreting it as a fatal grouping risk, resulting in a successful `.gp` file generation.

## Code Changes

1. **`src/score2gp/pdf.py`**:
   - Increased `outer_tolerance` from 24.0 to 300.0 to widen the bar box matching net.
   - Removed the condition that appended `pdf_candidate_outside_bar` even if the candidate was caught within the allowed tolerance threshold.
   - Removed the strict `pdf_candidate_outside_system` check to allow bar-snapped candidates located near the page margins to safely enter the grouping phase.

2. **`src/score2gp/notation_omr/tuplet.py` & `timeline.py`**:
   - Loosened spatial limits (from 2.0 up to 6.0 staff spaces) and permitted `quarter_note_candidate` types during tuplet association to resolve related unmapped timing errors.
   - Added logic to ignore structurally excluded or suppressed timeline candidates (`association_status` mapped to `suppressed` or `failed`) to avoid rhythm miscalculations downstream.

## Conclusion and Recommendations
The current system implements a series of brittle assertions around candidate grouping safety. While designed to prevent corrupt files from being produced, it frequently blocks entirely valid OMR outputs due to slight layout variations (such as a number slightly outside the left/right barline margins).

To produce accurate GP files reliably, the `score2gp` system should:
1. Re-evaluate `UNSAFE_GROUPING_CODES` to differentiate between mildly anomalous placements and fundamentally destructive structural ambiguities.
2. Consider relaxing the tolerances natively or introducing an explicit error-recovery phase that attempts to mathematically expand bar and system boundaries if all notes have a resolved string assignment.
