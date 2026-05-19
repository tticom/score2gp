# MusicXML And TabRaw Build-IR Groundwork

This phase proves that extraction stages can populate ScoreIR v0.1 without using private or real-world fixtures.

It is intentionally narrow:

- MusicXML supplies bars, timing, voices, rests, pitches, chord symbols, and selected notation details.
- TabRaw supplies spatial fret/string candidates and provenance.
- `build-ir` combines synthetic MusicXML fixtures with synthetic TabRaw fixtures into valid ScoreIR.
- Controlled generated born-digital PDF fixtures prove that `extract-tab` can produce real TabRaw evidence for the same path.

It does not attempt complete OMR, full tablature alignment, or full GPIF output.

## MusicXmlImport

`score2gp.musicxml.parse_musicxml()` parses uncompressed partwise MusicXML into an internal `MusicXmlImport` model.

Currently represented:

- metadata: title, composer, rights, source path
- tempo when a simple metronome or `sound tempo` value is present
- parts and part names
- measures with divisions, time signature, and key fifths
- notes and rests
- pitch step, alter, octave, MIDI pitch, and display name
- duration in MusicXML divisions
- onset in MusicXML divisions
- voice and staff when present
- chord flag
- tie start/stop
- simple tuplets from `time-modification`
- harmony/chord symbols from simple `harmony` elements
- selected guitar/phrase techniques: slide, bend, vibrato text, hammer-on, pull-off, and slur
- source element path for debugging

Unsupported or incomplete constructs are warnings, not hidden assumptions. Repeats, alternate endings, grace notes, unsupported technical notation, and compressed `.mxl` packages are not converted in this phase.

## Timing

ScoreIR uses `DEFAULT_TICKS_PER_QUARTER = 960`.

For each MusicXML note:

```text
duration_ticks = duration_divisions * 960 / measure_divisions
onset_ticks = onset_divisions * 960 / measure_divisions
```

Simple integer mappings are supported. Non-integer onset or duration mappings produce warnings and are truncated for now.

The original MusicXML division values remain in ScoreIR provenance so duration conversion can be inspected later.

## TabRaw

TabRaw is now a documented candidate contract with schema version `tabraw.v0.1`.

Each candidate preserves:

- stable candidate ID
- page, system, staff, bar, line, and string estimates where known
- raw text
- parsed fret value when confidently available
- x/y position and PDF-space bounding box when available
- confidence
- source stage and raw payload

`extract-tab` now emits `candidates` rather than anonymous text blocks. It reads born-digital PDF word boxes and, when vector page geometry looks like six-line tab systems, adds heuristic system, staff, string, and global bar estimates. Text above or near a detected tab system can keep system/bar evidence without being assigned to a string. These estimates are evidence, not truth: they should be reviewed through TabRaw JSON and build diagnostics before being trusted.

Controlled generated PDF smoke command:

```powershell
python -m score2gp.cli extract-tab `
  --out "work/generated_pdf/generated_tiny_tab.tabraw.json" `
  "tests/fixtures/pdf/generated_tiny_tab.pdf"
```

Then:

```powershell
python -m score2gp.cli build-ir `
  --musicxml "tests/fixtures/musicxml/generated_tiny_tab.musicxml" `
  --tabraw "work/generated_pdf/generated_tiny_tab.tabraw.json" `
  --out "work/generated_pdf/generated_tiny_tab.ir.json" `
  --diagnostics-out "work/generated_pdf/generated_tiny_tab.diagnostics.json"
```

Score-like generated PDF smoke command:

```powershell
python -m score2gp.cli extract-tab `
  --out "work/generated_pdf/generated_scorelike_tab.tabraw.json" `
  "tests/fixtures/pdf/generated_scorelike_tab.pdf"
```

Then:

```powershell
python -m score2gp.cli build-ir `
  --musicxml "tests/fixtures/musicxml/generated_scorelike_tab.musicxml" `
  --tabraw "work/generated_pdf/generated_scorelike_tab.tabraw.json" `
  --out "work/generated_pdf/generated_scorelike_tab.ir.json" `
  --diagnostics-out "work/generated_pdf/generated_scorelike_tab.diagnostics.json"
```

