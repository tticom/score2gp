# PDF-GROUP-02: bridging TAB string-line gaps at full-chord digit columns

Counts, codes and distances only; no private content. Source files are named only by role.

## Diagnosis (re-measured)

Two mounted PDFs (call them A and E) draw each TAB string as pieces separated by a 7.2 to 7.3 pt gap
wherever a fret digit sits. TAB string spacing is 9.66 pt, so the gap is 0.75 to 0.76 of it (notation
staff space 6.44 pt).

The investigation's description needed one correction. `_LineSegment.is_horizontal` keeps only
primitives of at least 75 pt, so the merge sees a string only through its long pieces. On a chord
column the left piece of every string is long, but on strings that continue as a run of short,
digit-broken pieces the right piece is dropped before the merge. The merge therefore sees, at the first
chord of A, rows with a break edge at the column on all 6 strings, but a complete left-and-right pair
on only 3 of them, and on the others no matching right piece.

Pass 2 of `merge_collinear_horizontal_segments` bridges a gap over 5.0 pt only if another line 2 to 45 pt
away spans it (here only the top TAB string, via the notation staff's lowest line 37 pt above) or if at
least 4 rows show the same left-and-right split. Neither holds for the remaining strings, so they stay
split. `_tab_line_groups` then yields a partial 6-line TAB group plus a 5-line `incomplete_tab_candidate`
group (A: 3 groups instead of 2; E: 6 TAB groups for 4 staves). The incomplete group is a second system
topology over the same vertical range, so the joint left stroke and the TAB-height rectangle barlines
overlap two topologies and get `primitive_to_system = None`.

| | base | head |
|---|---|---|
| A: staff groups (notation / TAB / incomplete) | 1 / 1 / 1 | 1 / 1 / 0 |
| A: barlines owned by the system | 4 (left stroke missing) | 5 |
| E: TAB groups for 4 staves | 6 | 4 |
| E: systems missing the left stroke | 2 (systems 2 and 4) | 0 |

## Rule

`_is_full_chord_gap` (in `pdf_geometry.py`) bridges a pass-2 gap when all of these hold:

* the gap is at most `FULL_CHORD_GAP_MAX_STRING_SPACING_RATIO` (0.8) of the string spacing;
* at least `FULL_CHORD_GAP_MIN_STRINGS` (4) rows have a break edge at the same x (a piece ends at the
  gap start or a piece begins at the gap end, within `FULL_CHORD_GAP_ALIGNMENT_TOLERANCE` = 1.5 pt);
* those rows form a run of uniform spacing (each step within 15% of the median) containing the gap's row.

The string spacing is measured from the rows themselves (the median step between the aligned rows), so
the limit is a multiple of the measured spacing; no new absolute point value limits the gap. The
unchanged 5.0 pt and 45.0 pt constants of the existing rule are not touched.

Why 4 rows and not 6: the merge only sees pieces of at least 75 pt, so a string whose neighbours of a
chord are all short pieces shows no edge at the column. In E (one system) only 4 of 6 strings show an edge
at the column; requiring 6 would leave the system split. Four evenly spaced rows with the same break edge
inside 0.8 of their spacing is not something two staves on one line can produce: they are separated by
many times that gap.

"Flanked by a digit" is not used: the merge receives line segments only, not page text.

## Not changed

* The 75 pt filter, the 5.0 / 45.0 / 120.0 / 360.0 constants, `build_ir.py` gating sets.
* The existing exit code 0 when bars are refused at the note-type route and written with 0 ticks (see
  the PR; reported, not fixed).
