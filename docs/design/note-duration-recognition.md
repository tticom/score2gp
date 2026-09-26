# Note-duration recognition (DUR-01)

Every note and rest carries its own duration, written in its **note type**: the notehead, the stem,
its flags or beam lines, augmentation dots, the rest glyph, and the grouping (beams, tuplets, ties).
Counts, spacing, defaults and bar totals are never a source of duration. The bar total is only a
check. When the symbols do not identify a value, the event is recorded **unread** with a located
reason, never guessed.

Code: `src/score2gp/notation_omr/note_duration.py`. CLI: `score2gp read-note-durations --pdf <pdf>
--out <dir> [--pages 1-2] [--time-signature 4/4]` writes `<dir>/note-durations.json`
(`note-duration-records.v0.1`). The conversion route does not use it yet; DUR-02 replaces the
route's fallbacks with it.

## Value rules

| Symbols | Value |
|---|---|
| Hollow notehead, no stem | whole |
| Hollow notehead with stem | half |
| Filled notehead with stem, no flag or beam | quarter |
| Plus 1, 2, 3, 4 flag hooks or beam lines at the stem | eighth, 16th, 32nd, 64th |
| Rest glyph | its own value, whole to 64th |

Each augmentation dot adds half of the previous value. A tuplet scales only the events it spans:
`n:m` as printed, or a bare `n` by convention (`3` is 3:2, `5` to `7` are n:4, and so on). A bare
`2` or `4` does not state its ratio, so the event is not read. A tie is recorded on both events,
and their values are not merged.

## Reading the symbols

The reader works from the PDF's vector drawings. It reuses the L3-01 painted-contour and
visibility-at-contact primitives from `pdf.py` (`_notehead_candidate_shapes`, `_paints_into`,
`_inside_fill`, `_has_attached_notehead`). Glyph kinds are identified from their painted form, by
scanning the fill along lines (`_runs`: exact, cut at every outline crossing). Every threshold is
in staff spaces of the staff being read.

- **Staves.** Collinear horizontal pieces merge into lines, across fret-number gaps. A line must
  be at least 60% ink along its span; a chain of ledger lines is about 30%. Five or six equally
  spaced lines that start and end together form a notation or TAB staff. Each notation staff's
  zone stops half a space short of its neighbours, so TAB digits never enter it.
- **Barlines.** A vertical that spans the staff exactly, with no notehead in painted contact.
  Double barlines merge into one boundary.
- **Noteheads.** A curved glyph of notehead size. It is *filled* when it paints its centre and
  at least half its box, and *hollow* when its centre is unpainted and scans through it cross a
  ring.
- **Stems.** A thin vertical in painted contact with a notehead at one end. Every notehead it
  touches belongs to the chord.
- **Beam lines.** A filled band of constant vertical thickness that meets a stem. The count is
  the number of visibly separate bands crossing the stem's painted extent, merged across drawings.
  The outermost band holds the stem tip and the rest follow inward. A stem crossing that is not at
  the tip is not a beam line. A beam-shaped band that meets no stem is not a beam: a whole or half
  rest is such a band.
- **Flags.** Glyphs painted onto the stem, starting at its tip and chaining inward. Hooks per flag
  glyph (`_flag_hooks`) are the blades crossed by vertical scans through the flag's middle, and
  three scans must agree. A combined sixteenth flag drawn as one glyph has two hooks. A flag drawn
  with many segments still has one. The count never comes from drawings or segments.
- **Dots.** Small round fills in a row to the right of each notehead (or rest), at its height. A
  chord's dot count is the length of one row, not the number of dot glyphs.
- **Rests.**
  - *Block*: a band hanging from a staff line is a whole rest; one sitting on a line is a half rest.
  - *Hooked* (8th to 64th): below the stem top, the right edge descends leftward without
    reversal. The hooks are the separate pieces left of the stem, found by run-connected
    components.
  - *Quarter*: a zigzag right edge, with at least 75% single-run horizontal scans. Sharps and
    naturals do not qualify.
  - Rest-sized glyphs that match none of these are recorded unread. Accidentals (just left of a
    notehead), articulations (over a notehead) and the system header are not events.
- **Tuplets.** A number with a bracket piece on each side spans the events inside the bracket. A
  bare number spans the one beam group directly beneath it. Several kinds of number are not
  tuplets:
  - bar numbers (above the staff, before the first event of their bar);
  - time-signature numbers;
  - numbers touching other text, such as chord names.

  Any other number is unassociated; the events under it are recorded unread.