The score-like fixture has two tab systems, four global bars, chord symbols, technique text, candidate text, multi-digit frets, and chord-like vertical stacks. It is still controlled and generated.

Legacy `items` payloads can still be normalized by `score2gp.tabraw.normalize_tabraw_payload()`.

TabRaw candidate IDs are required to be unique. Chord-symbol, technique-text, and candidate-text candidates are preserved and reported by `build-ir`, but they are not consumed as playable fret events.

## build-ir

The current `build-ir` implementation requires both inputs:

```powershell
python -m score2gp.cli build-ir `
  --musicxml "tests/fixtures/musicxml/tiny_single_bar.musicxml" `
  --tabraw "tests/fixtures/tabraw/tiny_single_bar_tabraw.json" `
  --out "work/synthetic/score.ir.json"
```

Richer synthetic smoke command:

```powershell
python -m score2gp.cli build-ir `
  --musicxml "tests/fixtures/musicxml/tiny_multibar.musicxml" `
  --tabraw "tests/fixtures/tabraw/tiny_multibar_tabraw.json" `
  --out "work/synthetic/multibar.ir.json" `
  --diagnostics-out "work/synthetic/multibar.diagnostics.json"
```

`--tab` is retained as an alias for `--tabraw`.

Current behavior:

- uses only the first MusicXML part
- creates ScoreIR bars from MusicXML measures
- creates rest events directly from MusicXML rests
- creates pitched events only when TabRaw provides aligned string/fret evidence
- aligns synthetic tab candidates by bar and x-position order
- treats repeated or near-repeated x-position candidates within a MusicXML chord event as stacked notes
- preserves MusicXML chord symbols on same-onset events
- carries simple MusicXML tuplets and selected note techniques into ScoreIR
- keeps MusicXML and TabRaw provenance on generated notes
- warns when notes cannot be aligned, pitch evidence conflicts, non-fret TabRaw candidates are not aligned, harmonies cannot attach to an event, or extra fret candidates are unused
- uses standard guitar tuning as an explicit placeholder

## Diagnostics

`build-ir` can write a sidecar diagnostics file with `--diagnostics-out`. This deliberately stays outside ScoreIR so the interchange schema remains stable.

The diagnostics contract is `build-ir-diagnostics.v0.1` and records:

- MusicXML event counts imported
- TabRaw candidate counts loaded, matched, unmatched, and ignored as non-playable
- fret/non-fret candidate counts
- chord-symbol, technique-text, and unknown candidate counts
- counts for candidates with bounding boxes, x/y positions, inferred systems, inferred strings, and inferred bars
- TabRaw source-stage counts
- unmatched MusicXML event and note counts
- unsupported construct warning codes
- per-system extraction/alignment summaries
- per-bar alignment summaries
- low-confidence flags
- extraction quality flags
- all ScoreIR warnings in JSON form

The per-system summaries show how many candidates were found, how many playable frets matched, and how many non-playable candidates were intentionally ignored. The per-bar summaries include rest/chord event counts and ambiguity flags such as repeated x-position candidates.

The generated ScoreIR should pass:

```powershell
python -m score2gp.cli validate-ir "work/synthetic/score.ir.json"
```

## Deferred

Still out of scope:

- real Derek Trucks fixture conversion
- Audiveris `.mxl` package parsing
- multi-part alignment
- robust system/staff detection beyond controlled generated PDFs
- robust tab string inference from detected line positions
- extraction from real commercial/private PDFs
- advanced rhythm, repeats, alternate endings, grace-note semantics, and tempo maps
- TabRaw-derived chord/technique alignment into ScoreIR events
- real optical x-to-onset calibration from page geometry
- GPIF writer expansion

The next architectural checkpoint should add x-to-onset diagnostics and then try a controlled private fixture only after the public generated path remains stable.
