# Handoff

## Current Branch

- Branch: `feature/ascii-tab-timing-contract-v0.1`
- Base: `main`
- PR #1, PR #3, and PR #4 have been merged into `main`.
- This branch defines public ASCII-tab timing/alignment evidence as a diagnostic contract.
- Do not start symbol attachment on this branch.
- Do not start full ASCII timing alignment or ScoreIR conversion from ASCII tab on this branch.

## Current Capability

- Drawn tab staff detection remains separate from ASCII-tab text detection.
- `extract-tab` detects six-row ASCII-tab blocks using `ascii-tab.v0.1`.
- ASCII-tab fret candidates now include `ascii-timing.v0.1` raw evidence:
  row labels, character spans, column indexes, normalized row positions, aligned bar-separator columns, measure segment IDs where available, timing status, confidence, and warning codes.
- Complete ASCII rows without usable bar separators emit `ascii_tab_timing_unavailable` and `ascii_tab_measure_boundary_missing`.
- Barred/equal-width public fixtures emit `partial_ascii_tab_timing`; this means measure/column evidence exists but musical onset/duration mapping is not safe.
- Uneven or inconsistent ASCII timing fixtures emit `ambiguous_ascii_tab_timing`.
- Malformed fewer-than-six-row ASCII blocks still emit `partial_ascii_tab_grouping`.
- `build-ir` refuses ASCII-tab candidates before ScoreIR output for unavailable, partial, ambiguous, or incomplete ASCII timing evidence.

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
- `ascii-timing.v0.1` provides alignment evidence only; it does not infer durations.
- Chord symbols and technique text are preserved but not musically attached to ScoreIR events.
- GPIF output remains minimal.

## Next Recommended Task

After this branch is reviewed, the next narrow task should design a public MusicXML-to-ASCII alignment proof path that can decide whether `ascii-timing.v0.1` evidence is compatible with actual musical onsets. Keep symbol attachment separate until timing alignment is trustworthy.
