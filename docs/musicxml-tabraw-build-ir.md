# MusicXML And TabRaw Build-IR Groundwork

This phase proves that extraction stages can populate ScoreIR v0.1 without using private or real-world fixtures.

It is intentionally narrow:

- MusicXML supplies bars, timing, voices, rests, pitches, chord symbols, and selected notation details.
- TabRaw supplies spatial fret/string candidates and provenance.
- `build-ir` combines synthetic MusicXML fixtures with synthetic TabRaw fixtures into valid ScoreIR.

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

`extract-tab` now emits `candidates` rather than anonymous text blocks. It still only performs first-pass born-digital text collection; staff, string, and beat alignment remain future work.

Legacy `items` payloads can still be normalized by `score2gp.tabraw.normalize_tabraw_payload()`.

TabRaw candidate IDs are required to be unique. Chord-symbol and technique-text candidates are preserved and reported by `build-ir`, but they are not aligned from TabRaw into events yet.

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
  --musicxml "tests/fixtures/musicxml/rich_guitar_cases.musicxml" `
  --tabraw "tests/fixtures/tabraw/rich_guitar_cases_tabraw.json" `
  --out "work/synthetic/rich_score.ir.json"
```

`--tab` is retained as an alias for `--tabraw`.

Current behavior:

- uses only the first MusicXML part
- creates ScoreIR bars from MusicXML measures
- creates rest events directly from MusicXML rests
- creates pitched events only when TabRaw provides aligned string/fret evidence
- aligns synthetic tab candidates by bar and x-position order
- preserves MusicXML chord symbols on same-onset events
- carries simple MusicXML tuplets and selected note techniques into ScoreIR
- keeps MusicXML and TabRaw provenance on generated notes
- warns when notes cannot be aligned, pitch evidence conflicts, non-fret TabRaw candidates are not aligned, harmonies cannot attach to an event, or extra fret candidates are unused
- uses standard guitar tuning as an explicit placeholder

The generated ScoreIR should pass:

```powershell
python -m score2gp.cli validate-ir "work/synthetic/score.ir.json"
```

## Deferred

Still out of scope:

- real Derek Trucks fixture conversion
- Audiveris `.mxl` package parsing
- multi-part alignment
- robust system/staff detection
- tab string inference from detected line positions
- advanced rhythm, repeats, alternate endings, grace-note semantics, and tempo maps
- TabRaw-derived chord/technique alignment
- GPIF writer expansion

The next architectural checkpoint should add controlled public fixtures that look more like born-digital guitar tab extraction before using private material.
