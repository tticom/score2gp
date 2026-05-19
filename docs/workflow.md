# Workflow

This document describes the intended staged workflow from an owned PDF score to a Guitar Pro `.gp` package.

The full PDF-to-GP workflow is not complete yet. The current project can inspect PDFs, run Audiveris, parse a limited uncompressed MusicXML subset, build ScoreIR from synthetic MusicXML plus TabRaw fixtures, inspect/write minimal GP packages, and validate generated packages. Real PDF-derived MusicXML/tab alignment is still pending.

## 1. Start From The Project Directory

```powershell
cd C:\Users\niall\src\Python\score2gp
```

Use the module form unless `score2gp.exe` is on `PATH`:

```powershell
python -m score2gp.cli --help
```

## 2. Inspect The Input PDF

Render pages, detect whether the PDF appears born-digital or raster, and extract text coordinates:

```powershell
python -m score2gp.cli inspect-pdf "fixtures/private/Derek Trucks BB King.pdf" `
  --out "work/derek/inspect"
```

Outputs:

```text
work/derek/inspect/inspect_pdf.json
work/derek/inspect/pages/page-001.png
work/derek/inspect/pages/page-002.png
```

Current status: implemented as basic PDF diagnostics.

## 3. Run Audiveris OMR

Audiveris is optional and focuses on standard notation, not complete guitar tablature extraction.

```powershell
python -m score2gp.cli omr "fixtures/private/Derek Trucks BB King.pdf" `
  --out "work/derek/omr" `
  --audiveris "C:\Program Files\Audiveris\Audiveris.exe"
```

Outputs:

```text
work/derek/omr/Derek Trucks BB King.mxl
work/derek/omr/Derek Trucks BB King.omr
work/derek/omr/audiveris.log
work/derek/omr/warnings.json
```

Current status: implemented as an Audiveris batch wrapper.

## 4. Extract Tablature Candidates

Extract born-digital text candidates for fret numbers, chord symbols, and technique labels:

```powershell
python -m score2gp.cli extract-tab "fixtures/private/Derek Trucks BB King.pdf" `
  --out "work/derek/tab"
```

Outputs:

```text
work/derek/tab/tab_raw.json
work/derek/tab/inspect/inspect_pdf.json
work/derek/tab/inspect/pages/*.png
```

Current status: first-pass candidate extraction only. It writes `tabraw.v0.1` candidates with stable IDs, bounding boxes, x/y evidence, confidence, and nullable staff/string/bar estimates. It does not yet perform full tab staff/string/beat alignment.

## 5. Build ScoreIR

Synthetic proof command:

```powershell
python -m score2gp.cli build-ir `
  --musicxml "tests/fixtures/musicxml/tiny_single_bar.musicxml" `
  --tabraw "tests/fixtures/tabraw/tiny_single_bar_tabraw.json" `
  --out "work/synthetic/score.ir.json"
```

Richer synthetic diagnostic command:

```powershell
python -m score2gp.cli build-ir `
  --musicxml "tests/fixtures/musicxml/rich_guitar_cases.musicxml" `
  --tabraw "tests/fixtures/tabraw/rich_guitar_cases_tabraw.json" `
  --out "work/synthetic/rich_score.ir.json"
```

Alignment diagnostics sidecar:

```powershell
python -m score2gp.cli build-ir `
  --musicxml "tests/fixtures/musicxml/tiny_multibar.musicxml" `
  --tabraw "tests/fixtures/tabraw/tiny_multibar_tabraw.json" `
  --out "work/synthetic/multibar.ir.json" `
  --diagnostics-out "work/synthetic/multibar.diagnostics.json"
```

Future real-input command:

```powershell
python -m score2gp.cli build-ir `
  --musicxml "work/derek/omr/Derek Trucks BB King.musicxml" `
  --tabraw "work/derek/tab/tab_raw.json" `
  --out "work/derek/score.ir.json"
```

Current status: implemented only for limited synthetic fixtures. It uses MusicXML for measure timing, rests, voices, chords, backup/forward timing, chord symbols, tuplets, and selected note techniques. It uses TabRaw for string/fret candidates and simple bar/x-order alignment. It emits warnings for unused candidates, non-fret TabRaw candidates that are preserved but not aligned, missing tab evidence, and pitch mismatches. The optional diagnostics file reports imported, matched, and unmatched counts plus per-bar summaries. It uses standard guitar tuning as an explicit placeholder. Private real-world fixture alignment is still deferred.

## 6. Write Guitar Pro Package

Once `score.ir.json` exists, write a GP7-style package:

```powershell
python -m score2gp.cli write-gp "work/derek/score.ir.json" `
  --template "fixtures/templates/minimal_gp7.gp" `
  --out "work/derek/output.gp"
```

Current status: implemented for hand-authored ScoreIR fixtures and a minimal GPIF subset.

Working example today:

```powershell
python -m score2gp.cli write-gp "fixtures/public/tiny_score.ir.json" `
  --template "fixtures/templates/minimal_gp7.gp" `
  --out "work/tiny/output.gp"
```

## 7. Validate The Output

```powershell
python -m score2gp.cli validate "work/tiny/output.gp"
```

For future Derek output:

```powershell
python -m score2gp.cli validate "work/derek/output.gp"
```

Current status: implemented for zip structure and GPIF XML well-formedness.

## 8. Inspect Or Compare GP Files

Inspect a GP file:

```powershell
python -m score2gp.cli inspect-gp "fixtures/private/Derek Trucks BB King.gp"
```

Compare semantic features:

```powershell
python -m score2gp.cli compare "expected.gp" "actual.gp"
```

Current status: implemented as a semantic summary comparison, not byte-for-byte comparison.

## 9. One-Command Convert

Intended command:

```powershell
python -m score2gp.cli convert "fixtures/private/Derek Trucks BB King.pdf" `
  --template "fixtures/templates/minimal_gp7.gp" `
  --out "work/derek/output.gp" `
  --workdir "work/derek"
```

Current status: scaffold only. It writes diagnostics and a conversion report, but it does not yet produce a real PDF-derived GP file.

## Current Stage Summary

| Stage | Command | Status |
| --- | --- | --- |
| PDF diagnostics | `inspect-pdf` | Implemented |
| Standard notation OMR | `omr` | Implemented via Audiveris |
| Tab candidate extraction | `extract-tab` | First pass |
| ScoreIR alignment | `build-ir` | Synthetic proof path |
| GP writing | `write-gp` | Minimal subset implemented |
| Validation | `validate` | Implemented |
| Full conversion | `convert` | Scaffold only |

The project should keep uncertainty visible at every stage. Unsupported features should become warnings or report items, not silent omissions.
