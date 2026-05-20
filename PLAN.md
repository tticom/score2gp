# PLAN

## Milestone 1: inspectable GP foundation

- Scaffold Python package, tests, docs, and fixtures.
- Define strict ScoreIR models.
- Implement `inspect-gp`, `validate`, and minimal GP7 package writing.
- Generate a minimal public synthetic ScoreIR fixture and template package.

## Milestone 2: PDF diagnostics and born-digital tab extraction

- Improve `inspect-pdf` page classification and rendering.
- Add tab-line/system/barline detection overlays.
- Extract vector text fret numbers, chord symbols, and technique labels with bounding boxes.
- Write `tab_raw.json` with confidence scores and warnings.
- Add a generated born-digital public PDF fixture to prove real `extract-tab` output can feed `build-ir`.
- Add a score-like generated PDF fixture with multiple tab systems, chord-symbol noise, technique text, candidate text, and spacing variation.
- Add an uneven-spacing generated fixture to prove diagnostics expose unsafe visual spacing.

## Milestone 3: timing alignment

- Add optional Audiveris runner and limited MusicXML ingestion.
- Prove synthetic MusicXML + TabRaw alignment with bars, rests, voices, chords, tuplets, selected techniques, and diagnostics.
- Align tab x-positions with MusicXML timing for controlled public fixtures.
- Produce richer ScoreIR with event-level provenance before attempting private real-world fixtures.
- Write `build-ir-diagnostics.v0.1` sidecars so alignment quality can be reviewed before trying private fixtures.
- Extend diagnostics with PDF-derived TabRaw evidence counts and extraction quality flags.
- Add per-system and ignored non-playable candidate diagnostics for PDF-derived TabRaw.
- Add per-bar x-to-onset diagnostics with visual fret groups, MusicXML onset groups, drift/error values, chord-stack flags, ambiguity counts, and quality labels.
- Use the diagnostics to decide when a controlled private fixture is safe to try.
- Run private fixtures only through ignored diagnostic workflows with sanitized summaries.
- Reproduce private failure classes with public fixtures: Audiveris-like MusicXML timing risk and PDF extraction without grouping.
- Refuse overfull MusicXML before writing invalid ScoreIR.
- Parse native Audiveris `.mxl` packages through the main MusicXML importer without unpacking private content to disk.
- Refuse PDF-derived TabRaw with playable candidates but missing system/string/bar grouping before writing ScoreIR.

## Milestone 4: GPIF coverage

- Expand GPIF builder for bends, slides, vibrato, hammer-ons/pull-offs, ties, let-ring, tuplets, grace notes, and multi-voice bars.
- Add semantic comparison against private GP fixtures.
- Document every GPIF assumption.

## Milestone 5: first-pass conversion report

- Implement full `convert` orchestration.
- Produce `warnings.json`, `conversion-report.html`, overlays, raw JSON, ScoreIR, and `.gp`.
- Keep unsupported and guessed features visible.
