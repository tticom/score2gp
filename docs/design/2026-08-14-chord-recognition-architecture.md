# ADR: Chord Recognition and Capacity Validation

**Date**: 2026-08-14
**Status**: Accepted

## 1. Context and Problem Statement
The `TopologicallyLockedBarTimeline` currently employs destructive partition hacks to force the output into a valid state. Specifically, it silently truncates overlapping same-voice notes and pads misaligned measures with synthetic `padding_rest` data. This masks OMR and timeline alignment errors, breaking true capacity invariants, and preventing the native recognition of chords. 

When the OMR engine provides true simultaneous notes (chords), the current logic either incorrectly serializes them if they fall into different X-based time slices, or silently truncates their durations if their upstream `start_tick`s overlap in complex ways. A strict, deterministic approach is required to correctly recognize chords and loudly flag capacity violations.

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
- **Time Slicing Preservation**: The existing `time_slices` logic based on `X_tol` will be maintained but properly leveraged. All candidates within a single `time_slice` that share the same `voice` are defined as a single chord.
- **Shared Start Tick and Cursor Advancement**: All notes within a chord group must receive the identical `start_tick`. The measure's timeline cursor (e.g. `cursor_1`) will advance exactly once by the maximum duration of the notes in that chord slice.
- **Explicit Capacity Validation**: If the final cursor position does not exactly equal `D_measure`, or if there is an explicit overlap between *distinct* sequential time slices, the timeline sets `invalid = True`. We do not attempt to repair the measure; we preserve the raw events so that downstream mismatch ledgers or human review can diagnose the underlying OMR failure.

## 4. Downstream Impact
By emitting chords as multiple `events` with identical `start_tick` and `voice` values, downstream systems like `musicxml_generator.py` (which already groups notes with identical `start_tick` into `<chord/>` elements) will naturally process the chords correctly. The `ScoreIRCompiler` will also receive truthful duration data rather than truncated artifacts.
