# Handoff

## Metadata
- **Current Branch**: `feature/pdf-fret-refinement-v0.5`
- **Base Branch**: `main`
- **Current PR**: [PR #44](https://github.com/tticom/score2gp/pull/44) (Draft)
- **Latest Local Commit**: `f2672bd`
- **Latest Pushed Commit**: `f2672bd`
- **Commit Subject**: Add PDF fret refinement fixtures v0.5
- **Working Tree Status**: Clean (except modified `HANDOFF.md` once saved)
- **Tests & Checks Run**:
  - `python -m pytest` -> 262 passed cleanly in 17.42s
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under Git
- **GitHub Check Status**: N/A (Draft PR)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Added 11 Public Synthetic PDF Fixtures**: Created a programmatic generator `tests/fixtures/pdf/make_fret_refinement_pdfs.py` compiling 11 public synthetic PDF fixtures under `tests/fixtures/pdf/` mapping to key fret-refinement scenarios:
  1. `generated_pdf_fret_clean_single_digit.pdf`: Clean single-digit frets on six tab strings.
  2. `generated_pdf_fret_clean_multidigit.pdf`: Clean multi-digit frets such as 10, 12, 15.
  3. `generated_pdf_fret_split_span_merged.pdf`: Multi-digit fret split into separate text spans but tightly aligned.
  4. `generated_pdf_fret_gap_too_large.pdf`: Adjacent digits too far apart horizontally.
  5. `generated_pdf_fret_vertical_misalignment.pdf`: Adjacent digits vertically misaligned.
  6. `generated_pdf_fret_technique_marker.pdf`: Digit near technique marker (e.g. 7h9, 5/7, 8b).
  7. `generated_pdf_fret_chord_text_excluded.pdf`: Chord symbol or section text containing digits above staff (e.g. A7 or Verse 2).
  8. `generated_pdf_fret_page_legend_excluded.pdf`: Page number / legend number outside tab system.
  9. `generated_pdf_fret_oversized_tall.pdf`: Oversized/tall text that overlaps multiple string bands.
  10. `generated_pdf_fret_tiny_noisy.pdf`: Tiny/noisy digit-like text.
  11. `generated_pdf_fret_grouped_success.pdf`: Valid grouped counterpart where fret refinement, system, bar, and string assignment all succeed.
- **Defined Taxonomy of 16 Fret-Related Warning/Reason/Provenance Codes**:
  - `pdf_fret_single_digit_extracted`: Clean single-digit fret candidate successfully extracted.
  - `pdf_fret_multidigit_extracted`: Clean multi-digit fret candidate successfully extracted.
  - `pdf_fret_digits_merged`: Horizontally close digits successfully merged into a single multi-digit candidate.
  - `pdf_fret_digits_not_merged_gap_too_large`: Rejection warning when horizontal gap between digits is too large to merge.
  - `pdf_fret_digits_not_merged_vertical_misalignment`: Rejection warning when digits are vertically misaligned.
  - `pdf_fret_split_text_span_merged`: Indicates horizontal merging performed across distinct PyMuPDF text spans.
  - `pdf_fret_bbox_too_tall`: Rejection warning when candidate bounding box height exceeds maximum limit.
  - `pdf_fret_bbox_too_wide`: Rejection warning when candidate bounding box width exceeds maximum limit.
  - `pdf_fret_bbox_too_small`: Rejection warning when candidate bounding box is too small/noisy.
  - `pdf_fret_outside_valid_range`: Rejection warning when numeric fret value is outside valid range (`0 <= fret <= 24`).
  - `pdf_fret_non_digit_rejected`: Rejection warning when candidate contains invalid non-digit characters.
  - `pdf_fret_technique_marker_excluded`: Technique symbols near fret digits are preserved as separate non-playable technique markers.
  - `pdf_fret_chord_text_digit_excluded`: Digits inside chord symbols or section text above staff are excluded from playable fret candidates.
  - `pdf_fret_page_or_legend_number_excluded`: Page/legend numbers outside the staff are excluded.
  - `pdf_fret_optical_bounds_confidence_below_threshold`: Rejection warning when optical bounding box dimensions are low-confidence.
  - `pdf_fret_refinement_not_enough_for_build_ir`: Blocker warning refusing ScoreIR construction due to unresolved fret ambiguities.
- **Implemented Conservative Heuristics for Horizontal & Vertical Grouping**:
  - Horizontal gap grouping threshold set to `5.0` pixels, and vertical offset alignment threshold set to `2.0` pixels inside the same string band.
  - Estimated proportional bounding boxes for split parts of technique mixed words (like `7h9`, `5/7`, `8b`) based on character length relative to overall word width.
  - Retained string distance and unassigned-to-string warning metadata on unassigned candidates to preserve robust downstream string diagnostics.
- **Enriched HTML/JSON Master Grouping Diagnostics**:
  - Integrated complete metrics for fret refinement, classification, merge counts, and rejection codes.
  - Updated visual Master Grouping report with a dedicated Fret Refinement section and clear remediation instructions.

## Private Smoke Blocker Summary (No Private Content Included)
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **ASCII block count**: 0
  - **Drawn system count**: 14 (8 on page 1, 6 on page 2)
  - **Accepted barline count**: System 6 on page 2 has 1 accepted boundary and 1 rejected boundary. The other 13 systems have accepted barlines and successfully constructed bar boxes.
  - **Constructed bar box count**: 13 constructed.
  - **Unboxed system count**: 1 (system 6 on page 2).
  - **Total candidate count**: 329.
  - **Playable candidate count**: 203.
  - **Non-playable candidate count**: 126.
  - **Candidates assigned to system**: 282.
  - **Candidates assigned to bar**: 265.
  - **Candidates assigned to string**: 141.
  - **Grouping status**: `partial_pdf_grouping`
  - **Primary PDF blocker stage**: `pdf_bar_box_one_boundary_rejected` (due to system 6 on page 2 having a rejected boundary, which correctly rejects fallback and blocks grouping).
  - **Timing blocker stage**: `musicxml_timing_repair_not_safe` (preflight VoiceOverlapError with 66 overfull or overlapping events).
  - **ScoreIR gate status**: `refused` (blocked by PDF grouping and timing).

- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Page count**: 1
  - **Text detected**: Yes
  - **Geometry detected**: Yes
  - **ASCII block count**: 1
  - **Total candidate count**: 71.
  - **Playable candidate count**: 54.
  - **Non-playable candidate count**: 17.
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary PDF blocker stage**: `drawn_system_detection` and `ascii_system_detection` (`pdf-tab-system-not-detected`).
  - **Timing status**: `not_attempted`.

## Comparison with Previous Blocker Summary
- **Previous summary**: `private_input_1` had grouping status `partial_pdf_grouping` and system 6 on page 2 had fallback rejected safely under PR #43.
- **Current summary**: Rejection behavior remains correctly strict, keeping `partial_pdf_grouping` and blocking ScoreIR generation. Non-playable chord symbols, page/legend numbers, and techniques are successfully preserved and excluded from playable fret blocking. Fret refinement successfully identifies clean candidates while flagging ambiguous or rejected merge boundaries appropriately, keeping ScoreIR gates fully secure.

## Current Top Blocker Classification
1. **`pdf_bar_box_one_boundary_rejected`** (Primary PDF grouping blocker stage)
2. **`musicxml_timing_repair_not_safe`** (Primary MusicXML timeline voice overlap blocker)

## Next Recommended Branch
- **`feature/pdf-pitch-tuning-v0.6`**: Once the draft PR for fret refinement is merged into main, the next recommended branch is `feature/pdf-pitch-tuning-v0.6` to refine pitch/tuning layout parsing and improve timing mapping.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
