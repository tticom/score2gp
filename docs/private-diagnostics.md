# Private Diagnostic Workflow

This workflow is for local evidence gathering only. It does not claim that arbitrary PDF conversion works, and it must not add private score material or generated private outputs to the repository.

## Private Data Locations

Keep private inputs under ignored paths:

- `fixtures/private/`
- `tests/fixtures/private/`

Keep private outputs under ignored paths:

- `work/private/`
- `work/private_diagnostics/`

Private PDFs, GP files, MusicXML/MXL exports, extracted TabRaw, generated ScoreIR, diagnostics JSON, rendered pages, overlays, and reports must stay local.

## Required Inputs

A full diagnostic run needs:

- a private born-digital PDF score that you have permission to process
- a matching MusicXML, XML, or MXL timing file from the same source

If matching MusicXML is missing, run the workflow in extraction-only mode. Do not fake timing and do not infer guitar positions from MusicXML pitch alone.

## Command

```powershell
python scripts/private_diagnostic_smoke.py `
  --pdf "fixtures/private/example.pdf" `
  --musicxml "fixtures/private/example.musicxml" `
  --out-dir "work/private_diagnostics/example"
```

For extraction-only diagnostics:

```powershell
python scripts/private_diagnostic_smoke.py `
  --pdf "fixtures/private/example.pdf" `
  --out-dir "work/private_diagnostics/example"
```

The script writes detailed artifacts under the output directory:

- `extracted.tabraw.json`
- `score.ir.json` when MusicXML build succeeds
- `diagnostics.json` when `build-ir` succeeds
- `summary.json`
- `summary.md`

Only the summary is designed to be public-safe, and it still belongs under ignored `work/` unless explicitly reviewed.

## Summary Fields

The summary uses input basenames only and omits candidate text dumps. It reports:

- total, playable, and non-playable candidate counts
- chord-symbol, technique-text, and unknown-text candidate counts
- inferred system and bar counts
- matched playable candidate count
- unmatched MusicXML event and note counts
- unmatched playable TabRaw candidate count
- ignored non-playable candidate count
- bar quality counts: `good`, `warning`, `poor`, `unknown`
- worst bars by relative visual/timing drift
- bars with missing x evidence, ambiguous x groups, and onset-count mismatches
- validation status
- failure stage and sanitized failure category when build-ir is refused
- MusicXML timing issue counts when available
- recommendation categories such as `missing_pdf_grouping`, `musicxml_timing_risk`, `alignment_not_attempted`, and `validation_failed`
- a recommended next diagnostic action

The most recent controlled private experiment is recorded only as sanitized counts: extraction found many PDF text candidates, but inferred zero systems, zero bars, and zero strings. The matching Audiveris MXL was unpacked locally, but build-ir did not reach alignment because MusicXML timing risk would have produced invalid ScoreIR. No private PDF, MXL, TabRaw, IR, diagnostics, or report content should be committed.

## Reading Quality

`good` means the controlled x-position evidence and MusicXML onset groups agree closely for that bar.

`warning` means the bar may still produce a valid ScoreIR, but alignment evidence is weak, uneven, or ambiguous enough to inspect manually.

`poor` means the current simple x-order alignment is not trustworthy for that bar.

`unknown` means the bar lacks enough playable x evidence or MusicXML onset evidence to judge.

Poor or unknown bars are conversion risks. They should not be hidden or smoothed over.

`missing_pdf_grouping` means extraction found candidates but did not infer enough system/string/bar evidence to align them safely. `musicxml_timing_risk` means the MusicXML timing preflight found an overfull bar or similar structure that would violate ScoreIR. `alignment_not_attempted` means the run stopped before x-to-onset alignment. `validation_failed` means output validation failed and needs public reproduction before private-specific debugging.

## Current Limits

This workflow measures the current extraction and alignment path. It does not add OCR, ML, full optical calibration, GPIF expansion, or arbitrary score support. Chord symbols and technique text are preserved as non-playable evidence, but they are not yet attached to ScoreIR events.
