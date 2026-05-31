# Guitar Technique and Articulation Conversion

This document defines the domain-backed concepts, constraints, and safe conversion boundaries for guitar-specific techniques and articulations in `score2gp`. 

---

## 1. Guitar Articulation Definitions

### A. Hammer-ons (H) & Pull-offs (P)
- **Concept:** Legato articulations where a note is sounded without picking, using only the fretting hand.
  - **Hammer-on (H):** A finger of the fretting hand strikes the string sharply against a higher fret while a lower note is already sounding.
  - **Pull-off (P):** A fretting finger is pulled off a fretted string, slightly plucking it, to allow a lower fretted note or open string to sound.
- **Visual Representation:** Enclosed under a slur curve in standard notation; annotated with `H` or `P` above the staff or between fret digits in tablature.
- **ScoreIR Model:** Represented via `HammerOnTechnique` and `PullOffTechnique` models.

### B. Slides (sl.)
- **Concept:** Pitch transitions achieved by sliding a fretting finger along the string from one fret to another.
  - **Shift Slide:** The destination note is picked upon arrival.
  - **Legato Slide:** The destination note is sounded purely by the sliding motion (no second pick).
  - **Slide In / Out:** A slide starting from or ending at an indefinite pitch.
- **Visual Representation:** Slanted lines (`/` or `\`) between fret digits in TAB, often accompanied by a slur and the text label `sl.`.
- **ScoreIR Model:** Represented via `SlideTechnique` with styles (`shift`, `legato`, `slide-in`, `slide-out`).

### C. Bends & Releases
- **Concept:** Raising the pitch of a fretted note by pushing or pulling the string sideways across the frets.
  - **Full Bend (full):** Pitch is raised by a whole step (+2 semitones).
  - **Half Bend (1/2):** Pitch is raised by a half step (+1 semitone).
  - **Bend and Release:** The string is bent to a higher pitch and then released back to the original fretted pitch.
  - **Pre-Bend:** The string is bent *before* it is plucked, sounding the higher pitch immediately.
- **Visual Representation:** Curved arrows pointing upward with text labels like `full`, `1/2`, `1/4` above the staff.
- **ScoreIR Model:** Represented via `BendTechnique` containing a sequence of `BendPoint` offsets and values.

### D. Slurs & Legato
- **Concept:** A curved line connecting notes of different pitches, indicating that they are to be played smoothly (legato) without separation.
- **Visual Representation:** A curved arc spanning a group of notes.
- **ScoreIR Model:** Represented via `SlurTechnique` mapping the start and end event IDs.

### E. Parenthesised Fret Numbers
- **Concept:** Fret digits enclosed in parentheses, such as `(5)`.
  - **Ghost Note:** Played very softly to add rhythmic texture.
  - **Tied / Held Note:** A continuation of a note sustained from a previous measure or beat.
  - **Pre-Bent Pitch:** Indicates the target bent pitch before striking.
- **ScoreIR Model:** Ghost notes map to `Note` with velocity/dynamics properties; tied notes map to `TieTechnique`.

---

## 2. Earliest Defective Stage: Large Line Spacing Blocker

### Spacing Spanned Blocker (Stage 1/2 Layout Grouping)
- **Defect:** Melodic soloing scores printed at large page scale or high spatial density have tab staff line-to-line spacing of **26.575 points** (or other large values exceeding standard defaults).
- **Blocker Cause:**
  - `_tab_line_groups()` in `src/score2gp/pdf.py` enforces a strict horizontal line-gap filter: `if gap < 6.0 or gap > 24.0: continue`.
  - `classify_staff_line_group()` restricts 6-line staves to a median gap within `5.5 <= median_gap <= 7.2` or `9.5 <= median_gap <= 15.0`.
- **Consequence:** The six tab lines are never grouped into a valid `TabSystem`. This forces all fret digit candidates on the page to fail system and string assignment. They are categorized as unassigned/non-playable, and Stage 4 `build_ir` writes an empty staff, even though the visual extraction stages correctly located all characters.

---

## 3. Safe Fallback Behavior (Preservation Contract)

To prevent valid inputs from compiling into blank sheets, the pipeline must enforce a strict **Preservation Contract**:

1. **Never Delete Playable Notes Silently:** Playable notes with valid pitches, string assignments, and timing alignment must always be preserved and written to ScoreIR and GPIF, even if they have attached techniques that are unsupported or fail to parse.
2. **Warn Loudly, Do Not Refuse:** Unsupported guitar technique marks (like bends, slides, or grace notes) must be captured as non-playable technique candidates, raise `pdf_unsupported_technique_warning` or `scoreir-technique-skipped` info warnings, and allow the core note to render.
3. **Fail Loudly on Unsafe Timing Only:** The only condition that justifies compile refusal is structurally unsafe timing (e.g. overfull measures, mismatched voice tracks, or corrupt durations) where writing the file would cause playback crashes or binary corruption.

---

## 4. Future Public Synthetic Fixture Plan (Future Work)

> [!NOTE]
> This section outlines planned future work. No synthetic fixtures or technique-specific assertions are implemented in the current branch.

To develop and test technique conversion without exposing private inputs, the following public-safe synthetic test files are planned for subsequent implementation branches:

### Fixture 1: `synthetic_hammer_pull.xml` / `synthetic_hammer_pull.json`
- **Rhythm:** 4/4 bar of four quarter notes.
- **Articulation:**
  - Note 1 to Note 2: Pitch E3 (string 4, fret 2) to G3 (string 3, fret 0) connected by `HammerOn` (slur + `H`).
  - Note 3 to Note 4: Pitch G3 (string 3, fret 0) to E3 (string 4, fret 2) connected by `PullOff` (slur + `P`).
- **Assertion:** Fret notes are preserved; `HammerOnTechnique` and `PullOffTechnique` are verified in the IR. ScoreIR model support exists; exact GPIF representation must be verified in a later implementation fixture.

### Fixture 2: `synthetic_slides.xml` / `synthetic_slides.json`
- **Rhythm:** 4/4 bar of eighth notes.
- **Articulation:**
  - Note 1 to Note 2: Pitch E2 (fret 0) to G2 (fret 3) connected by `Slide` up (`/`).
  - Note 3 to Note 4: Pitch A3 (fret 2) to G3 (fret 0) connected by `Slide` down (`\`).
- **Assertion:** Note pitches are correct; slide techniques are assigned to target notes.

### Fixture 3: `synthetic_bends.xml` / `synthetic_bends.json`
- **Rhythm:** 4/4 bar of quarter notes.
- **Articulation:**
  - Note 1: Pitch D3 (string 3, fret 7) with a `full bend` (+2 semitones).
  - Note 2: Pitch D3 with a `1/2 bend and release`.
- **Assertion:** Note pitch is correct; `BendTechnique` contains valid `DestinationValue` and points list.

### Fixture 4: `synthetic_mixed_rhythms.xml` / `synthetic_mixed_rhythms.json`
- **Phrase:** Lead melody with sixteenth, dotted eighth, and quarter notes.
- **Assertion:** Mixed rhythmic durations are successfully aligned using dynamic sequence alignment with zero timing overlap warnings.

