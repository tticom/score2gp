# MusicXML Model

## Purpose

This document defines the MusicXML-shaped domain model relevant to `score2gp`.

It is not a full MusicXML specification. It describes the concepts the project should understand when using MusicXML as an input, output, comparison format or intermediate representation.

## Why MusicXML matters

MusicXML is useful because it represents symbolic music rather than rendered page layout.

For this project, MusicXML-shaped data can help with:

- representing measures,
- representing notes and rests,
- preserving durations,
- representing voices,
- representing pitches,
- comparing expected musical output,
- creating synthetic fixtures,
- validating rhythm and measure structure.

PDF extraction should not assume that the PDF contains MusicXML-like structure. MusicXML is a helpful target model, not a description of what is present in a PDF.

## Core hierarchy

A practical model contains:

```text
score
  part
    measure
      attributes
      directions
      note/rest/chord events
      backup/forward time movement
      barline/repeat metadata
```

For guitar music, a part may correspond to a guitar instrument. A part may contain one or more staves, and may contain tablature-related technical information depending on the source.

## Measures

A measure is the symbolic equivalent of a bar.

It should preserve:

- measure number or sequence index,
- time signature in force,
- key signature where relevant,
- clef where relevant,
- divisions or duration unit,
- ordered musical events,
- barline and repeat information,
- validation status.

Do not rely only on printed measure numbers. PDFs may omit them or repeat them across systems.

## Durations and divisions

A symbolic model usually needs a duration unit. MusicXML commonly uses a `divisions` concept: durations are measured as integer units relative to a quarter note.

The project can use its own internal unit, but it must be able to represent durations exactly and convert safely.

Avoid using floating point for symbolic duration.

## Notes

A note-like event should be able to represent:

- pitch,
- rest,
- chord membership,
- duration,
- voice,
- staff,
- ties,
- articulations,
- technical notation,
- source evidence where derived from PDF.

For guitar tab, note data should also preserve string and fret when known.

Pitch alone is not enough for guitar conversion because the same pitch can often be played on multiple strings.

## Chords

A chord contains multiple notes at the same onset.

In a MusicXML-shaped stream, chord notes may be represented as separate note elements with chord markers. Internally, the project may choose a more explicit chord object.

Whichever representation is used, validation must preserve:

- common onset,
- note durations,
- voice ownership,
- string/fret identities if known.

## Voices

Voices represent independent rhythmic streams.

A measure may contain multiple voices. A voice should be validated independently against the measure capacity unless the representation uses explicit time movement operations.

A conversion pipeline must not merge voices merely because notes are visually close.

## Backup and forward movement

Some symbolic representations use explicit time movement to encode multiple voices.

Conceptually:

- forward movement advances the current time position,
- backup movement rewinds the current time position to encode another voice or staff.

The internal model does not need to expose the same mechanism, but it must preserve equivalent timing relationships.

## Attributes

Measure attributes can include:

- time signature,
- key signature,
- divisions,
- clef,
- staff details,
- transposition,
- tuning metadata.

For guitar, transposition matters because written notation may sound one octave lower than written. See `guitar_notation_guide.md` for the basic notation convention.

## Directions and text

Directions may include:

- tempo,
- rehearsal marks,
- dynamics,
- technique text,
- section labels,
- expression text.

Directions should be preserved when recognised, but they should not be confused with note events.

## Technical notation for guitar

Guitar-relevant technical information may include:

- string,
- fret,
- bend,
- slide,
- hammer-on,
- pull-off,
- harmonic,
- palm mute,
- let ring,
- fingering.

Unsupported technical notation should produce warnings rather than disappearing silently.

## Use as a test oracle

MusicXML or a simplified MusicXML-shaped model can be used as an oracle for tests.

Good oracle checks:

- measure count,
- time signatures,
- note/rest count,
- durations,
- onsets,
- voices,
- string/fret pairs,
- ties,
- warnings.

Weak oracle checks:

- exact XML formatting,
- ordering that is not semantically meaningful,
- cosmetic layout details,
- private fixture-specific filenames.

## Architect guidance

When writing tasks involving MusicXML, specify whether the goal is:

- parse MusicXML,
- emit MusicXML,
- compare against MusicXML,
- use MusicXML-shaped internal concepts,
- convert MusicXML to Guitar Pro,
- use MusicXML only as a test fixture.

Those are different tasks and should not be blurred.
