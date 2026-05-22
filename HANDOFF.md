# Handoff

## Metadata
- **Current Branch**: `feature/musicxml-voice-cursor-model-v0.1`
- **Base Branch**: `main`
- **Current PR**: [#21](https://github.com/tticom/score2gp/pull/21)
- **Latest Local Commit**: `ab2f109602722620606cca115e1bc570fa4b22dc`
- **Latest Pushed Commit**: `ab2f109602722620606cca115e1bc570fa4b22dc`
- **Commit Subject**: Add MusicXML voice cursor model
- **Working Tree Status**: Clean (except HANDOFF.md)
- **Tests & Checks Run**:
  - `python -m pytest` -> 169 passed
  - `python -m score2gp.cli export-schema --out schemas` -> passed with no diffs
  - `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid
  - `git diff --check` -> passed cleanly
  - `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep` is tracked
- **GitHub Check Status**: Pending
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or diagnostic outputs are tracked or committed. All outputs under `work/` are ignored.

## What Changed in the Task
- Implemented a deterministic `MusicXmlVoiceCursorModel` that accurately tracks per-part, per-measure, and per-voice timelines.
- Properly simulated `backup`, `forward`, `rest`, and `chord` elements to calculate voice-specific start/end offsets and chord stack counts.
- Addressed chord stacks using `<chord/>` so they do not trigger false same-voice timing overlap errors.
- Refined build-ir gating: invalid same-voice timelines block ScoreIR with the `musicxml_timing_risk` category, whereas valid but unsupported multi-voice structures downstream trigger `musicxml_scoreir_polyphony_gate_refused`.
- Added 9 tiny synthetic public MusicXML fixtures to represent voice cursor patterns.
- Expanded the test suite in `tests/test_musicxml_voice_cursor.py` to assert diagnostic outcome correctness across all 9 new fixtures.
- Updated diagnostics HTML reports with voice cursor timeline counts and remediation hints for all 15 new voice cursor codes.

## Change Comparison
- The pipeline now possesses a formal timeline and cursor tracking model. Instead of treating all backup/forward and multi-voice movements as general timing risk or timing overlap errors, the parser can programmatically follow voice cursors and chord stack alignments. Same-voice overlaps (invalid timing) are cleanly distinguished from valid multi-voice structures that remain unsupported downstream.

## Current Blocker Classification
- **Top Blocker**: `musicxml_timing`
- **Rationale**: For E2E inputs like `private_input_1`, while we have implemented the voice cursor model to correctly diagnose and classify multi-voice timing versus same-voice overlaps, the files remain blocked by `musicxml_scoreir_polyphony_gate_refused` or `musicxml_timing_risk`. This ensures our gating is extremely safe and conservative, and developer-facing HTML reports now explicitly categorize the exact measures and voices causing the refusal.

## Recommended Next Branch
- **Next Branch**: `feature/private-smoke-refresh-after-musicxml-voice-cursor-v0.1`
- **Goal**: Re-run the local private-safe E2E diagnostic smoke workflow to evaluate the exact updated blocker status, classifications, and counts across `private_input_1` and `private_input_2` using the new voice cursor model.

## Known Limitations
- PDF grouping is strictly conservative and requires born-digital vector tab geometry. No ML layout recognition or OCR is supported.
- Unsafe PDF grouping (partial, missing, ambiguous, or unsupported) and unsafe MusicXML timing strictly block `build_ir` and prevent ScoreIR compilation.
- Scanned/raster PDFs remain unsupported.
- Valid multi-voice MusicXML timing may still be unsupported downstream by build-ir and is gated under `musicxml_scoreir_polyphony_gate_refused`.

## Remaining Risks
- None. All 169 tests are fully passing locally. Whitespace checks are perfectly clean, and schemas are identical to the base branch.

## Explicit Scope Boundaries
- **Do not** commit any private inputs, private outputs, private GP files, private PDFs, private summaries, private HTML diagnostics, or any `work/` contents.
- **Do not** weaken validation/timing gates or tune thresholds to private examples.
- **Do not** add OCR/scanned-PDF/ML support.
- **Do not** push directly to `main`.
