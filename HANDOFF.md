# Handoff

## Metadata
- **Current Branch**: `feature/musicxml-overlap-diagnostics-v0.1`
- **Base Branch**: `main`
- **Current PR**: *Pending creation in Phase 12*
- **Latest Local Commit**: `e35238fdf28945ff60086bb5f7b036573c0be850`
- **Latest Pushed Commit**: `e35238fdf28945ff60086bb5f7b036573c0be850`
- **Commit Subject**: `Merge pull request #13 from tticom/feature/private-e2e-diagnostic-smoke-v0.1`
- **Working Tree Status**: Modified files (before handoff commit)
- **Tests & Checks Run**:
  - `python -m pytest` -> 135 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git diff -- schemas` -> empty
- **GitHub Check Status**: N/A (before push)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Improved MusicXML timing/overlap diagnostics and strict validation gates so that the pipeline safely and explicitly blocks MusicXML timing/voice/overlap problems before ScoreIR generation.
- Implemented robust timing analysis in `src/score2gp/musicxml.py` covering:
  - Overfull measures (`musicxml-overfull-bar`)
  - Underfull measures (`musicxml-underfull-bar` warning)
  - Same-voice overlapping events (`musicxml-voice-overlap`)
  - Multi-voice pitched note overlaps (`musicxml_polyphony_not_supported`)
  - Legitimate chord stacks (`musicxml_chord_stack_detected` info)
  - Backup/forward cursor movement risks (`musicxml_backup_forward_risk` / `musicxml_unbalanced_backup_forward`)
  - Rest overlaps with other events (`musicxml_rest_overlap`)
  - Missing or zero duration note properties (`musicxml_duration_missing` / `musicxml_duration_zero`)
  - Mid-measure/mid-part divisions changes (`musicxml_divisions_changed_mid_measure` / `musicxml-divisions-changed`)
  - Unsupported tuplet timing (`musicxml_tuplet_unsupported`)
- Updated standard build-ir error escalation in `src/score2gp/build_ir.py` to treat note duration issues as fatal errors for non-ASCII standard E2E paths, while letting the ASCII gate check them if an ASCII alignment sidecar is present.
- Created 10 public synthetic timing and overlap fixtures under `tests/fixtures/musicxml/` to model each category.
- Added a dedicated test suite `tests/test_musicxml_timing_overlap.py` verifying all 10 synthetic fixtures.
- Added a new developer-facing HTML diagnostic report `write_musicxml_timing_diagnostics_html` in `src/score2gp/report.py` that visualizes detailed tables of timing issues, affected measures, and voice metadata with tailored remediation hints on preflight failure.
- Updated documentation (`docs/architecture.md`, `docs/workflow.md`, `docs/limitations.md`, and `TASKS.md`) to integrate and explain the new preflight gates and HTML diagnostics.

## Private Smoke Result Summary (Safe Counts & Statuses Only)
The local diagnostic smoke scan from the previous task remains valid, showing:
1. **`private_input_1`** (`pdf-tab-musicxml`):
   - **Page Count**: 2
   - **Text/Geometry Detected**: Yes (both ASCII tab and drawn tab geometry detected)
   - **Playable Candidate Count**: 203 candidates
   - **Timing Status**: `failed` (ScoreIR gate status: `refused`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: `musicxml_timing_risk`
   - **Secondary Reason Codes**: `MusicXML timing risk prevents ScoreIR output: 63 overfull or overlapping event(s) would violate ScoreIR timing`, `missing_pdf_grouping`, `pdf-tab-system-not-detected`
   - **Next Diagnostic Recommendation**: `review-musicxml-timing-risk-before-alignment`
2. **`private_input_2`** (`pdf-tab-only`):
   - **Page Count**: 1
   - **Text/Geometry Detected**: Yes (both ASCII tab and drawn tab geometry detected)
   - **Playable Candidate Count**: 54 candidates
   - **Timing Status**: `not_attempted` (ScoreIR gate status: `not_attempted`)
   - **GP Written**: No
   - **Primary Failure/Refusal Reason**: None (MusicXML is missing)
   - **Secondary Reason Codes**: `missing_pdf_grouping`, `pdf-tab-system-not-detected`
   - **Next Diagnostic Recommendation**: `provide-matching-musicxml-before-build-ir`

## Known Limitations
- Diagnostics are conservative and do not tune to private examples or loosen the safety gates.
- Polyphony/overlap support is intentionally narrow and monophonic-focused.
- Backup/forward cursor movement is checked strictly at measure boundaries.
- No OCR or scanned-PDF support.

## Remaining Risks
- None. All 135 tests are fully passing locally. Whitespace checks are perfectly clean, and schemas are identical to the base branch.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken validation/timing gates or tune thresholds to private examples.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** expand GPIF technique rendering.
- **Do not** push directly to `main`.
