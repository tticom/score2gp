# Handoff

## Current Branch

- Branch: `feature/ascii-tab-pdf-diagnostics-v0.1`
- Base: `main`
- PR #1 and PR #3 have been merged into `main`.
- This branch characterizes born-digital ASCII-tab PDFs as a separate input class from drawn tab-staff geometry.
- Do not start symbol attachment on this branch.

## Current Capability

- Public PDF grouping v0.1 remains public-fixture-only and born-digital/generated-fixture focused.
- Drawn tab staff detection remains separate from ASCII-tab text detection.
- `extract-tab` can detect six-row ASCII-tab blocks using `ascii-tab.v0.1`.
- Complete ASCII-tab blocks assign row-order strings and extract fret numbers with character-span provenance.
- Inline ASCII technique markers such as slide, hammer-on, pull-off, bend, release, and vibrato are preserved as non-playable technique-text candidates.
- Legend and heading text is not treated as playable fret evidence.
- Malformed fewer-than-six-row ASCII blocks emit `partial_ascii_tab_grouping`.
- Complete ASCII-tab blocks emit `ascii_tab_timing_unavailable` because character positions are not safe timing.
- `build-ir` refuses ASCII-tab candidates before ScoreIR output unless a future phase supplies safe timing/alignment.

## Verification Expected

Run before any commit, push, or review:

- `python -m pytest`
- `python -m score2gp.cli export-schema --out schemas`
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json`
- `git diff --check`
- `git diff -- schemas`

## Private Safety

- The local private ASCII-tab PDF was used only for smoke characterization.
- Do not commit `work/` outputs.
- Do not commit private PDFs, GP files, MXL files, private diagnostic HTML, private overlays, logs, or temporary smoke outputs.
- The only intended tracked private-path item is `fixtures/private/.gitkeep`.
- Public fixtures must stay synthetic and must not copy private titles, URLs, headings, fret sequences, or layout.

## Known Limitations

- No OCR.
- No scanned-PDF support.
- No ML layout recognition.
- No arbitrary commercial score conversion.
- ASCII-tab support is diagnostic/extraction-level only.
- ASCII character positions are not yet mapped to musical timing.
- Chord symbols and technique text are preserved but not musically attached to ScoreIR events.
- GPIF output remains minimal.

## Next Recommended Task

After this branch is reviewed, the next narrow task should define a public timing/alignment contract for ASCII-tab character positions or start a separate public-fixture-only symbol attachment branch. Keep both out of this branch.
