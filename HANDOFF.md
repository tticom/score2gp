# Handoff

## Metadata

- **Current Branch**: `feature/private-smoke-refresh-after-pdf-timing-refinement-v1.0`
- **Base Branch**: `main`
- **Current PR**: [PR #51](https://github.com/tticom/score2gp/pull/51) (Draft)
- **Latest Local Commit**: `e549fae5ae812193324b27c5812b2973d58bbd77`
- **Latest Pushed Commit**: `e549fae5ae812193324b27c5812b2973d58bbd77`
- **Latest Commit Subject**: `Mark private-safe smoke refresh task as completed`
- **Working Tree Status Before Handoff Update**: Clean
- **GitHub Check Status**: Pending (triggered by current feature branch push)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, private summaries, overlays, logs, diagnostic outputs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. `git ls-files grouping-diagnostics.html inspect overlays tuning_outside.tabraw.json warnings.json` returned no tracked files.

## Tests And Checks Run

- `python -m pytest` -> 301 passed.
- `python -m score2gp.cli export-schema --out schemas` -> passed.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed.
- `git diff -- schemas` -> empty.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `git ls-files grouping-diagnostics.html inspect overlays tuning_outside.tabraw.json warnings.json` -> empty.

## What Changed

- Ran the E2E private smoke runner `scripts/private_e2e_smoke.py` against local real private inputs to generate ignored diagnostic outputs under `work/`.
- Generated private-safe E2E summaries (`work/private_e2e_smoke_v0_1/private_e2e_summary.json` and `work/private_e2e_smoke_v0_1/private_e2e_summary.md`).
- Fully compared the new `pdf-timing-refinement.v1.0` classifications and issue codes against real OMR timing risk inputs on `private_input_1`.
- Verified that all 301 test suites, schema validation, and git tracking assertions pass.
- Marked the smoke refresh task as done in `TASKS.md`.
- Opened draft PR #51 on origin.

## Private Smoke Refresh Result

An E2E private smoke refresh was run successfully against all local private inputs under `fixtures/private/`. Below is the anonymized, private-safe summary of results:

| Label | Type | Pages | Extract | ASCII Tab | Drawn Tab | Playable | ScoreIR | GP | Failure Reason | Next Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `private_input_1` | `pdf-tab-musicxml` | 2 | Yes | Yes | Yes | 191 | No | No | `musicxml_timing_risk` | `review-musicxml-timing-risk-before-alignment` |
| `private_input_custom` | `pdf-tab-only` | 2 | Yes | Yes | Yes | 101 | No | No | `none` | `provide-matching-musicxml-before-build-ir` |
| `private_input_2` | `pdf-tab-only` | 1 | Yes | Yes | Yes | 54 | No | No | `none` | `provide-matching-musicxml-before-build-ir` |

### Detailed Findings & Comparison

#### 1. `private_input_1` (`Derek Trucks BB King`)
- **Status**: Timing failed (`timing_status = "failed"`), ScoreIR writing refused (`scoreir_gate_status = "refused"`). Grouping remains partial (`grouping_status = "partial_pdf_grouping"`).
- **Candidates**: 362 total, 191 playable, 171 non-playable. Playable candidates are assigned as: 301 assigned to system, 282 to bar, 139 to string.
- **Timing Refinement Classifications (v1.0)**:
  - `timing_classification`: `invalid_timing_refused`.
  - `mapping_quality_classification` (mapping sidecar): `refused`.
  - `musicxml_timing_issue_counts`: `musicxml-overfull-bar`: 63, `musicxml-underfull-bar`: 1, `musicxml_alignment_not_attempted_due_to_timing_risk`: 1, `musicxml_many_timing_risks`: 2, `musicxml_tie_continuity_risk`: 2 (total 69 issues: 66 errors, 3 warnings).
  - `primary_reason_counts`: `musicxml_voice_timeline_valid`: 67.
  - `secondary_reason_counts` include: `musicxml_event_extends_past_measure` (66), `musicxml_same_voice_measure_overfull` (66), `musicxml_voice_duration_overfull` (66), `musicxml_tie_continuity_blocks_calibration` (69), `musicxml_timing_calibration_not_safe` (69).
- **Layout Blockers**: PDF grouping successfully identifies OMR layout warning codes including `pdf_bar_box_one_boundary_rejected` (1) on page 2.
- **Comparison**: `private_input_1` remains blocked by `musicxml_timing_risk` and `partial_pdf_grouping`. The timing preflight successfully categorizes the risk under the new `invalid_timing_refused` classification, highlighting 66 overfull event violations.

#### 2. `private_input_2` (`Lick in All 5 CAGED Shapes...`)
- **Status**: Grouping failed (`grouping_status = "missing_pdf_grouping"`), ScoreIR writing not attempted.
- **Candidates**: 84 total, 54 playable, 30 non-playable.
- **Blockers**: early exit due to `missing_pdf_grouping` / `pdf-tab-system-not-detected`.
- **Comparison**: `private_input_2` remains blocked by complete system-not-detected, correctly refusing to align ASCII-tab inputs with no system layout.

#### 3. `private_input_custom` (`Just-Practice-Like-THIS-Every-Day`)
- **Status**: Grouping partial (`grouping_status = "partial_pdf_grouping"`), no MusicXML provided.
- **Candidates**: 124 total, 101 playable, 23 non-playable.
- **Blockers**: `missing_pdf_grouping`.

## Known Limitations

- No automatic MusicXML timing repair.
- No silent MusicXML timeline mutation to make invalid inputs pass.
- No OCR, scanned-PDF support, ML layout recognition, or broad score conversion.
- No MusicXML pitch/tuning inference to bypass PDF geometry gates.
- No inference of missing durations, events, strings, or frets.
- Vector x-to-onset evidence remains diagnostic and cannot repair unsafe PDF grouping or unsafe MusicXML timing.
- Non-monotonic vector layout timing evidence remains refused.

## Remaining Risks

- The OMR timing files (MusicXML) from Audiveris and other transcription software frequently contain duration imbalances and ties that violate ScoreIR voice constraints.
- Visual barlines and staff geometry on pages with dense text overlays can trigger fallback line/box rejections.

## Next Recommended Task

Add developer-facing HTML styling and compact thumbnails for PDF grouping diagnostics (`grouping-diagnostics.html`) to make the visual boundary rejections easier to inspect and reproduce.

## Explicit Scope Boundaries

- Do not tune to private examples.
- Do not commit private files or `work/` outputs.
- Do not weaken timing/grouping/string/fret/build-ir gates.
- Do not implement automatic MusicXML timing repair without a future explicit, public-fixture-proven gate.
- Do not infer strings or frets from MusicXML pitch/tuning.
- Do not use tuning evidence to bypass geometry gates.
- Do not implement OCR, scanned-PDF support, ML layout recognition, GPIF expansion, or broad score conversion in this branch.
