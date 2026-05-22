# Handoff

## Current Branch

- Branch: `feature/ascii-musicxml-alignment-proof-v0.1`
- Base: `main`
- PR #1, PR #3, PR #4, and PR #5 have been merged into `main`.
- This branch defines a public ASCII/MusicXML alignment proof sidecar.
- Do not start symbol attachment on this branch.
- Do not start full ASCII-to-ScoreIR conversion on this branch.

## Current Capability

- Drawn tab staff detection remains separate from ASCII-tab text detection.
- `extract-tab` detects six-row ASCII-tab blocks using `ascii-tab.v0.1`.
- ASCII-tab fret candidates include `ascii-timing.v0.1` raw evidence with row labels, character spans, column indexes, normalized positions, bar-separator columns, measure segment IDs, timing status, confidence, and warning codes.
- `ascii-musicxml-alignment.v0.1` compares ASCII measure segment/column evidence with MusicXML onset positions in controlled public fixture pairs.
- Alignment status can be `compatible`, `partial`, `ambiguous`, `incompatible`, or `unavailable`.
- Timing-risk MusicXML blocks alignment before matching.
- The new CLI command is `python -m score2gp.cli align-ascii-musicxml --tab <tabraw.json> --musicxml <score.musicxml> --out <dir>`.
- The command writes `ascii_musicxml_alignment.json`, `warnings.json` when warnings exist, and `alignment-diagnostics.html`.
- `build-ir` still refuses ASCII-tab candidates by default. It refuses unavailable, partial, ambiguous, and incompatible sidecars, and it also refuses compatible sidecars with `ascii_scoreir_writing_not_implemented`.

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
- The alignment proof does not infer durations, attach techniques, or authorize ScoreIR writing.
- Chord symbols and technique text are preserved but not musically attached to ScoreIR events.
- GPIF output remains minimal.

## Next Recommended Task

After this branch is reviewed, the next narrow task should design the explicit public ScoreIR-writing gate for ASCII TabRaw, starting with a tiny compatible fixture and keeping conservative refusal for every unsupported timing, technique, and symbol case.
