# Handoff

## Metadata
- **Current Branch**: `feature/private-e2e-diagnostic-smoke-v0.1`
- **Base Branch**: `main`
- **Current PR**: PR #13 (https://github.com/tticom/score2gp/pull/13)
- **Latest Local Commit**: `945fb2e1843baa03a2ee9671078ab90769bc2f99`
- **Latest Pushed Commit**: `945fb2e1843baa03a2ee9671078ab90769bc2f99`
- **Commit Subject**: `Add private-safe E2E diagnostic smoke`
- **Working Tree Status**: Clean (before handoff commit)
- **Tests & Checks Run**:
  - `python -m pytest` -> 124 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed
  - `git diff -- schemas` -> empty
- **GitHub Check Status**: Checks running on GitHub Actions
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Added a local-only private E2E diagnostic smoke script/workflow (`scripts/private_e2e_smoke.py`).
- Added public-safe tests for the private smoke script (`tests/test_private_smoke.py`) using synthetic/public temporary fixtures proving:
  1. The script writes a summary JSON and Markdown.
  2. The summary redacts/avoids raw score text and private information.
  3. The summary includes counts, status, and reason codes.
  4. Private-like filenames can be anonymized properly.
  5. Outputs are written under a supplied output directory (`work/` or `tmp_path`).
  6. No private fixtures are required to run the test suite.
- Updated documentation (`docs/workflow.md` and `docs/limitations.md`) to reflect that the private diagnostic smoke is optional, local-only, does not commit private files, uses private examples purely as diagnostic inputs, and never tunes thresholds or weakens validation gates to make specific private examples pass.
- Updated `TASKS.md` to reflect the completed task.
- Generated draft Pull Request #13 using the compiled E2E PR body.

## Private Smoke Result Summary (Safe Counts & Statuses Only)
The local diagnostic smoke scan successfully identified and processed the following private inputs:
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
- Private smoke is diagnostic-only and does not tune thresholds.
- It does not make private examples pass or weaken validation/timing gates.
- No OCR or scanned-PDF support.
- No broad ASCII-to-ScoreIR conversion.
- GPIF technique rendering is out of scope.

## Remaining Risks
- None. Stable public fixtures and strict pipeline validations are fully in place. All local summaries are verified to be private-safe.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken validation/timing gates or tune thresholds to private examples.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** expand GPIF technique rendering.
- **Do not** push directly to main.

## Next Recommended Task
- Review and merge the private E2E diagnostic smoke PR (PR #13). Once merged, the next step is to address the MusicXML timing/overlap issue in the pipeline or begin designing alignment improvement gates for public ascii alignment, keeping a strict gate without loosening thresholds.
