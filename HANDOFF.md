# Handoff

## Current Branch

- Branch: `feature/ascii-scoreir-writing-gate-v0.1`
- Base: `main`
- PR #1, PR #3, PR #4, PR #5, and PR #6 have been merged into `main`.
- This branch defines the explicit public ASCII TabRaw to ScoreIR writing gate.
- Do not start symbol attachment on this branch.
- Do not broaden ASCII-to-ScoreIR conversion beyond the tiny controlled public gate.

## Current Capability

- Drawn tab staff detection remains separate from ASCII-tab text detection.
- `extract-tab` detects six-row ASCII-tab blocks using `ascii-tab.v0.1`.
- ASCII-tab fret candidates include `ascii-timing.v0.1` raw evidence with row labels, character spans, column indexes, normalized positions, bar-separator columns, measure segment IDs, timing status, confidence, and warning codes.
- `ascii-musicxml-alignment.v0.1` compares ASCII measure segment/column evidence with MusicXML onset positions in controlled public fixture pairs.
- `ascii-scoreir-gate.v0.1` allows ScoreIR output only for one tiny public compatible fixture.
- Durations and rests come from MusicXML. Strings and frets come from ASCII TabRaw.
- The gate requires safe MusicXML timing, a compatible alignment sidecar, one-to-one candidate mappings, string/fret evidence, known MusicXML measure/onset evidence, monophonic notes, and no unsupported technique/symbol/chord/polyphony requirements.
- Missing sidecars, unavailable/partial/ambiguous/incompatible sidecars, broad compatible examples outside the tiny gate, unsupported techniques, missing string/fret evidence, and MusicXML timing risk all refuse before ScoreIR output.
- Build diagnostics now include `ascii_scoreir_gate_status`, reason codes, candidate counts, aligned candidate counts, output event count, and whether ScoreIR was written.

## Verification Expected

Run before any commit, push, or review:

- `python -m pytest`
- `python -m score2gp.cli export-schema --out schemas`
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json`
- `git diff --check`
- `git diff -- schemas`

## Private Safety

- Do not use private PDFs as regression fixtures.
- Do not commit `work/` outputs.
- Do not commit private PDFs, GP files, MXL files, private diagnostic HTML, private overlays, logs, or temporary smoke outputs.
- The only intended tracked private-path item is `fixtures/private/.gitkeep`.
- Public fixtures must stay synthetic and must not copy private titles, URLs, headings, fret sequences, or layout.

## Known Limitations

- No OCR.
- No scanned-PDF support.
- No ML layout recognition.
- No arbitrary commercial score conversion.
- ASCII character columns are not musical timing by themselves.
- `ascii-musicxml-alignment.v0.1` proves only whether controlled ASCII column evidence is compatible with MusicXML onsets.
- `ascii-scoreir-gate.v0.1` is proven only on a tiny synthetic monophonic fixture.
- The gate does not infer durations from ASCII columns, attach techniques, support chord symbols, support polyphony, or broaden GPIF output.
- Chord symbols and technique text are preserved but not musically attached to ScoreIR events.
- GPIF output remains minimal.

## Next Recommended Task

After this branch is reviewed, the next narrow task should add more public refusal fixtures and human-facing diagnostics for ASCII gate edge cases before any private smoke attempt.
