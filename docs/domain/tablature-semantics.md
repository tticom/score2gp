# Tablature Semantics

## Purpose

This document defines the domain meaning of guitar tablature for `score2gp`.

It is not a renderer specification. It explains what must be understood and preserved when converting a guitar score from PDF-derived evidence into an internal representation and then into an output format such as Guitar Pro.

## Core model

A tablature event should capture at least:

- string number,
- fret number or non-pitched marker,
- musical time position,
- duration where known or inferable,
- voice where known or inferable,
- technique annotations where recognised,
- confidence and source evidence where practical.

## String order

In standard six-string guitar tablature, the top printed tab line represents the highest-pitched string and the bottom printed tab line represents the lowest-pitched string.

For standard tuning this usually means:

| Printed tab line | Guitar string | Standard tuning |
|---:|---:|---|
| 1, top line | 1st string | E4 |
| 2 | 2nd string | B3 |
| 3 | 3rd string | G3 |
| 4 | 4th string | D3 |
| 5 | 5th string | A2 |
| 6, bottom line | 6th string | E2 |

Do not hard-code standard tuning as a universal truth. Many guitar pieces use drop tunings, capo notation, seven-string guitars or other variants. Standard tuning is the default only when no contrary evidence is present.

## Fret numbers

A fret number identifies where the string is stopped.

- `0` means open string.
- Positive integers mean fretted notes.
- Multi-digit numbers such as `10`, `11` and `12` must be treated as one fret value, not separate events.
- `x` usually indicates a muted or dead note rather than a normal pitch.
- Parenthesised fret numbers may indicate ghost notes, optional notes, held notes, editorial suggestions or continuation depending on context.

The parser must not split adjacent digits merely because glyph extraction returns separate characters.

## Chords and simultaneity

Tab numbers vertically aligned across multiple strings usually represent notes played at the same musical time.

A chord event may contain multiple string/fret pairs at the same onset. The representation should allow one onset to contain several notes while still preserving each note's string and fret identity.

Small horizontal differences can occur because of font metrics, multi-digit fret numbers or PDF extraction noise. The grouping tolerance must be explicit and testable.

## Duration

Tablature alone often indicates pitch/string/fret more directly than rhythm.

Duration may come from:

- rhythmic stems and beams attached to tab numbers,
- standard notation staff aligned with the tab,
- spacing heuristics,
- bar structure,
- rests,
- explicit duration symbols,
- a previous or parallel representation such as MusicXML.

When duration cannot be inferred safely, the system should report uncertainty rather than inventing a precise value.

## Techniques

Common guitar techniques include:

- hammer-on,
- pull-off,
- slide,
- bend,
- release bend,
- vibrato,
- palm mute,
- let ring,
- staccato,
- dead note,
- natural harmonic,
- artificial harmonic,
- tapped harmonic,
- grace note,
- tied note,
- legato phrase markings.

The initial implementation does not need to support every technique. Unsupported techniques should be preserved as warnings or annotations where possible.

A technique should not be emitted as a supported semantic feature unless the parser has sufficient evidence to identify it reliably.

## Staff and tab reconciliation

Many guitar scores include both standard notation and tablature.

The staff may provide:

- rhythm,
- voices,
- ties,
- rests,
- tuplets,
- expression markings,
- repeats,
- tempo,
- key and time signatures.

The tab may provide:

- string assignment,
- fret assignment,
- idiomatic guitar fingering,
- open-string choices,
- alternative positions for the same pitch.

Where staff and tab disagree, do not silently prefer one. Record the conflict and make the conversion policy explicit.

## Ambiguity policy

Ambiguous tab extraction should produce structured warnings.

Examples:

- possible multi-digit fret split,
- uncertain string assignment,
- tab number not aligned to a known rhythmic event,
- unsupported technique marking,
- inconsistent staff and tab pitch,
- missing tuning information,
- overlap between unrelated glyphs.

Warnings should include enough context to reproduce the issue without committing private source material.

## Acceptance criteria for tab-related work

A valid tab-related implementation task should define:

- the specific tab feature being handled,
- the expected source evidence,
- the internal representation change if any,
- the output behaviour,
- at least one positive fixture or synthetic example,
- at least one ambiguity or failure case,
- diagnostics expected when confidence is low.

## Stop conditions

Stop and report rather than continuing if:

- a fixture appears to depend on private or copyrighted source material that should not be committed,
- the required technique cannot be distinguished from another notation mark,
- the implementation would guess fret/string values without evidence,
- tests pass only because they assert cosmetic output instead of musical meaning.
