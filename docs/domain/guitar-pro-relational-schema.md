# Guitar Pro Relational Schema (GPIF) Constraints

## Status: Stable / Verified Project Decision

This document details the reverse-engineered constraints of the official Guitar Pro relational database XML schema (GPIF) and the packaging requirements necessary to prevent crashes and ensure visual/structural alignment in Guitar Pro 7 & 8.

---

## 1. Relational Database XML Schema Hierarchy

Unlike the classic hierarchical layout mode used in older GP file formats, native Guitar Pro 7 & 8 relational layouts utilize flat database tables (like `<MasterBars>`, `<Bars>`, `<Voices>`, `<Beats>`, `<Notes>`, and `<Rhythms>`) directly under the root `<GPIF>` element. The strict parsing engine in official Guitar Pro editors enforces several schema invariants, deviations from which cause immediate application crashes or hangs.

### A. Element Order Constraints under `<Score>`
Under `<Score>`, the sequential XML parser expects metadata and layout settings in an exact order:
1. `Title`, `SubTitle`, `Artist`, `Album`, `Words`, `Music`, `WordsAndMusic`, `Copyright`, `Tabber`, `Instructions`, `Notices` (Direct children of `<Score>`)
2. `ScoreSystemsDefaultLayout`
3. `ScoreSystemsLayout`
4. `ScoreZoomPolicy`
5. `ScoreZoom`
6. `MultiVoice`
7. `View`
8. `Print`
9. `Layout`

*Project Decision*: Any deviations or out-of-order tags under `<Score>` will trigger sequential parser rejection, resulting in a blank screen and a hanging app.

### B. Track Properties Invariants
Official Guitar Pro files do not contain visual layout properties directly under `<Track>`.
*   **Capo and Tuning Locations**: Tuning and Capo must NOT be written as `<Tuning>` or `<Capo>` direct children under `<Track>`. Instead, they are strictly defined inside staff properties:
    *   `Staves -> Staff -> Properties -> Property[@name="Tuning"]` using a space-separated `<Pitches>` element.
    *   `Staves -> Staff -> Properties -> Property[@name="CapoFret"]`.
*   **Instrument**: Never write `<Instrument>` under `<Track>` in relational layouts.
*   **Staff Properties**: Never write `<StaffProperties>` under `<Staff>` in relational mode; only `<Properties>` is permitted.

### C. MasterBar to Bar Serialization
*   **No Index Attribute**: `<MasterBar>` nodes must carry no attributes (no `index="..."`). The bar sequence is determined strictly by their index in the child array under `<MasterBars>`.
*   **Key before Time**: Under `<MasterBar>`, `<Key>` must strictly precede `<Time>`.
*   **Key Custom Properties**: The `<Key>` element must use relational elements `<AccidentalCount>`, `<Mode>` (e.g., `"Major"` or `"Minor"`), and `<TransposeAs>` (e.g., `"Sharps"` or `"Flats"`), rather than the classic `<Fifths>` and lowercase `<Mode>`.

---

## 2. Packaging and Binary Companion Files

A valid `.gp` file is a zipped package containing a `VERSION` file, a `Content/score.gpif` file, and several binary/JSON companion files.

### A. Pristine Template Preservation
Companion files such as `Content/Preferences.json`, `Content/LayoutConfiguration`, and `Content/ScoreViews/*.gpsv` must be preserved exactly as they are defined in native templates. Rewriting them as generic XML or standard JSON breaks the internal binary structure and causes the application to crash immediately on load.

### B. Track ID Reference Snap-to-Zero
*   **The Zero-Index Invariant**: Binary companion files and stylesheet templates in Guitar Pro are hardcoded to reference Track ID `"0"`. 
*   **Resolution**: If the ScoreIR uses strings like `"gtr-1"`, these track IDs must be mapped to sequential 0-indexed integers (`"0"`, `"1"`, etc.) during relational compilation to align references across binary view files.

### C. SystemsLayout Measure Count
The `SystemsLayout` list (a space-separated string under `<Track>`) represents the number of measures per page system. The sum of the list must match the total measure count `M` exactly (e.g. `"3 3 ... 3"`). An incorrect or truncated list causes a layout engine bounds overflow and immediate crash.

### D. Explicit Directory Headers in Zip
Decompressors in strict native C++/Qt GUI frameworks (such as Guitar Pro's) throw exceptions or crash if they attempt to extract files into subfolders that have not been explicitly declared in the zip headers. Zip compilers must dynamically write explicit folder entries (e.g., `Content/ScoreViews/` and `Content/Stylesheets/`) into the zip file headers.

---

## 3. Rhythms, Beats, and Voice Mapping

### A. Rests and Rhythms in Relational Mode
*   **Illegal `<Rest>` Tag**: In flat relational layouts, a beat representing a rest must NOT contain a `<Rest />` tag. Instead, rests are represented simply by omitting the `<Notes>` reference element from the `<Beat>` node entirely.
*   **Stem Orientations**: Every beat node must carry standard stem orientation elements `<TransposedPitchStemOrientation>` (set to `"Downward"` for rests and `"Upward"` for notes) and `<ConcertPitchStemOrientation>` (set to `"Undefined"`).

### B. Voice-to-Staff Partitioning
In paired standard-tab notation tracks, different staves (Standard Notation and Tablature) are parsed as separate voices.
*   **MusicXML / ScoreIR Voice Convention**:
    *   Staff 1 uses voices `1, 2, 3, 4` (0-indexed `0, 1, 2, 3`).
    *   Staff 2 uses voices `5, 6, 7, 8` (0-indexed `4, 5, 6, 7`).
*   **GP Relational Bar Constraints**: A single relational `<Bar>` node represents one staff for a given measure and supports up to 4 voices (GP Voice 0 to 3).
*   **Voice Range Folding**: To prevent note-loss, events must be partitioned across staves by voice range:
    *   Staff Index `s_idx = (voice - 1) // 4` (clamped).
    *   GP Voice Index `gp_v_idx = (voice - 1) % 4`.
    This maps Voice 5 (Tablature Note 1) cleanly to GP Voice 0 on Staff 2, restoring 100% of the notes.
