# TABEXT-03 measurement: TAB digits printed but never reaching a bar

Normal CLI (`convert --pdf-only-tab`) over every approved PDF (43 `*.pdf` in `fixtures/private/`), `main` at e72ed5d vs this branch. Counts, codes and labels only.

## Before (re-measured)

Bars written 1410. Refused `bar_without_notation_event`: 34 = 7 `tab_digits_printed_but_not_grouped` (6 `7_Grateful_Dead_Melodies`, 1 `PARANOID`), 23 `bar_without_notation_or_tab_item` (16 Grateful, 4 Gloria, 2 EXACT, 1 PARANOID) and 4 `tab_digits_without_notation_event` (Melodic_Expressions, not in scope). The brief's 7 and 23 are confirmed.

## Cause: one stage, system geometry

Every digit-bearing bar of the two codes lies in a TAB staff whose six rows are drawn in pieces shorter than the 75 pt line filter in `pdf._detect_tab_systems`: a bar narrower than 75 pt, or a bar whose every row is interrupted by its own fret numbers. The system then ends before that stretch, starts after it, or is not detected, so the digits fall to `_nearest_system(...) is None` or `candidate_zone_contains` and are excluded as "page or legend number" (the `refined_words` loop in `pdf.py`). Causes by bar count (digit-bearing bars):

| cause | bars | sources |
|---|---|---|
| digit-interrupted staff (a row of 9 bars) not detected | 9 | Grateful |
| staff ends early / split in two by a narrow bar | ~9 | Grateful |
| leading narrow bar outside the system | 2 | Grateful (this bar was missing from the output altogether), PARANOID |
| four whole systems of a source whose rows are below the DUR-03 row evidence | 15 | PARANOID (silently absent, not even refused) |
| bars that print no digit at all | 14 | Grateful 8, Gloria 4, EXACT 2 |

Classification: every digit-bearing bar is a reader gap (system geometry). The 14 digit-free bars are blank bars, a final empty bar and simile signs: representation gap (simile) or unknown (blank); they stay refused with their located reason and are not guessed.

## Change (`pdf.py`)

* `_row_continuous_but_for_digits`: a row is continuous over a span if its drawn pieces cover it except for gaps that each lie inside a printed fret number on that row.
* `_bridged_tab_groups`: joins two groups of one staff across a stretch of 30 to 200 pt when the rows share y, every row runs across continuously (digits aside), a printed fret number lies in the stretch, and a full-height vertical stands on each side.
* `_digit_extended_tab_groups`: extends a group to the furthest full-height vertical to which all six rows run continuously, provided a fret number lies in the added span and at least three rows draw a piece of 75 pt or more inside it (a span narrower than the ordinary line filter is never evidence of more staff). A row owned by another group blocks it, except a five-row incomplete candidate wholly inside the span (the same staff).
* `_left_extended_tab_groups`: a row broken at a fret number at the start no longer blocks the extension (three rows must still continue; the rest are checked by the digit rule); also applied to the groups added or joined above.
* `_recovered_segmented_tab_groups`: unchanged. Once the base systems are whole, the existing TABEXT-01 recovery adds the digit-interrupted row of `7_Grateful_Dead_Melodies` by itself.
No gate, tolerance or row-evidence guard was loosened; each rule only joins or extends a group that is already accepted.

## Tried and removed (guards respected, reported unfinished)

Two wider versions read more and were removed because real-source tests pin the guards they bypass:

* the continuity evidence standing in for the DUR-03 row evidence when recovering a new system: +22 written bars in PARANOID (four whole systems, 15 bars, silently absent from the output today) and +9 in Melodic_Expressions, but it admits systems that `test_system_without_legacy_row_evidence_is_not_added` (Melodic pages 9 and 12) and EXACT bar 24 refuse;
* extending a group over a final bar narrower than the 75 pt line filter whose rows break at digits: wrote Melodic_Expressions bar 129 and The_EXACT bar 19 (both checked against the printed page), but `test_real_tab_recovery_topology[Melodic-Expressions-P12-reject-four-rows]` pins that bar as outside its system.
Those bars (PARANOID: 2 refused bars with printed digits and four unread systems; Melodic bar 129; EXACT bar 19) stay refused: reader gap, **unfinished**, and a maintainer decision on the pinned guards.

## After

Bars written 1410 -> 1410 (no bar newly written). `tab_digits_printed_but_not_grouped` 7 -> 1 (PARANOID bar 6), `bar_without_notation_or_tab_item` 23 -> 15 (8 Grateful, 4 Gloria, 2 EXACT, 1 PARANOID; the 14 that are not PARANOID print no digit), `note_duration_event_unread` 117 -> 132: the Grateful digit bars now reach their bar and stop at the rhythm gate `tab_column_without_rhythm_mark` (that sheet prints no rhythm; separate task). Exit codes identical for all 43 sources.

Inner `Content/score.gpif`: 37 of 38 converting sources byte-identical. The one changed is `7_Grateful_Dead_Melodies`: its output gains **one bar** (83 source bars, was 82): the leading narrow bar of the "Outro" row printed a digit but was missing from the output altogether; it is now present and refused (empty). This is not a refused bar that became written (7 written before and after); it is listed on purpose.

Grateful: all 238 printed fret numbers on its TAB rows now lie in a bar (independent word count; 238 columns in the route).

Timing: A/B on the same machine with `pdf.py` swapped (HEAD vs this branch), 12 sources, 4 parallel, two rounds: summed 125.0/125.6 s vs 125.4/126.3 s; serial 12 Bar Blues 9.0/9.4 s vs 9.2/9.4 s (an early version was 33% slower there; a per-page row index and memoised classification removed that). Whole-set wall-clock sweeps varied 2314 to 2871 s against 2105 s for the baseline sweep with identical code, i.e. machine drift; the A/B is the comparison offered.

## Verification

No bar is newly written, so there is no new bar to verify against a reference or the page. The Grateful digits (reach their bar, stay refused for rhythm) were counted against the printed page words (238 = 238).
