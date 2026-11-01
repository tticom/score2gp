# TABRHY-01: the rhythm printed under a staffless TAB

Counts, codes and mark classes only. No fixture content is recorded here.

## Reading order (maintainer, 2026-11-01)

1. printed notation staff (the existing reader, unchanged);
2. **rhythm marks printed under the TAB** (this change);
3. printed beat-count text (not implemented);
4. a labelled guess from the TAB itself (TABONLY-01, not part of this task, not implemented).

A bar is written only when its durations total the printed meter's capacity exactly
(`meter.bar_capacity_ticks`, rational). Otherwise it is refused with a located reason code and its numbers.

## What is read (`src/score2gp/pdf_tab_rhythm.py`)

The reader emits `note-duration-records.v0.6` records, so the single PDF-only route
(`pdf_tab_bar_assembler`) writes or refuses each bar. Nothing is counted from columns or spacing.

| mark | reading |
| --- | --- |
| stem under a digit column | one event; its value from its beams |
| beams covering the stem (levels checked evenly spaced from the stem end) | 0 quarter, 1 eighth, 2 sixteenth, 3 thirty-second |
| dot beside the stem's lower end | one augmentation dot |
| tuplet bracket (two halves around a printed number) | the number gives n:2 (n:4 for 5 to 7); the group must hold exactly n events |
| arc between two columns holding the same strings and frets, or ending at a digit-less stem | tie |
| circle round a stemless column | whole note |
| circle round a column with a stem (and a dot) | half (dotted half) |
| whole-rest glyph hanging from a string line | whole rest |
| bar total below the meter, nothing else printed | IMPLIED trailing rest (labelled, counted apart, never rescues an over, contradicted or unread bar) |

### The circle (shown from real PDFs, not assumed)

On the sources that print it, a circle round a stemless chord stands alone in a bar of 4/4, so only a
whole note makes the bar total the meter. In a 3/4 bar a circle with a stem and a dot stands alone and only a
dotted half totals the meter. A circle with a stem and no dot (a half note) is the standard reading and is
checked by the same total; no source here prints one.

### Not read, located and refused

Flags (a stem with a flag glyph), rest glyphs other than the whole rest, any curved glyph under the strings that
is not a fingering label or a system-end bracket, two stems on one column, a stem between two columns, a
circle that does not enclose exactly one column, a tuplet whose events disagree with its number, a column
with no rhythm mark. Printed beat-count text is not read.

### Technique marks are not rhythm

Bends (arrow, label, parenthesised target), vibrato, slide lines and hammer-on or pull-off arcs are not read.
An arc is a tie only between identical string and fret (or into a digit-less stem); a fret digit
comes only from a TabRaw fret candidate; a vibrato squiggle sits above the strings and is never collected.
Real-source tests pin this (`tests/test_tab_rhythm_real.py`).

## Grouping resolution (`pdf.py`)

Measured on the grouping-unsafe source: its TAB staves have a line spacing between the two ranges
`classify_staff_line_group` accepted, and the staff lines are interrupted at every digit. Two changes, both
requiring independent evidence, neither loosening a gate:

1. a six-line group with a spacing in the gap between the two accepted ranges is a TAB when fret digits sit on
   its own lines (six lines cannot be a notation staff);
2. a digit-interrupted TAB group with three intact full-width lines and fret digits on its lines is recovered
   without a notation partner (the existing recovery already required three intact lines; the partner stands
   in for "not a text underline, diagram or legend", and fret digits on the lines do the same).

The rhythm reader finds its own TAB staves (the notation reader's finder plus the PDF reader's detector) and
the bar edges from full-height strokes. A fret digit that lies outside every one of those bars refuses the source
as `pdf_only_tab_grouping_unsafe` and is located, so no bar is silently dropped or renumbered.

## Numerals

`classify_numeral(..., narrow_one_only=True)` reads a form wider than 0.55 of its height as not a 1: a heavy 3 has a
right edge that runs the full height and was read as a 1 (3/4 as 1/4). The default is unchanged, so notation reads are unchanged.
