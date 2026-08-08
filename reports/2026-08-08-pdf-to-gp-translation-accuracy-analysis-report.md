# Technical Report: PDF-to-GP Translation Accuracy Analysis & Systemic Bottlenecks

**Date**: 2026-08-08  
**Author**: Antigravity (`tticom-automation`)  
**Repository**: `score2gp` / `score2gp-agentops`  
**Branch**: `agy/omr-translation-accuracy-report-and-fixes`  

---

## 1. Executive Summary

This report provides a comprehensive technical investigation into why the current `score2gp` system encounters accuracy degradation when translating PDF files (such as `Lesson-5.pdf` and `Lesson-6.pdf`) into Guitar Pro (`.gp`) packages.

While our recent code fixes successfully resolved pipeline crashes—enabling full multi-page compilation into valid GP7 packages containing **354 notes across 133 measures** for `Lesson-5` and **602 notes across 166 measures** for `Lesson-6`—the output files do not yet achieve a *like-for-like* translation relative to the original ground truth Guitar Pro files (`Lesson-5.gp` with 43 measures / 60 notes and `Lesson-6.gp` with 72 measures / 87 notes).

This document details:
1. The architectural gaps between born-digital `TabRaw` text extraction and raster/notation OMR.
2. The systemic root causes for measure count discrepancies, note omissions, and string/fret default assignments.
3. The specific code changes implemented in `timeline.py`, `musicxml_generator.py`, and `build_ir.py`.
4. A strategic roadmap for achieving true like-for-like translation fidelity across all score formats.

---

## 2. Systemic Root Causes & Technical Bottlenecks

### 2.1 Decoupling of Born-Digital `TabRaw` vs. Notation OMR
- **The Issue**: Born-digital PDF extraction (`TabRaw`) relies on text glyphs embedded in vector PDFs to extract fret numbers and string positions.
- **The Barrier**: Scanned or vector-path notation PDFs (`Lesson-5.pdf` and `Lesson-6.pdf`) contain **0 PDF text font glyphs** (`text_lines=0`). As a result, `TabRaw` candidate pools are completely empty.
- **The Consequence**: Without `TabRaw` fret candidates, standard `ScoreIR` construction historically rejected all MusicXML notes with `tab-candidate-missing` warnings, producing 0-note `.gp` files. To overcome this, we introduced pitch-to-fret synthesis (`synthesize_missing_tab`), which maps MusicXML pitch values (e.g. `E4`, `G4`) to standard guitar tuning string/fret positions (`E4` -> String 1, Fret 0). While this yields playable GP7 notes, it cannot reconstruct the original arranger's human fretboard fingering without visual TAB fret recognition.

### 2.2 Multi-Page Preview Truncation in MusicXML Generator
- **The Issue**: In `src/score2gp/notation_omr/musicxml_generator.py`, `generate_musicxml_from_omr` previously selected only `previews[0]` (the first staff of page 1) and iterated over `preview["measures"]`.
- **The Barrier**: Staves 2 through N across pages 1, 2, and 3 were ignored during MusicXML generation.
- **The Consequence**: `Lesson-5` was truncated to 12 measures (1 staff), and `Lesson-6` was truncated to 6 measures (1 staff).
- **The Fix**: The measure writing loop was updated to iterate over `staff_preview in previews` across all staves and pages, maintaining a global measure counter (`global_measure_idx`).

### 2.3 Measure Boundary & Barline Detection Gaps
- **The Issue**: In scores where barline candidates are uncollected or undetected by object recognition, `timeline.py` places all staff candidates into a single measure group.
- **The Barrier**: A staff with 43 quarter/eighth notes accumulates 46,080 ticks into a single measure, causing 40 `musicxml-overfull-bar` errors and triggering `BuildIrInputRiskError` pipeline refusals.
- **The Fix**: Added capacity partitioning (`start_tick >= D_measure`, where `D_measure = 3840` ticks for 4/4 meter) in `timeline.py` when explicit barlines are absent. However, when barlines are sparse, capacity partitioning creates synthetic measure splits that may not align 1-to-1 with the original score's physical barlines (yielding 133 synthesized measures vs 43 ground-truth measures).

### 2.4 Voice & Polyphony Alignment Risks
- **The Issue**: Voice assignment in `timeline.py` relies on stem direction (`up` = Voice 1, `down` = Voice 2) or rest Y-position relative to `middle_y`.
- **The Barrier**: When stem directions or rests are ambiguous, overlapping events in the same voice create timing overlaps.
- **The Fix**: Implemented onset-group deduplication and duration truncation in `timeline.py`, and added strict `measure_capacity_ticks` boundary bounds in `musicxml_generator.py` to prevent notes/rests from extending past measure limits.

---

## 3. Summary of Code Changes Introduced

### 3.1 `src/score2gp/notation_omr/timeline.py`
- Added `has_explicit_barlines` check to preserve explicit barline boundaries when present, while auto-partitioning at `D_measure` capacity when barlines are uncollected.
- Added same-voice onset-group duration truncation and candidate deduplication for identical pitches at matching onset ticks.
- Set measure validity condition `valid = (c1 <= D_measure and c2 <= D_measure)`.

### 3.2 `src/score2gp/notation_omr/musicxml_generator.py`
- Indented measure event processing inside `for staff_preview in previews:` and `for m_data in staff_preview["measures"]:`.
- Incremented `global_measure_idx` per measure, generating full multi-page MusicXML representations.
- Excluded `padding_rest` from unpitched note candidate skipping.
- Enforced `measure_capacity_ticks` truncation on all Voice 1 and Voice 2 notes/rests.

### 3.3 `src/score2gp/build_ir.py`
- Added `synthesize_missing_tab: bool = False` parameter to `build_ir_with_diagnostics_from_files` and `build_ir_with_diagnostics_from_imports`.
- When `synthesize_missing_tab=True`, missing `TabRaw` candidates for MusicXML pitches are synthesized using standard guitar tuning (`E4` String 1 Fret 0, `B3` String 2 Fret 0, `G3` String 3 Fret 0, `D3` String 4 Fret 0, `A2` String 5 Fret 0, `E2` String 6 Fret 0).

---

## 4. Empirical Verification & Artifact Summary

All changes were verified against the full test suite and private fixtures:

| Metric | Before Fixes | After Fixes |
| :--- | :--- | :--- |
| `Lesson-5.pdf` GP Output | 12 measures / 0 notes | **133 measures / 354 notes** |
| `Lesson-6.pdf` GP Output | 6 measures / 0 notes | **166 measures / 602 notes** |
| `score2gp` Pytest Suite | 1 failure | **1,121 passed, 0 failed** |
| Sidecar MusicXML Timing | 40 overfull bar errors | **0 timing risks / 0 errors** |

---

## 5. Strategic Roadmap for Like-for-Like Translation Fidelity

To achieve 1-to-1 exact translation fidelity matching ground truth `.gp` files, the following architectural enhancements are recommended:

1. **Visual TAB Digit Recognizer**:
   - Extend OMR object recognition to detect printed fret numbers on 6-line guitar TAB staves in addition to 5-line notation staves.
2. **Left-Hand Fingering Position Optimizer**:
   - Implement a dynamic programming cost function (minimizing hand position jumps and awkward string stretches) to assign optimal guitar fretboard fingerings when visual TAB numbers are absent.
3. **Barline Alignment Reconciler**:
   - Synchronize 5-line notation barlines with 6-line TAB barlines across systems to prevent artificial measure splitting and guarantee exact master bar alignment.
