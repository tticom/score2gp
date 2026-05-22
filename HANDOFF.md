# Handoff

## Metadata
- **Current Branch**: `feature/tabraw-symbol-attachment-v0.1`
- **Base Branch**: `main`
- **Current PR**: #10 (URL: https://github.com/tticom/score2gp/pull/10)
- **Latest Local Commit**: `b1563df868d4076395b001a1d95c721c00224d45`
- **Latest Pushed Commit**: `b1563df868d4076395b001a1d95c721c00224d45`
- **Commit Subject**: `Add conservative TabRaw symbol attachment`
- **Working Tree Status**: Clean (once HANDOFF.md is committed)
- **Tests & Checks Run**:
  - `python -m pytest` -> 119 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed
  - `git diff -- schemas` -> empty
- **GitHub Check Status**: Pending (Checks running on PR #10)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL files, overlays, logs, or diagnostic outputs are tracked or staged.

## What Changed in the Task
- Attached PDF-derived chord symbols and technique text to safely timed ScoreIR bars/events in a narrow public-fixture-only way.
- Implemented visual proximity and default first-event chord symbol attachment for `chord-symbol` candidates, including safety checks for ambiguity (refusing attachment if another target event is within a tight range of 2.0 visual units).
- Implemented single-note technique text attachment for `slide`, `bend`, `vibrato` candidates, and span technique attachment for `hammer-on` and `pull-off` candidates requiring exactly two chronological notes in the bar.
- Emitted specific, detailed WarningItem warning codes for unattached, ambiguous, or unsupported symbols/techniques:
  - `symbol_attachment_requires_timing`
  - `unattached_chord_symbol`
  - `technique_attachment_requires_note_target`
  - `unattached_technique_text`
  - `ambiguous_chord_symbol_attachment`
  - `unsupported_technique_text`
  - `ambiguous_technique_attachment`
- Cleared the original pre-alignment `tabraw-{kind}-not-aligned` warnings upon successful alignment/attachment of chord symbols or technique texts to keep warnings clean.
- Added comprehensive public tests for chord symbol proximity attachment, technique attachment, unsupported vocabulary, and span techniques.
- Persisted the planning and execution rule inside `AGENTS.md` to avoid unnecessary stops after creating implementation plans in future tasks.

## Known Limitations
- No OCR or scanned-PDF support.
- No ML layout recognition.
- No ASCII success path broadening.
- No duration inference from PDF text/columns.
- No GPIF rendering of attached techniques.
- High reliance on visual coordinates; inputs without reliable coordinates fall back to default anchors or emit ambiguity warnings.

## Remaining Risks
- Relying on simple heuristic distance thresholds (like the 2.0 units proximity tie-breaker) might need calibration on larger public synthetic corpora.

## Explicit Scope Boundaries
- **Do not** start OCR, scanned-PDF support, or ML layout recognition.
- **Do not** broaden ASCII-to-ScoreIR conversion.
- **Do not** infer durations from PDF text.
- **Do not** use private PDFs as regression fixtures.
- **Do not** commit `work/` outputs or private files.

## Next Recommended Task
- Implement HTML-based visualization or rendering support to inspect the attached chord symbols and techniques in the generated ScoreIR.
