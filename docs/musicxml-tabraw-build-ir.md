# MusicXML And TabRaw Build-IR Groundwork

This phase proves that extraction stages can populate ScoreIR v0.1 without using private or real-world fixtures.

It is intentionally narrow:

- MusicXML supplies bars, timing, voices, rests, pitches, chord symbols, and selected notation details.
- TabRaw supplies spatial fret/string candidates and provenance.
- `build-ir` combines synthetic MusicXML fixtures with synthetic TabRaw fixtures into valid ScoreIR.
- Controlled generated born-digital PDF fixtures prove that `extract-tab` can produce real TabRaw evidence for the same path.

It does not attempt complete OMR, full tablature alignment, or full GPIF output.

## MusicXmlImport

`score2gp.musicxml.parse_musicxml()` parses partwise MusicXML into an internal `MusicXmlImport` model. Inputs may be plain `.musicxml`/`.xml` files or compressed `.mxl` packages.

For `.mxl`, the importer opens the zip package, reads `META-INF/container.xml`, validates the declared rootfile path, and parses that member directly. It does not extract the package to disk. Missing containers, missing rootfiles, unsafe paths, malformed XML, non-zip input, and empty packages fail with clear errors.

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

Unsupported or incomplete constructs are warnings, not hidden assumptions. Repeats, alternate endings, grace notes, and unsupported technical notation are not converted in this phase.

## Timing

ScoreIR uses `DEFAULT_TICKS_PER_QUARTER = 960`.

For each MusicXML note:

```text
duration_ticks = duration_divisions * 960 / measure_divisions
onset_ticks = onset_divisions * 960 / measure_divisions
```

Simple integer mappings are supported. Non-integer onset or duration mappings produce warnings and are truncated for now.

The original MusicXML division values remain in ScoreIR provenance so duration conversion can be inspected later.

Before ScoreIR construction, `build-ir` runs a MusicXML timing preflight. It reports:

- overfull bars where a MusicXML event extends beyond the expected measure length
- same-voice overlaps that would later violate ScoreIR
- underfull bars as warnings
- compound-meter assumptions such as 12/8
- backup/forward cursor movement as import warnings
- divisions changes between measures as informational timing context

Overfull bars and same-voice overlaps are refused before invalid ScoreIR is written. If `--diagnostics-out` is provided, the CLI writes a `build-ir-failure-diagnostics.v0.1` payload with timing issue counts and public-safe MusicXML element identifiers.

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

Uneven-spacing generated PDF smoke command:

```powershell
python -m score2gp.cli extract-tab `
  --out "work/generated_pdf/generated_uneven_spacing_tab.tabraw.json" `
  "tests/fixtures/pdf/generated_uneven_spacing_tab.pdf"
```

Then:

```powershell
python -m score2gp.cli build-ir `
  --musicxml "tests/fixtures/musicxml/generated_uneven_spacing_tab.musicxml" `
  --tabraw "work/generated_pdf/generated_uneven_spacing_tab.tabraw.json" `
  --out "work/generated_pdf/generated_uneven_spacing_tab.ir.json" `
  --diagnostics-out "work/generated_pdf/generated_uneven_spacing_tab.diagnostics.json"
```

The uneven-spacing fixture deliberately keeps the MusicXML rhythm simple while placing two visual fret groups very close together. It exists to prove that diagnostics can report unsafe geometry without blocking ScoreIR generation.

Unstructured generated PDF smoke command:

```powershell
python -m score2gp.cli extract-tab `
  --out "work/generated_pdf/generated_unstructured_tab_text.tabraw.json" `
  "tests/fixtures/pdf/generated_unstructured_tab_text.pdf"
```

This fixture deliberately has extractable fret/chord/technique text but no reliable six-line tab staff geometry. It should preserve candidates with bbox/x/y evidence while leaving system, string, and bar estimates empty. This reproduces the important failure mode "extraction succeeded, grouping failed" using public generated data.

When playable fret candidates exist but system/string/bar grouping is absent, extraction emits `missing_pdf_grouping`. `build-ir` treats that as unsafe input and refuses ScoreIR output rather than consuming ungrouped candidates from a global fallback pool.

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
- refuses overfull or same-voice-overlapping MusicXML before writing invalid ScoreIR
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
- per-bar x-to-onset summaries comparing playable fret x groups with MusicXML pitched onset groups
- candidate x groups, MusicXML onset groups, relative positions, drift/error values, chord-stack flags, ambiguity counts, and `good`/`warning`/`poor`/`unknown` quality labels
- low-confidence flags
- extraction quality flags
- all ScoreIR warnings in JSON form

The per-system summaries show how many candidates were found, how many playable frets matched, and how many non-playable candidates were intentionally ignored. The per-bar summaries include rest/chord event counts and ambiguity flags such as repeated x-position candidates.

For x-to-onset diagnostics, playable candidates are only candidates with parsed fret values. Chord symbols such as `Am` or `D7`, technique text such as `slide` or `PM`, and other nearby text are preserved as evidence but excluded from playable x groups. A vertical stack of fret numbers at the same x position is treated as a playable chord stack only when the grouped candidates are frets on different strings.

Relative drift is computed by normalizing playable x groups and MusicXML pitched onset groups inside their observed ranges. This is intentionally a diagnostic measurement, not full optical calibration. A `good` bar means the current x-order heuristic looks internally consistent for that controlled input. A `warning` or `poor` bar means the sidecar should be inspected before trusting automatic conversion. `unknown` usually means the bar lacks enough playable x or MusicXML onset evidence to measure spacing.

The generated ScoreIR should pass:

```powershell
python -m score2gp.cli validate-ir "work/synthetic/score.ir.json"
```

## Deferred

Still out of scope:

- real Derek Trucks fixture conversion
- multi-part alignment
- robust system/staff detection beyond controlled generated PDFs
- robust tab string inference from detected line positions
- extraction from real commercial/private PDFs
- advanced rhythm, repeats, alternate endings, grace-note semantics, and tempo maps
- TabRaw-derived chord/technique alignment into ScoreIR events
- full optical x-to-onset calibration from page geometry
- GPIF writer expansion

The latest controlled private diagnostic experiment produced only sanitized evidence: PDF extraction found many candidates, but no system/bar/string grouping was inferred, and MusicXML timing risk stopped build-ir before ScoreIR output. Those failure classes are now represented by public fixtures; another private run should check whether native `.mxl` intake and the stricter `missing_pdf_grouping` refusal produce clearer summaries without tuning to private material.