- **Ties.** A thin crescent that leaves a notehead (after its dots). It ends at the same staff
  position on the very next event, possibly across a barline. An arc that skips an event or
  changes pitch is a slur: a hammer-on or pull-off slur over three notes is not a tie.
- **Time signature.** Two stacked text numbers at the start of the staff. A signature drawn as
  paths (as in the Guitar Pro corpus) is not read. The caller may then declare one, and it is used
  for the bar check only.

## Unread reasons

`filled_notehead_without_stem`, `hollow_notehead_with_flag_or_beam`, `flag_and_beam_on_one_stem`,
`more_than_four_flags_or_beams`, `flag_glyph_unidentified`, `beam_lines_not_separable`,
`stem_crossing_not_at_tip`, `rest_glyph_unidentified`, `tuplet_number_unassociated`,
`overlapping_tuplets`, `mixed_notehead_kinds`, `dot_rows_disagree`, `concurrent_events`.

Each unread record keeps `location` (page, system, bar, event index, bounding box). Its `written`,
`value_quarters` and `duration_quarters` are null. An event that lies outside every bar is never
dropped silently: it is counted in `diagnostics.events_outside_bars`, which is zero on every fixture
and on Lessons 3 to 7 (tested).

## Bar check

Per bar: the total of the read durations and the expected total from the time signature. The status
is `match`, `mismatch`, `incomplete` (some event unread) or `time_signature_unread`. The check never
changes a record. Declaring a different signature changes only the check (tested).

## Evidence

Fixtures are the public synthetic PDFs under `tests/fixtures/pdf/dur_01/`, generated by
`scripts/dur_01_make_fixtures.py` in the corpus's vector vocabulary with uniform spacing. Tests are
in `tests/test_dur_01_note_durations.py`. Each fixture reads 100% correctly:

- a half note and eight 32nd notes;
- dotted and double-dotted notes;
- an eighth beamed to two sixteenths, and partial beams both ways;
- bracketed eighth and quarter triplets;
- every rest, whole to 64th;
- a tie across a barline;
- ambiguous symbols recorded unread.

Each mutation check makes the tests fail, and the tests assert it:

| Mutation | Fixtures that fail |
|---|---|
| Flag hooks replaced by a segment count | `dotted`, `rests` |
| Dots ignored | `dotted`, `mixed_beams`, `tie_across_barline` |
| Tuplets ignored | `triplet` |
| Values derived from beam-group size | `mixed_beams` |

**Real sources** are compared with the ground-truth `.gp` per event by `scripts/dur_01_compare.py`.
Lesson 3 uses the independent reference reader `scripts/native_slice_reference.py` (standard
library only; never imports score2gp). The reference reader refuses Lessons 4 to 7 (tuplets, ties).
Their rhythm is read by the script's standard-library rhythm-only reader. That reader agrees with
the reference reader on Lesson 3, and it also compares ties. The tests are
`tests/test_dur_01_lesson3.py` and `tests/test_dur_01_lessons_4_7.py`.

| Source | Bars (truth / read) | Events | Read | Equal | Tied events | Mismatches |
|---|---|---|---|---|---|---|
| Lesson 3 | 66 / 66 | 465 | 465 | 465 | 0 | none |
| Lesson 4 | 79 / 79 | 557 | 557 | 557 | 6 | none |
| Lesson 5 | 43 / 43 | 523 | 523 | 523 | 6 | none |
| Lesson 6 | 72 / 72 | 663 | 663 | 663 | 10 | none |
| Lesson 7 | 50 / 50 | 474 | 474 | 474 | 0 | none |

Lesson 3's first system (page 0, system 0: 3 bars, 17 events) is read in full and equals ground
truth. With the time signature declared as 4/4, all 66 Lesson 3 bar checks are `match`. Without a
declaration they are `time_signature_unread`, because the corpus draws time signatures as paths.
Full per-event outputs stay under `work/`.

## Limits

- **Symbols seen only in synthetic fixtures.** Whole rests, 8th, 32nd and 64th rests, flags beyond
  the eighth, 32nd and 64th notes, and double dots appear only in the synthetic fixtures. The real
  corpus confirms half, quarter and 16th rests, eighth flags, single dots, 16th beams, partial
  beams, triplets and ties.
- **One voice per staff.** Overlapping events from different stems are recorded
  `concurrent_events`.
- **Grace notes** (smaller noteheads) are not events.
- **Rests at the very start of a system.** A rest-shaped glyph before the first notehead of a
  system, but after the header, is read. A glyph that is contiguous with the clef, key and time
  signature is treated as header.
- **Time signatures drawn as paths** are not read; the bar check then needs a declared signature.
