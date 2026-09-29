# LAYOUT-01 source row layout

## Measurement before implementation

At product base `3b30f395781cad6fbd7aac6dc20b6f635b953e34`, each mounted PDF with a sibling GP reference was read with `read_note_durations(pdf, time_signature=(4, 4))`. The independent GPIF reader read every reference track's `SystemsLayout`. These are topology counts only.

| Source | PDF systems | PDF bars | Reference tracks | Agreement |
| --- | ---: | ---: | --- | --- |
| Lesson 3 | 23 | 66 | 23 rows, 66 bars | exact |
| Lesson 4 | 29 | 79 | 29 rows, 79 bars | exact |
| Lesson 5 | 14 | 43 | 14 rows, 43 bars | exact |
| Lesson 6 | 34 | 72 | 34 rows, 72 bars | exact |
| Lesson 7 | 25 | 50 | 25 rows, 50 bars | exact |
| Can't Find My Way Home | 10 | 21 | 10 rows, 21 bars | exact |
| Derek Trucks BB King | 9 | 20 | track 1: 9 rows, 16 bars; track 2: 6 rows, 16 bars | differs; PDF source has one notation system sequence |
| Ex 2 Hands Up | 3 | 27 | 3 rows, 11 bars | differs |
| Melodic Soloing Masterclass | 0 | 0 | 3 rows, 8 bars | no systems read |

Measured PDF bars per row:

- Lesson 3: `3 2 2 3 3 2 3 4 3 3 3 3 3 3 3 3 3 2 2 3 3 3 4`
- Lesson 4: `2 2 2 3 2 3 2 3 4 3 3 3 3 4 4 3 3 2 3 2 2 3 3 2 2 2 3 3 3`
- Lesson 5: `4 4 4 4 2 4 3 2 3 3 3 2 2 3`
- Lesson 6: `2 2 2 2 2 3 2 2 2 4 2 3 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2`
- Lesson 7: `2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2`
- Can't Find My Way Home: `2 2 2 2 2 2 2 2 2 3`
- Derek Trucks BB King: `2 2 3 2 2 2 1 3 3`
- Ex 2 Hands Up: `12 12 3`
- Melodic Soloing Masterclass: no rows found.

## Transfer rule

`read_note_durations` numbers each source bar from zero across pages and records each system's first bar and count. The PDF-only assembler writes a `ScoreIR` bar for every source ordinal. A refused event produces an empty bar at its original ordinal, so it does not move a row boundary. The transfer checks positive system counts, contiguous first-bar indices, contiguous page order, the complete written bar count, and written bar ordinals. It then stores the counts on the track. Any failed check leaves the track without source rows and records `pdf_systems_layout_fallback` with page, system, and bar provenance.

The GPIF writer emits the existing `SystemsDefautLayout` code and one space-separated `SystemsLayout` text element for each track. When source counts are unavailable or no longer sum to the written bar count, its documented default is consecutive rows of `SystemsDefautLayout` bars, with a shorter final row. For the PDF-only guitar track that default is three. It does not use `DoubleBar` to split rows. Other GPIF elements retain their previous shape.

The public PDF fixture joins two rows composed from a standard notation and TAB engraving, with two bars on its first row and one on its second. It removes page furniture that the current TAB extractor would otherwise classify as a fret. It was composed independently of the layout transfer code.
