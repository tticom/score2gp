# ADR: Chord Recognition and Capacity Validation

**Date**: 2026-08-14
**Status**: Accepted

## 1. Context and Problem Statement
The `TopologicallyLockedBarTimeline` currently employs destructive partition hacks to force the output into a valid state. Specifically, it silently truncates overlapping same-voice notes and pads misaligned measures with synthetic `padding_rest` data. This masks OMR and timeline alignment errors, breaking true capacity invariants, and preventing the native recognition of chords.

When the OMR engine provides true simultaneous notes (chords), the current logic either incorrectly serializes them if they fall into different X-based time slices, or silently truncates their durations if their upstream `start_tick`s overlap in complex ways. A strict, deterministic approach is required to correctly recognize chords and loudly flag capacity violations.

## 1.5. Scope and Non-Goals
**In Scope**: Native parsing of chords from identical `start_tick`s or non-transitive spatial grouping; removal of silent duration truncation and `padding_rest` injection; loud capacity invalidation.
**Out of Scope**: Fixing the upstream OMR engine's stem extraction; polyphony voice separation logic; auto-correction of invalid measures.

## 2. True OMR Evidence for Simultaneous Notes
In standard notation, chords are represented by vertically aligned noteheads. However, intervals of a second (e.g., C and D) are drawn horizontally adjacent.
True OMR evidence for a chord consists of note candidates that:
1. Belong to the same voice.
2. Have horizontal bounding boxes (or X-coordinates) that are strictly overlapping or within a narrow tolerance (e.g., `1.5 * staff_spacing`).
3. Have identical durations (as derived from a shared stem).

If upstream timing alignment (e.g. from TAB duration association) provides explicit `start_tick` metadata, candidates with identical `start_tick` and `voice` are deterministically part of the same chord.

## 3. Architecture Design

### 3.1. Removal of Destructive Hacks
The following code blocks in `TopologicallyLockedBarTimeline` must be completely removed:
- **Silent Truncation**: The nested loops that dynamically shrink `curr_e["duration_ticks"]` when it overlaps with `next_e["start_tick"]`.
- **Synthetic Padding**: The logic that injects `padding_rest` events when `cursor < D_measure`.

### 3.2. Deterministic Chord Grouping
Instead of destructive normalization, the timeline will preserve OMR evidence natively:
- **Non-Transitive Geometric Grouping**: The existing `time_slices` logic must be rewritten to be non-transitive. A slice's width cannot exceed `1.5 * staff_spacing` relative to the *first* note in the slice.
- **Timing Precedence**: Explicit upstream timing (`start_tick`) takes strict precedence over geometry. If candidates possess differing explicit `start_tick`s, they must never be grouped into the same chord slice, regardless of spatial proximity. Conflicts where candidates have identical explicit `start_tick`s but fall far outside the geometric bounds are resolved in favor of the explicit `start_tick` (they group as a chord).
- **Shared Start Tick and Cursor Advancement**: All notes within a chord group must receive the identical `start_tick`. The measure's timeline cursor (e.g. `cursor_1`) will advance exactly once by the maximum duration of the notes in that chord slice.
- **Explicit Capacity Validation**: If the final cursor position does not exactly equal `D_measure`, or if there is an explicit overlap between *distinct* sequential time slices, the timeline sets `invalid = True`. The invalid state is persisted on the timeline object. The original unaltered candidates remain in the `events` ledger. Downstream consumers (e.g., `musicxml_generator.py` or the ScoreIR compiler) must refuse to compile invalid measures (e.g. throwing a capacity mismatch error) rather than silently omitting or padding them.

## 3.5. Validation and Pre-Submit Challenge
**Baseline**: The current tests (like `test_musical_timeline_replacement.py`) explicitly test the padding and truncation behaviors.
**Challenge**: These tests must be updated to expect `invalid = True` instead of synthetic padding, and new tests must prove that chords retain identical `start_tick`s without truncation.

## 4. Downstream Impact
By emitting chords as multiple `events` with identical `start_tick` and `voice` values, downstream systems like `musicxml_generator.py` (which already groups notes with identical `start_tick` into `<chord/>` elements) will naturally process the chords correctly. The `ScoreIRCompiler` will also receive truthful duration data rather than truncated artifacts.
