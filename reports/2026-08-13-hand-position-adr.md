# ADR: Hand Position Inference vs. Explicit TAB Data

## Status
Accepted

## Context
The `ScoreIRCompiler` requires fret and string data for note events. Currently, the `BiomechanicalPositionOptimizer` attempts to infer these positions using a sequential cost-optimization model that heavily penalizes fret jumps and string stretches. 
However, guitarists play chords as simultaneous shapes, not as sequences of extreme hand jumps. Furthermore, varying musician styles dictate different positional choices across the fretboard. When OMR (Optical Music Recognition) fails to extract an explicit TAB string and fret for a note (i.e. an "unowned" note), the system attempts to infer the position or falls back to injecting synthetic `(string=1, fret=0)` notes, resulting in musically corrupt output and failing integration tests.

## Decision
We will **rely entirely on explicit TAB data** and abandon complex, sequential biomechanical position inference. 
It is **not strictly necessary** to infer and record physical hand positions for the `ScoreIRCompiler`. Guitar Pro (`.gp`) files only require string and fret numbers for each note to render correctly. 

Any unowned notes (where explicit TAB string/fret data cannot be observed) must trigger a strict failure (`ValueError`) in the compiler rather than silently mutating the score with synthetic data.

## Rationale
1. **Subjectivity:** Hand positions are highly style-dependent. Inferring them introduces subjectivity that cannot be deterministically validated against the original sheet music.
2. **Chord Shapes vs. Jumps:** Sequential cost models fundamentally break down for chords, treating simultaneous notes as massive physical hand jumps.
3. **Data Integrity:** Injecting synthetic data like `(string=1, fret=0)` silently corrupts the output file. A strict fail-closed approach ensures data integrity and forces the OMR extraction layers to improve their TAB recognition fidelity.

## Consequences
- The `ScoreIRCompiler` will throw an explicit `ValueError` if an unowned note reaches it.
- `BiomechanicalPositionOptimizer`'s sequential inference can be deprecated or strictly relegated to an optional, secondary heuristic that is never allowed to override missing critical data.
- The pipeline's accuracy relies entirely on explicit TAB extraction; missing TAB data will properly fail the conversion process, providing clear signals for upstream fixes.
