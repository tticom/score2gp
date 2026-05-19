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
- preserve stable candidate IDs
- preserve system/staff/bar/string estimates when known
- preserve x/y evidence for later MusicXML alignment
- keep confidence values visible
- keep uncertain text as candidates rather than forced notes

Status: `tabraw.v0.1` candidate contract implemented. Candidate IDs must be unique. Extraction is still first-pass born-digital text candidate collection only; `build-ir` currently consumes fret candidates and reports chord-symbol or technique-text candidates as preserved but not aligned.

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
- parse uncompressed partwise MusicXML into limited timing, pitch, voice, rest, tie, tuplet, harmony, and selected guitar technique data
- provide timing input for the first synthetic ScoreIR builder

Status: Audiveris wrapper implemented. A limited uncompressed MusicXML parser is implemented for synthetic fixtures. Compressed `.mxl` package parsing, repeat expansion, alternate endings, grace timing, and full MusicXML semantics are not implemented yet.

## ScoreIR

Intended produced by:

```powershell
python -m score2gp.cli build-ir --musicxml work/omr/score.musicxml --tabraw work/tab/tab_raw.json --out score.ir.json
```

Purpose:

- normalize recognised notation and tablature into a strict score contract
- store tracks, tunings, bars, timing, notes, techniques, confidence, and provenance
- be suitable for validation, semantic comparison, correction, and writing

Status: ScoreIR v0.1 schema and validation are implemented. `build-ir` now supports a narrow synthetic MusicXML + TabRaw path. Real PDF-derived alignment is still pending.

Current synthetic alignment details:

- MusicXML provides bar timing, rests, notated duration, tuplets, chord symbols, and selected note techniques.
- TabRaw provides string/fret candidates, consumed by bar and x-position order.
- Pitched ScoreIR events are emitted only when TabRaw provides string/fret evidence.
- Unused fret candidates, non-fret TabRaw candidates, unattached harmonies, and pitch mismatches are explicit warnings.

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
