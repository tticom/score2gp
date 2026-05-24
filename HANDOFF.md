# Handoff

## Metadata
- **Current Branch**: `feature/pdf-pitch-tuning-v0.6`
- **Base Branch**: `main`
- **Current PR**: None (Feature Branch)
- **Latest Local Commit**: `766a581`
- **Latest Pushed Commit**: `9e3e555`
- **Commit Subject**: Refine PDF pitch and tuning layout parsing and public fixtures v0.6
- **Working Tree Status**: Clean (except modified `HANDOFF.md` once saved, and untracked diagnostic/inspect outputs)
- **Tests & Checks Run**:
  - `python -m pytest` -> 274 passed cleanly in 17.33s
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under Git
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Added 10 Public Synthetic PDF Fixtures**: programmatically generated via `tests/fixtures/pdf/make_pitch_tuning_pdfs.py` to cover all crucial layout and pitch/tuning scenarios:
  1. `generated_pdf_tuning_standard_text.pdf`: Standard tuning text page-wide.
  2. `generated_pdf_tuning_explicit_eadgbe.pdf`: Explicit EADGBE six-string labels.
  3. `generated_pdf_tuning_alternate_dadgad.pdf`: Alternate DADGAD six-string labels.
  4. `generated_pdf_tuning_label_outside.pdf`: Standard tuning text outside system bounds.
  5. `generated_pdf_tuning_conflict.pdf`: Conflicting Standard and Drop D tuning texts on the same page.
  6. `generated_pdf_tuning_malformed.pdf`: Malformed "Tuning: Standardish" text.
  7. `generated_pdf_tuning_chord_resembling.pdf`: Chord symbol resembling a pitch label above staff.
  8. `generated_pdf_tuning_section_note_names.pdf`: Section text containing note names.
  9. `generated_pdf_tuning_valid_grouping.pdf`: Valid system/bar/string/fret grouping with tuning evidence.
  10. `generated_pdf_tuning_timing_unimplemented.pdf`: Proves timing mapping remains not implemented.
- **Defined Taxonomy of 5 Pitch/Tuning Blocker Codes**:
  - `pdf_tuning_conflict_detected`: Conflict among vertical string labels or multiple page-wide tuning texts.
  - `pdf_tuning_label_ambiguous`: Tuning labels are ambiguous or conflict on the page.
  - `pdf_tuning_label_malformed`: Malformed tuning label.
  - `pdf_tuning_format_unsupported`: Unsupported tuning format.
  - `pdf_pitch_tuning_diagnostics_not_enough_for_build_ir`: Diagnostic blocker refusing ScoreIR construction due to unresolved tuning ambiguities.
- **Implemented Conservative Heuristics & Diagnostics**:
  - Refined page-wide standard tuning detection checking line-texts case-insensitively and detecting conflicts when multiple tuning styles are matched on the same page.
  - Implemented explicit vertical six-string label detection on the left side of systems, verifying clean alignment to staff line Ys.
  - Whitelisted outside/unassociated tuning warnings in candidate preservation logic (`_should_keep_candidate`) to ensure non-playable tuning candidates are correctly reported and not silently filtered out.
  - Integrated full whitelisting of the new pitch/tuning blocker codes in the `unsafe` warning codes list inside `build_ir.py`, correctly refusing ScoreIR construction when blockers are detected.

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
- **Previous summary**: `private_input_1` had grouping status `partial_pdf_grouping` and system 6 on page 2 had fallback rejected safely under PR #44.
- **Current summary**: Rejection behavior remains correctly strict, keeping `partial_pdf_grouping` and blocking ScoreIR generation. The new pitch/tuning parser accurately preserves, classifies, and reports all PDF pitch/tuning evidence without inferring playable frets/strings or loosening geometry gates, keeping ScoreIR gates fully secure.

## Current Top Blocker Classification
1. **`pdf_bar_box_one_boundary_rejected`** (Primary PDF grouping blocker stage)
2. **`musicxml_timing_repair_not_safe`** (Primary MusicXML timeline voice overlap blocker)

## Next Recommended Task / Branch
- **`feature/pdf-timing-mapping-v0.7`**: Refine timing mapping alignment for PDF-derived TabRaw, utilizing onsets and calibration metrics to build/repair robust PDF ScoreIR.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
