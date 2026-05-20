# Handoff

## Current Context

- Branch: `feature/scoreir-v0.1-contract`
- Latest local checkpoint commit: `1e07d40 Add native MXL intake and grouping failure safeguards`
- Current diagnostic-report work is intentionally uncommitted unless the user asks to commit.
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
- `extract-tab` now writes `warnings.json` whenever warnings exist.
- Missing or partial PDF grouping now writes `grouping-diagnostics.html` and `overlays/page-*-grouping.png`.
- The grouping report distinguishes extraction success, grouping failure, alignment not attempted, and ScoreIR not written.
- `build-ir` CLI failure payloads can point to sibling grouping diagnostics when the category is `missing_pdf_grouping`.
- Private diagnostic summaries include grouping diagnostic artifact names/counts without exposing private candidate text.

## Verification

- Focused report tests: `python -m pytest tests/test_pdf.py tests/test_report.py tests/test_private_diagnostics.py`: 15 passed

## Remaining Work

- Run full `python -m pytest`, schema export, `validate-ir`, CLI smoke commands, `git diff --check`, and private-safety status checks before any commit.
- Improve PDF grouping heuristics using public fixtures only.
- Add developer-facing styling/thumbnails for grouping reports if useful.
- Continue adding public MusicXML timing-risk fixtures before another private diagnostic experiment.
- Keep GPIF expansion, OCR, ML, and real private conversion out of this phase.
