# ScoreIR v0.1

ScoreIR is the versioned interchange contract used after recognition and before GPIF writing.

It is not a dump of every PDF or OMR detail. It is the normalized musical score representation that humans can inspect, validate, correct, compare, and pass to writers.

Committed schema:

```text
schemas/scoreir.v0.1.schema.json
```

Export the schema:

```powershell
python -m score2gp.cli export-schema --out schemas
```

Validate an IR file:

```powershell
python -m score2gp.cli validate-ir "fixtures/public/tiny_score.ir.json"
```

Compare two IR files semantically:

```powershell
python -m score2gp.cli compare-ir "expected.ir.json" "actual.ir.json"
```

## Top-Level Shape

ScoreIR v0.1 contains:

- `schema_version`: always `0.1.0`
- `metadata`: title, artist, composer, transcriber, copyright, source
- `conversion`: tool/source metadata including source hash, page count, timestamps, and Audiveris version when known
- `tempo`: score tempo
- `tracks`: instruments, tunings, tab/capo/staff/MIDI hints
- `bars`: measures and events
- `warnings`: score-level warnings that should remain visible to users

## Timing

Every event has structured timing:

- `bar_index`
- `onset_ticks`
- `duration_ticks`
- `ticks_per_quarter`
- `voice`
- optional `notated_duration`
- optional `tuplet`
- optional `grace`

Ticks are bar-relative. For the current public fixture, `ticks_per_quarter` is `960`; in 12/8, the bar length is `12 * 960 * 4 / 8 = 5760` ticks.

## Techniques

Techniques are a discriminated union using `kind`:

- `slide`
- `bend`
- `vibrato`
- `hammer-on`
- `pull-off`
- `tie`
- `slur`
- `let-ring`
- `palm-mute`
- `grace`
- `unsupported`

Use `unsupported` when the recognizer sees something real but cannot model it yet. Do not silently drop it.

## Provenance

Events, notes, and warnings can carry provenance entries with:

- `source_stage`: `musicxml`, `pdf-text`, `ocr`, `inferred`, `manual`, `gpif`, or `unknown`
- `page`
- `system_id`
- `staff_id`
- `bar_index`
- `bbox` in PDF coordinates
- `raw_token_id`
- `raw`
- `confidence`

Confidence is always `0.0` to `1.0`. Bounding boxes must use ordered coordinates.

## Semantic Validation

`validate-ir` performs pydantic and semantic checks:

- track references exist
- bar indexes are consistent
- event IDs are unique
- event timing fits inside bars
- events do not overlap in the same track/bar/voice
- rests do not contain notes
- non-rest events contain notes
- strings exist in the track tuning
- pitch equals open-string tuning plus fret
- confidence values are in range
- provenance bounding boxes are valid
- technique payloads match their declared `kind`
- technique links reference known events when a link is present

The validator is intended to return musician-readable messages such as:

```text
event 'bad-pitch' note string 2 fret 3 has pitch 61; expected 62 from tuning
```

## Current Non-Goals

ScoreIR v0.1 does not yet define:

- a complete MusicXML import mapping
- a complete tab-alignment model
- every Guitar Pro technique parameter
- detailed layout correction tooling

Those should build on this contract rather than bypass it.
