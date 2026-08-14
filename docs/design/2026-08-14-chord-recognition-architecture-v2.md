# ADR: Chord Recognition and Capacity Validation v2

**Date**: 2026-08-14
**Status**: Proposed

## 1. Context and Problem Statement
The `TopologicallyLockedBarTimeline` currently employs destructive partition hacks to force output into a valid state. Specifically, it silently truncates overlapping same-voice notes and pads misaligned measures with synthetic `padding_rest` data. This masks OMR and timeline alignment errors, breaking true capacity invariants and preventing the native recognition of chords. 

When the OMR engine provides true simultaneous notes (chords), the current logic either incorrectly serializes them if they fall into different X-based time slices, or silently truncates their durations if their upstream `start_tick`s overlap in complex ways. A strict, deterministic approach is required to correctly recognize chords and loudly flag capacity violations.

## 1.5. Scope and Non-Goals
**In Scope**: Native parsing of chords based on strict equivalence (same voice, start tick, and duration); removal of silent duration truncation and `padding_rest` injection; loud capacity invalidation.
**Out of Scope**: Fixing the upstream OMR engine's stem extraction; auto-correction of invalid measures.

## 2. True OMR Evidence for Simultaneous Notes
In standard notation, chords are represented by vertically aligned noteheads. 
True OMR evidence for a chord strictly requires that note candidates:
1. Belong to the exact same **voice**.
2. Share the exact same **start tick**.
3. Share the exact same **duration**.

*Rule*: If candidates share the same voice and start tick but have **unequal durations**, they are musically invalid as a single voice chord. Such evidence must be interpreted as polyphony (requiring voice separation) or trigger an explicit refusal (invalidation of the measure).

## 3. Architecture Design

### 3.1. Removal of Destructive Hacks
The following code blocks in `TopologicallyLockedBarTimeline` must be completely removed:
- **Silent Truncation**: The logic that dynamically shrinks a note's `duration_ticks` when it overlaps with a subsequent note.
- **Synthetic Padding**: The logic that injects `padding_rest` events to force a measure to full capacity.

### 3.2. Deterministic Chord Grouping
Instead of destructive normalization, the timeline will preserve OMR evidence natively:
- **Strict Chord Equivalence**: Candidates are grouped into a chord if and only if they share the exact same `voice`, `start_tick`, and `duration_ticks`. 
- **Polyphony / Conflict Rejection**: If notes share a `start_tick` and `voice` but have unequal `duration_ticks`, the timeline must explicitly refuse to process them as a chord. The measure must be flagged as invalid.
- **Explicit Capacity Validation**: If the final cursor position does not exactly equal `D_measure`, or if there is an explicit overlap (notes with different start ticks that intersect in time), the timeline sets `invalid = True`. The invalid state is persisted on the timeline object. The original unaltered candidates remain in the `events` ledger. 
- **Consumer Refusal**: Downstream consumers (e.g., `musicxml_generator.py` or the ScoreIR compiler) must refuse to compile invalid measures (e.g., throwing a capacity mismatch error) rather than silently omitting or padding them.

## 4. Validation and Pre-Submit Challenge
**Baseline**: The current tests (like `test_musical_timeline_replacement.py`) explicitly test the padding and truncation behaviors.
**Challenge**: These tests must be updated to expect `invalid = True` instead of synthetic padding. New tests must prove that chords (equal voice, start tick, and duration) are preserved natively, and that unequal durations at the same tick trigger invalidation.
