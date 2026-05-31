# Guitar Pro Format Domain Notes

## Purpose

This document defines what `score2gp` needs to preserve when creating a Guitar Pro-compatible result.

It deliberately avoids undocumented binary-layout claims. Unless the repository contains verified implementation evidence or a public specification is cited elsewhere, do not treat internal `.gp`, `.gp5`, `.gpx` or `.gp` container details as known facts.

The architect should specify musical output requirements first, then implementation details second.

## Output goal

The output should be a usable guitar score that preserves musical meaning from the source.

At minimum, the project should aim to preserve:

- title and metadata where safe and available,
- instrument/track identity,
- tuning,
- measures,
- time signatures,
- tempo where available,
- notes,
- rests,
- durations,
- chords,
- voices where supported,
- string/fret positions,
- ties,
- common guitar techniques where supported,
- warnings for unsupported features.

## Guitar-specific data that must not be lost

Pitch is not enough.

For guitar, the same pitch can usually be played at several fretboard positions. A valid conversion should preserve the intended string and fret when tab evidence exists.

Important data:

- string number,
- fret number,
- tuning,
- capo if known,
- track/instrument,
- technique markings,
- rhythmic voice,
- tied/sustained notes.

If string/fret information is unavailable, the system may infer it only under an explicit, tested policy.

## Version and compatibility policy

Guitar Pro has multiple file families and versions.

The project should define which output target is supported before implementing format-specific behaviour.

Recommended policy fields:

- target extension/version,
- library or writer used,
- supported feature subset,
- known unsupported features,
- validation method,
- manual playback/opening check if available,
- compatibility risks.

Do not claim support for a Guitar Pro version until it has been empirically validated.

## Internal representation before writer output

The writer should receive a structured musical model, not raw PDF glyphs.

Recommended model boundary:

```text
PDF evidence
  -> extracted symbols
  -> grouped musical events
  -> validated score model
  -> Guitar Pro writer/exporter
```

The writer should not be responsible for guessing barlines, grouping fret digits or resolving PDF coordinate ambiguity.

## Measures

A Guitar Pro-compatible score should maintain measure order and measure capacity.

Each measure should have:

- time signature,
- barline/repeat metadata if supported,
- one or more beats/events,
- validation status before writing.

If a measure is underfull or overfull, the writer should not hide the issue by padding or truncating unless the task explicitly defines that policy.

## Beats, notes and chords

Guitar Pro-style representations commonly organise music into beats containing one or more notes.

For project purposes:

- a beat has an onset and duration,
- a beat may contain one or more notes,
- each note may have string/fret information,
- a rest is a beat or event with silence,
- multiple voices may require separate streams depending on the writer/library.

The implementation may use different class names. The semantic requirements still apply.

## Techniques

Prioritise reliable support in this order:

1. ties / sustained notes,
2. dead notes,
3. slides,
4. hammer-ons and pull-offs,
5. bends,
6. harmonics,
7. palm mute / let ring,
8. vibrato and expressive markings.

This is a project-priority recommendation, not a universal rule.

Unsupported techniques should be recorded in diagnostics. They should not be silently dropped if the source evidence clearly contains them.

## Validation before writing

Before writing a Guitar Pro-compatible artifact, validate:

- measure durations,
- voice overlaps,
- invalid strings,
- invalid frets,
- missing tuning,
- impossible string/fret/pitch combinations where pitch is known,
- unsupported techniques,
- unresolved timing,
- metadata safety.

## Validation after writing

A successful write is not enough.

Recommended post-write checks:

- file exists and is non-empty,
- writer reports no error,
- generated file can be parsed back by the chosen library if possible,
- smoke conversion preserves expected measure/event counts,
- no private source file was committed,
- diagnostics explain any lost features.

If manual Guitar Pro opening is used as evidence, record it as manual evidence and include exact version/tool used.

## Architect guidance

A task involving Guitar Pro output must define:

- target output format/version,
- library/tool assumptions,
- supported feature subset,
- minimum fixture,
- validation command,
- expected warnings,
- what must not be silently lost,
- what is explicitly out of scope.

## Stop conditions

Stop and report if:

- the output target/version is undefined,
- the writer library cannot represent required semantics,
- conversion would require guessing string/fret data,
- generated files would include private source content,
- validation cannot prove the output is musically meaningful.
