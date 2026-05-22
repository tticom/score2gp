# Handoff

## Metadata
- **Current Branch**: `feature/ascii-scoreir-gate-html-diagnostics-v0.1`
- **Base Branch**: `main`
- **Current PR**: #9 (URL: https://github.com/tticom/score2gp/pull/9)
- **Latest Local Commit**: `d33406e87381c1ee50b89f35d1efec94e5262531`
- **Latest Pushed Commit**: `d33406e87381c1ee50b89f35d1efec94e5262531`
- **Commit Subject**: `Update handoff for HTML diagnostics PR`
- **Working Tree Status**: Clean (once HANDOFF.md is committed)
- **Tests & Checks Run**:
  - `python -m pytest` -> 115 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed (CRLF warnings only)
  - `git diff -- schemas` -> empty
- **GitHub Check Status**: Pending (Checks running on PR #9)
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL files, overlays, logs, or diagnostic outputs are tracked or staged.

## What Changed in the Task
- Added developer-facing HTML rendering for ASCII ScoreIR gate refusal diagnostics.
- When `build-ir` refuses due to ASCII ScoreIR gate diagnostics, it writes an HTML diagnostics report (`ascii-scoreir-gate-diagnostics.html`) alongside the JSON diagnostics sidecar.
- The HTML report displays:
  - Gate status (refused/allowed)
  - Primary refusal reason code
  - Secondary refusal reason codes (or explicitly "None")
  - Remediation hints
  - Total candidate count, aligned candidate count, and rejected candidate count
  - Safe candidate IDs (if present)
  - MusicXML timing safety status
  - Alignment sidecar presence and status
  - Whether ScoreIR was written
  - Reference to the JSON diagnostics sidecar
  - Clear statement that refusal is expected for unsupported ASCII inputs
- Preserved backward compatibility of existing JSON diagnostics.
- Added comprehensive public tests for the HTML report content without using private fixtures.
- Updated documentation (`docs/architecture.md`, `docs/workflow.md`, `docs/limitations.md`, and `TASKS.md`) detailing the new developer-facing report and strict boundaries.

## Known Limitations
- HTML diagnostics are developer-facing explanations. JSON diagnostics remain the programmatic source of truth.
- Refusal is expected for most inputs as this does not broaden ASCII-to-ScoreIR conversion.
- No OCR or scanned-PDF support.
- No ML layout recognition or arbitrary commercial score conversion.
- Symbol/technique attachment remains out of scope.
- GPIF output remains minimal.

## Remaining Risks
- None. Refusal is deterministic and expected for unsupported ASCII inputs.

## Explicit Scope Boundaries
- **Do not** start symbol/technique attachment.
- **Do not** broaden ASCII-to-ScoreIR conversion.
- **Do not** add new ScoreIR success paths.
- **Do not** implement OCR or scanned-PDF support.
- **Do not** use private PDFs as regression fixtures.
- **Do not** commit `work/` outputs or private files.

## Next Recommended Task
- Attach PDF-derived chord symbols and technique text to ScoreIR events once timing calibration exists.
