# ScoreIR To GPIF Coverage

The current GP writer is intentionally minimal. It writes a GP7-style zip package with a generated `Content/score.gpif`, but it is not a complete Guitar Pro authoring engine.

## Supported

| ScoreIR Field | GPIF Output | Notes |
| --- | --- | --- |
| `metadata.title` | `Metadata/Title` | Supported |
| `metadata.artist` | `Metadata/Artist` | Supported |
| `metadata.composer` | `Metadata/Composer` | Supported |
| `metadata.album` | `Metadata/Album` | Supported |
| `metadata.transcriber` | `Metadata/Transcriber` | Supported |
| `metadata.copyright` | `Metadata/Copyright` | Supported |
| `tempo.bpm` | `Tempo/Value` | Supported |
| `tempo.text` | `Tempo/Text` | Supported |
| `tracks[].id` | `Track/@id` | Supported |
| `tracks[].name` | `Track/Name` | Supported |
| `tracks[].instrument` | `Track/Instrument` | Supported |
| `tracks[].tuning` | `Track/Tuning/String` | Supported |
| `bars[].time_signature` | `MasterBar/Time` | Supported |
| `bars[].key_signature` | `MasterBar/Key` | Supported |
| `events[].timing.onset_ticks` | `Event/@position` | Converted to a whole-note fraction |
| `events[].timing.duration_ticks` | `Event/@duration` | Converted to a whole-note fraction |
| `events[].timing.voice` | `Event/@voice` | Supported |
| `events[].is_rest` | `Event/@rest` | Supported |
| `events[].chord_symbol` | `Event/Chord` | Supported |
| `notes[].string` | `Note/@string` | Supported |
| `notes[].fret` | `Note/@fret` | Supported |
| `notes[].pitch` | `Note/@pitch` | Supported |
| `confidence` | `@confidence` | Supported on events and notes |

## Partially Supported

| ScoreIR Field | GPIF Output | Warning Behavior |
| --- | --- | --- |
| `slide` | `Technique name="slide"` | Written as a simple tag only |
| `vibrato` | `Technique name="vibrato"` | Written as a simple tag only |
| `hammer-on` | `Technique name="hammer-on"` | Written as a simple tag only |
| `pull-off` | `Technique name="pull-off"` | Written as a simple tag only |
| `tie` | note `tie` attribute plus technique tag | Does not enforce GP-native tie semantics |
| `slur` | note `slur` attribute plus technique tag | Does not enforce GP-native slur semantics |
| `tracks[].capo` | `Track/Capo` | Basic value only |

## Unsupported In The Minimal Writer

The writer emits warnings for these fields or techniques:

| ScoreIR Field | Reason |
| --- | --- |
| `tracks[].tablature_enabled = false` | Minimal writer always emits the same simplified track shape |
| `tracks[].staff_count != 1` | Multiple staves are not modelled |
| `tracks[].midi_program` | MIDI playback details are not written |
| `tracks[].midi_channel` | MIDI playback details are not written |
| `events[].timing.tuplet` | Tuplet engraving/playback is not modelled |
| `events[].timing.grace` | Grace-note timing is not modelled |
| `bend` | Bend points/targets are not written |
| `let-ring` | Spans are not written |
| `palm-mute` | Spans are not written |
| `grace` | Grace note rendering/playback is not written |
| `unsupported` | Preserved in IR only |

## Not Written By Design

These fields are validation/provenance/reporting data and are not expected in minimal GPIF output:

- `conversion`
- `warnings`
- `provenance`
- `source_file_hash`
- PDF bounding boxes
- raw extraction payloads

They should remain in ScoreIR and conversion reports.
