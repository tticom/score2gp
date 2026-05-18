# Intermediate Contracts

The project is a staged pipeline. Each stage should write files a human can inspect and, eventually, correct.

## PdfInspection

Produced by:

```powershell
python -m score2gp.cli inspect-pdf input.pdf --out work/inspect
```

Current file:

```text
work/inspect/inspect_pdf.json
```

Purpose:

- classify the PDF as born-digital, raster/scanned, or mixed
- render page images
- record page dimensions
- extract text blocks and bounding boxes when available
- preserve enough data for diagnostic overlays

Status: implemented as a basic diagnostic contract.

## TabRaw

Produced by:

```powershell
python -m score2gp.cli extract-tab input.pdf --out work/tab
```

Current file:

```text
work/tab/tab_raw.json
```

Purpose:

- hold candidate fret numbers, chord symbols, and technique text
- preserve source page and bounding boxes
- keep confidence values visible
- keep uncertain text as candidates rather than forced notes

Status: first-pass born-digital text candidate extraction only.

## MusicXmlImport

Produced by:

```powershell
python -m score2gp.cli omr input.pdf --out work/omr --audiveris "C:\Program Files\Audiveris\Audiveris.exe"
```

Current files:

```text
work/omr/*.mxl
work/omr/*.omr
work/omr/audiveris.log
work/omr/warnings.json
```

Purpose:

- use Audiveris for standard notation OMR
- capture logs and warnings
- provide MusicXML/MXL timing input for a later ScoreIR builder

Status: Audiveris wrapper implemented. MusicXML parsing is not implemented yet.

## ScoreIR

Intended produced by:

```powershell
python -m score2gp.cli build-ir --musicxml work/omr/score.mxl --tab work/tab/tab_raw.json --out score.ir.json
```

Purpose:

- normalize recognised notation and tablature into a strict score contract
- store tracks, tunings, bars, timing, notes, techniques, confidence, and provenance
- be suitable for validation, semantic comparison, correction, and writing

Status: ScoreIR v0.1 schema and validation are implemented. `build-ir` is not implemented yet.

## ConversionReport

Produced by:

```powershell
python -m score2gp.cli convert input.pdf --template fixtures/templates/minimal_gp7.gp --out output.gp --workdir work/run1
```

Current files:

```text
work/run1/warnings.json
work/run1/conversion-report.html
```

Purpose:

- summarize recognised items
- list guessed items
- list unsupported items
- preserve warnings rather than hiding uncertainty

Status: basic scaffold implemented.

## Contract Rule

Every stage should either read/write ScoreIR or read/write a clearly documented derivative listed here. Recognition uncertainty belongs in the data, not in console-only output.
