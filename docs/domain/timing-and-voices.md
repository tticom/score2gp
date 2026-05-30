# Timing and Voices

## Purpose

This document defines how `score2gp` should reason about musical time, durations and voices.

It builds on `guitar_notation_guide.md`, which defines basic note values, bars/measures, rests and dotted durations.

## Core timing model

Use rational durations, not floating-point durations, for internal musical time.

Recommended examples:

| Duration | Fraction of semibreve / whole note |
|---|---:|
| Semibreve / whole note | 1 |
| Minim / half note | 1/2 |
| Crotchet / quarter note | 1/4 |
| Quaver / eighth note | 1/8 |
| Semiquaver / sixteenth note | 1/16 |
| Demisemiquaver / thirty-second note | 1/32 |

The implementation may use another internal unit such as ticks or divisions, but it must preserve exact fractional relationships.

## Bars and measure capacity

Each bar has an expected duration derived from the active time signature.

For example:

| Time signature | Expected bar capacity |
|---|---:|
| 4/4 | 4 crotchet beats |
| 3/4 | 3 crotchet beats |
| 6/8 | 6 quaver beats |
| 12/8 | 12 quaver beats |

The notes and rests assigned to a voice in a bar should normally add up to the bar capacity.

Exceptions exist, including:

- pickup/anacrusis bars,
- incomplete final bars,
- hidden voices,
- cadenzas or non-metered notation,
- editorial layout shortcuts,
- repeat endings,
- grace notes,
- notation extraction errors.

The validator should distinguish expected exceptions from structural errors.

## Dotted durations

A dot adds half the value of the note or rest it follows.

Examples:

- dotted minim / dotted half note = minim + crotchet,
- dotted crotchet / dotted quarter note = crotchet + quaver,
- dotted quaver / dotted eighth note = quaver + semiquaver.

Double and triple dots may occur in music generally. If unsupported, they should produce explicit warnings rather than incorrect durations.

## Tuplets

Tuplets compress or expand a group of notes into the duration normally occupied by a different number of notes.

The parser should not approximate tuplets with floating-point durations.

A tuplet representation should capture:

- actual number of notes,
- normal number of notes,
- base note value if known,
- start and end range,
- affected voice,
- confidence/source evidence.

If the notation only shows a bracket or number and the affected notes cannot be identified reliably, the system should warn and avoid pretending the rhythm is certain.

## Voices

A voice is an independent rhythmic stream within a staff or tab system.

Multiple voices may occur on the same staff or tab line. Guitar notation commonly uses voices to represent sustained bass notes together with moving upper notes.

A voice should have:

- a measure-local sequence of events,
- onset positions,
- durations,
- rests or implicit gaps where needed,
- note/chord events,
- ties where applicable.

## Chords

A chord is a set of notes sharing the same onset in the same voice.

A chord may have one duration even if individual notes are displayed on different strings.

If notes visually align but have conflicting stems or rhythmic notation, treat this as possible multi-voice material rather than forcing a single chord.

## Rests and gaps

A rest is explicit silence.

A gap is missing or unrepresented time.

Do not treat gaps as rests unless the notation supports that interpretation. Gaps may indicate extraction failure, hidden rests, alternate voices or layout spacing.

The pipeline should be able to represent:

- explicit rests,
- inferred rests,
- unknown gaps,
- ignored grace-note time,
- validation errors.

## Ties and sustained notes

A tie extends the same pitch across durations or barlines.

In guitar tab, tied notes may appear as repeated fret numbers, parentheses, curved markings or staff notation ties. These signals are not always extracted cleanly from PDFs.

The representation should distinguish:

- re-struck note,
- sustained tied note,
- held note shown again for readability,
- unknown continuation.

## Tempo

Tempo affects playback speed but not symbolic duration.

Timing validation should work without converting everything into seconds.

Tempo markings may still matter for output quality and should be preserved when recognised.

## Repeat structures

Repeats, first/second endings, codas and segnos affect playback order but not the symbolic duration of a single written measure.

Initial conversion may flatten, ignore or warn on repeat structures, but the policy must be explicit.

Do not silently duplicate measures or drop endings without diagnostic evidence.

## Timing validation categories

Recommended categories:

- `ok`: measure and voices are internally consistent.
- `incomplete`: known missing data prevents full validation.
- `overfull_measure`: total duration exceeds measure capacity.
- `underfull_measure`: total duration is below measure capacity without accepted exception.
- `voice_overlap`: events in the same voice overlap unexpectedly.
- `unknown_duration`: event lacks a safe duration.
- `tuplets_unsupported`: tuplet evidence exists but is not represented.
- `conflicting_evidence`: staff, tab or layout evidence disagree.
- `unsupported_notation`: known symbol class exists but is not implemented.

## Architect guidance

A timing task is not complete because a file is produced. It is complete when the timing model can be validated against a meaningful fixture and the diagnostic output explains uncertainty.

Every timing-related task should specify:

- the expected time signature,
- target measures,
- expected event durations,
- voice behaviour,
- known exceptions,
- exact validation checks,
- what warnings are acceptable.
