# Handoff

## Current Context

- Branch: `feature/scoreir-v0.1-contract`
- Latest pushed commit before this work: `08b1d6f Add timing and grouping failure diagnostics`
- Current work is intentionally uncommitted unless the user asks to commit.
- Private fixtures and diagnostic outputs must remain ignored and uncommitted.

## Implemented In This Working Tree

- Native compressed `.mxl` parsing in `score2gp.musicxml`.
- `.mxl` rootfile resolution through `META-INF/container.xml` without extracting to disk.
- Clear `.mxl` failures for missing container files, missing rootfiles, unsafe rootfile paths, malformed/non-zip packages, malformed root XML, and empty archives.
- Native `.mxl` intake through `build-ir`.
- Private diagnostic runner now passes `.mxl` inputs directly to the importer instead of writing `prepared.musicxml`.
- Public PDF grouping failure diagnostics now emit `missing_pdf_grouping`.
- `build-ir` refuses TabRaw with playable fret candidates but missing system/string/bar grouping, so ungrouped PDF text cannot be consumed as notes.
- Private diagnostic summaries now include grouping status, grouping warning codes, warning counts, and risk details for refused build-ir runs.

## Verification

- `python -m pytest`: 65 passed

## Remaining Work

- Run final schema export, CLI smoke commands, `git diff --check`, and private-safety status checks before any commit.
- Improve PDF grouping heuristics using public fixtures only.
- Add report/overlay views for extraction-succeeded/grouping-failed cases.
- Continue adding public MusicXML timing-risk fixtures before another private diagnostic experiment.
- Keep GPIF expansion, OCR, ML, and real private conversion out of this phase.
