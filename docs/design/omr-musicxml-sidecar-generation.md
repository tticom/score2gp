# OMR MusicXML Sidecar Generation Architecture

This document records the architectural details of how professional OMR (Optical Music Recognition) engines like PhotoScore and ScanScore algorithmically translate graphical music sheets into valid, structured MusicXML files, and how these rules form the foundation of our implementation.

---

## Phase 1: Physical-to-Logical Space Mapping (Staff Alignment)

Before recognizing symbols, the engine maps physical image pixels (or vector PDF paths) into a relative coordinates grid:

1. **Staff Line Detection**: Using horizontal projection profiles (summing black pixels horizontally) or Run-Length Coding, the engine detects staff lines and calculates the staff-space size ($s_y$, the vertical distance between lines) and line thickness. This establishes a normalized coordinate system.
2. **Clef Anchoring**: The engine classifies clefs (Treble, Bass, Alto) using pattern matching or convolutional neural networks. The center of the clef determines the reference pitch (e.g., G4 on the second line from the bottom for a Treble clef).
3. **Pitch Determination**: The y-coordinate of a detected notehead is calculated relative to the staff lines. The pitch is resolved by checking how many half staff-spaces ($s_y / 2$) the notehead center is offset from the clef's anchor line.

---

## Phase 2: Structural Segmentation and Grouping

Individual pixels/lines are grouped into logical musical objects:

1. **Spatial Linking**: Glyphs are bounded by coordinate boxes. The engine applies proximity rules:
    - **Stems & Noteheads**: A vertical line (stem) is associated with a notehead only if its endpoints touch or overlap the notehead's bounding box.
    - **Accidentals**: A sharp, flat, or natural glyph is bound to a notehead if it shares the same vertical offset (staff-space height) and falls within a tight horizontal tolerance (typically $1.5 \times s_y$ to the left of the notehead).
2. **Barlines & Breaks**: Vertical lines that span the entire staff height are classified as barlines. The engine analyzes line thickness and counts to differentiate single, double, or final barlines. The vertical gap spacing between staff lines determines system and page layout boundaries.

---

## Phase 3: Polyphonic Voice Allocation (The Temporal Layer)

Since music is polyphonic but XML is serial, the engine must divide simultaneous events into independent musical tracks (voices) within the same staff:

1. **Timeline Slices**: The engine scans the staff from left to right, grouping notes into vertical time slices based on their x-coordinate.
2. **Stem-Direction Heuristics**: The primary rule for voice assignment is stem direction:
    - Stems pointing up $\rightarrow$ assigned to Voice 1.
    - Stems pointing down $\rightarrow$ assigned to Voice 2.
3. **Divisions Computation**: To prevent float rounding errors in timing, the engine calculates the Least Common Multiple (LCM) of all note subdivisions (e.g. triplets, eighths, sixteenths) in the measure. This integer is set as the `<divisions>` value for the measure.
4. **Filler Rest Insertion**: In a valid MusicXML measure, the sum of note durations for each active voice must equal the measure duration dictated by the `<time>` signature. If a voice has no notes on a particular beat, the engine computes the time gap and inserts a `<rest>` element to maintain temporal alignment.

---

## Phase 4: Hierarchical MusicXML Encoding

Once the logical graph is complete, it is exported into the standard nested MusicXML structure:

```xml
<score-partwise>
  <part id="P1">
    <measure number="1">
      <!-- Notes and Navigation -->
    </measure>
  </part>
</score-partwise>
```

### Navigating Time via `<backup>` and `<forward>`

Because XML is a linear tree, the parser cannot write Voice 1 and Voice 2 in parallel. The engine solves this by using virtual playback head movements:

1. **Encode Voice 1**: The engine writes Voice 1 note elements linearly from the beginning of the measure to the end.
    ```xml
    <note>
      <pitch>
        <step>G</step>
        <octave>4</octave>
      </pitch>
      <duration>8</duration>
      <voice>1</voice>
    </note>
    ```
2. **Rewind Time (`<backup>`)**: To encode Voice 2, the engine inserts a `<backup>` tag with a `<duration>` attribute matching the exact length of the measure. This moves the XML reader's timeline pointer back to the start of the measure.
    ```xml
    <backup>
      <duration>8</duration>
    </backup>
    ```
3. **Encode Voice 2**: The engine then writes the Voice 2 note elements linearly.
    ```xml
    <note>
      <pitch>
        <step>C</step>
        <octave>4</octave>
      </pitch>
      <duration>8</duration>
      <voice>2</voice>
    </note>
    ```
4. **Offsetting Time (`<forward>`)**: If Voice 2 starts late, the engine writes a `<forward>` element with the corresponding duration to skip empty space without needing a visible rest.
