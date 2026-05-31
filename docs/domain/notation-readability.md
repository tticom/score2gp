# Notation Readability Domain Rules

## Semantic Correctness versus Human Readability
- **Status:** Verified domain fact
  - **Source:** Standard music notation engraving manuals (e.g. Gardner Read, Elaine Gould)
  - **Claim:** A piece of music can be mathematically/semantically correct (all durations sum exactly to the measure capacity) yet remain extremely difficult or impossible for a human musician to read at sight if rhythmic groupings and beat subdivisions are obscured.

## Beaming as Rhythmic Grouping
- **Status:** Verified domain fact
  - **Source:** Elaine Gould, *Behind Bars*, p. 153-157
  - **Claim:** Beaming is used to visually group notes of eighth-note (quaver) duration or shorter to reflect the underlying metric structure of the time signature. Correct beaming allows the performer to instantly perceive the beat units and their internal subdivisions.

## The Midpoint of the Bar in 4/4 Metric Space
- **Status:** Verified domain fact
  - **Source:** Elaine Gould, *Behind Bars*, p. 162
  - **Claim:** In a 4/4 measure, the imaginary vertical division between beats 2 and 3 represents the "midpoint of the bar". Connecting eight equal eighth notes (quavers) with a single continuous beam across the entire bar (a group of [8]) completely obscures this midpoint. Engraving conventions demand that beams do not cross the bar's midpoint, ensuring the performer can clearly distinguish the first half of the measure from the second.

## Default Project Policy for 4/4 Eighth-Note Grouping
- **Status:** Project decision
  - **Claim:** The project's default beaming policy for eight eighth notes in 4/4 is to split them into two equal groups of four (`[4, 4]`). Alternatively, grouping by individual beat units (`[2, 2, 2, 2]`) is acceptable. One single continuous beam group of eight (`[8]`) is explicitly rejected.

## Compound Metre Grouping Expectations
- **Status:** Verified domain fact
  - **Source:** Standard music theory metric classification
  - **Claim:** In compound metres (e.g. 6/8, 9/8, 12/8), beats are divided into groups of three eighth notes. For instance, in 6/8, eighth notes must be beamed in two groups of three (`[3, 3]`), never `[2, 2, 2]`, to preserve compound duple metric flow.

## Tablature and Notation Alignment Readability
- **Status:** Project decision
  - **Claim:** Visual alignment between the standard treble notation staff and the tablature staff must be perfectly maintained. Desynchronized stave positions or mismatched beat groupings confuse the reader and constitute a notation readability defect.

## Observed Implementation Behaviour
- **Status:** Observed implementation behaviour
  - **Evidence:** Executing `python scripts/private_e2e_smoke.py` on Lesson 3 produced beats containing unconditional link-to-next beaming properties, resulting in eighth notes in 4/4 being grouped into a single continuous beam of eight (`[8]`).
  - **Correction:** Modify `gpif.py` to selectively serialize the Beat `XProperty id="1124204546"` (Beam Link to Next) to enforce the `[4, 4]` beaming contract for 4/4 bars.

## Suggested Tests
- **Status:** Project decision
  - **Claim:** Implement automated contract tests at the writer boundary asserting that 4/4 bars of eighth notes serialize with beam groupings of `[4, 4]` or `[2, 2, 2, 2]` by checking that `XProperty id="1124204546"` is omitted on beat boundaries.

## Stop Conditions
- **Status:** Project decision
  - **Claim:** If beaming adjustments require altering underlying note durations or timing onsets, stop and report immediately. Engagement with Engraving layout parameters must not compromise semantic correctness.

## Unresolved Questions
- **Status:** Unknown / unresolved
  - **Question:** How does the relational GPIF XML represent beaming for triplets and complex subdivisions (e.g. 16th-note beams)?
