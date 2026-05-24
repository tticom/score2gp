# Handoff

## Metadata
- **Current Branch**: `feature/pdf-timing-mapping-v0.7`
- **Base Branch**: `main`
- **Current PR**: [PR #46](https://github.com/tticom/score2gp/pull/46) (Draft)
- **Latest Local Commit**: `9876791`
- **Latest Pushed Commit**: `9876791`
- **Commit Subject**: Add PDF timing mapping diagnostics v0.7
- **Working Tree Status**: Clean (except modified `HANDOFF.md` once saved, and untracked diagnostic/inspect outputs)
- **Tests & Checks Run**:
  - `python -m pytest` -> 284 passed cleanly in 14.69s (including 10 new timing mapping tests)
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked under Git
- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- **Defined PDF Timing-Mapping / Spacing Telemetry Schema (`pdf-timing-mapping.v0.7`)**:
  - Populates diagnostic metrics: `contract_version`, `input_class`, `grouping_status`, `grouping_safe`, `timing_source_safe`, `musicxml_timing_preflight_status`, `whether_mapping_attempted`, `whether_mapping_refused`, `refusal_reason_codes`, `quality`, `whether_scoreir_written`, `remediation_hint`, `per_bar`, `matched_x_onset_group_count`, `unmatched_x_group_count`, `unmatched_onset_group_count`, `mean_absolute_relative_error`, `max_relative_error`, `monotonic`, `ambiguity_count`.
  - Added Pydantic field `pdf_timing_mapping` on `BuildIrDiagnostics` class.
- **Implemented Visually Rich Developer Diagnostics HTML Report (`pdf-timing-mapping-diagnostics.html`)**:
  - Visual dark-mode premium dashboard showing attempting/refused verdict, tabular comparison of per-bar spacing, drift metrics, ambiguity, and remediation info.
  - Automatically written on both successful runs and `BuildIrInputRiskError` failure paths.
- **Added 4 Timing-Mapping Blocker Taxonomy Codes**:
  - `pdf_timing_mapping_refused`
  - `pdf_timing_mapping_not_enough_for_build_ir`
  - `pdf_timing_mapping_group_count_mismatch`
  - `pdf_timing_mapping_non_monotonic`
  - Whitelisted these in `_tabraw_unsafe_grouping_warning_codes` to cleanly enforce gates.
- **Enforced Strict Compiler Gates & Preflight Safeties**:
  - Attempt timing mapping only if grouping is safe and preflight MusicXML timing is safe.
  - Strictly block ScoreIR compilation and raise `BuildIrInputRiskError` if visual x-positions across bars are non-monotonic (`monotonic == False`), ensuring correct ordering.
  - Allow slightly uneven spacings to pass with warning/poor quality warnings in diagnostics JSON/HTML without breaking build-ir, satisfying existing spacing regression tests.
- **Added 10 Public Synthetic Timing Mapping Tests**:
  - Programmatically exercises clean one-bar spacing (good), clean multi-bar spacing (good), extra PDF x group (warning/poor), missing PDF x group (warning/poor), non-monotonic ordering (refused), ambiguous close x groups (warning/poor), chord stack (review flagged), unsupported polyphony (refused), unsafe MusicXML timing (refused), unsafe PDF grouping (refused).
  - All 284 project tests are now passing cleanly!

## Private Smoke Blocker Summary (No Private Content Included)
- **`private_input_1`** (`pdf-tab-musicxml`):
  - **Input class**: `drawn_tab_candidate`
  - **Page count**: 2
  - **Drawn system count**: 14 (8 on page 1, 6 on page 2)
  - **Constructed bar box count**: 13 constructed.
  - **Unboxed system count**: 1 (system 6 on page 2).
  - **Total candidate count**: 329.
  - **Playable candidate count**: 203.
  - **Non-playable candidate count**: 126.
  - **Candidates assigned to system**: 282.
  - **Candidates assigned to bar**: 265.
  - **Candidates assigned to string**: 141.
  - **Grouping status**: `partial_pdf_grouping`
  - **Primary PDF blocker stage**: `pdf_bar_box_one_boundary_rejected` (system 6 on page 2 has 1 accepted and 1 rejected boundary, blocking fallback and grouping).
  - **Timing blocker stage**: `musicxml_timing_repair_not_safe` (preflight VoiceOverlapError with 66 overfull or overlapping events).
  - **ScoreIR gate status**: `refused` (blocked by PDF grouping and timing).
  - **PDF Timing Mapping Status**: `refused` (with `pdf_timing_mapping_not_attempted_grouping_unsafe` and `pdf_timing_mapping_not_attempted_musicxml_unsafe`).

- **`private_input_2`** (`pdf-tab-only`):
  - **Input class**: `ascii_tab_candidate` / `unsupported`
  - **Page count**: 1
  - **ASCII block count**: 1
  - **Total candidate count**: 71.
  - **Playable candidate count**: 54.
  - **Non-playable candidate count**: 17.
  - **Grouping status**: `missing_pdf_grouping`
  - **Primary PDF blocker stage**: `drawn_system_detection` and `ascii_system_detection` (`pdf-tab-system-not-detected`).
  - **Timing status**: `not_attempted`.
  - **PDF Timing Mapping Status**: `refused` (with `pdf_timing_mapping_not_attempted_grouping_unsafe` and `pdf_timing_mapping_not_attempted_missing_musicxml`).

## Current Top Blocker Classification
1. **`pdf_bar_box_one_boundary_rejected`** (Primary PDF grouping blocker stage)
2. **`musicxml_timing_repair_not_safe`** (Primary MusicXML timeline voice overlap blocker)

## Next Recommended Task / Branch
- **`feature/pdf-fret-refinement-v0.8`**: Focus on refining fret digit height/width size gates and horizontal digit overlap grouping filters to build premium ScoreIR.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken timing/grouping gates or implement timing auto-repair.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
