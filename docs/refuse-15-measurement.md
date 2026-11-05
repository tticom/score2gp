# REFUSE-15 measurement: `notehead_digit_count_mismatch`

Normal CLI (`convert --pdf-only-tab`) over every approved PDF in the private set (46 PDFs), current `main` (a677425).
Counts and codes only. No source changed: this task stopped at its stop condition (see below).

Whole-set result before (and after: nothing changed): 863 bars written. Six PDFs end without a route record (CLI refusal before bars: 4 with exit 4, 1 with exit 1, 1 with exit 2), as before. Refused bars by code (ranked):

| bars | code / cause | gap kind |
|---|---|---|
| 53 | note_duration_event_unread / tab_column_without_rhythm_mark | reader gap |
| 29 | bar_without_notation_event / bar_without_notation_or_tab_item | reader gap |
| 15 | notation_note_without_tab_digit / no_tab_column_at_notation_event | reader gap (see REFUSE-13) |
| 11 | notehead_digit_count_mismatch (all `notation_has_extra`) | split below |
| 10 | notation_note_without_tab_digit / tie_stop_without_written_predecessor | reader gap (predecessor refused) |
| 9 | note_duration_event_unread / unsupported_overlapping_form | representation gap |
| 6 | note_duration_event_unread / symbol_unclassified | unknown |
| 4 | bar_total_mismatch / notation_total_below_meter | reader gap |
| 4 | note_duration_event_unread / rest_glyph_unidentified | reader gap |
| 3 | mixed_percussive_tie_ownership_unread | representation gap |
| 3 | note_duration_event_unread / concurrent_events | unknown |
| 2 each | mixed_notehead_kinds, tuplet_number_unassociated, filled_notehead_without_stem | unknown |
| 1 each | bar_total_mismatch / above_meter, overlapping_tuplets, grace_note_beat_too_far | unknown |

(REFUSE-14 already moved the parenthesised-head class into written bars.)

## The 11 bars of the task class (5 sources) are not "mostly hammer-on / pull-off clusters"

Located by page/system/bar/event from the route record and note-duration events. In 10 of 11 the event is a 2-head chord with one TAB digit; one is a 6-head chord with 4 digits.

| bars | what the records show | kind |
|---|---|---|
| 8 (3 sources) | the bar also carries unread `unsupported_overlapping_form` symbols (`accidental_beside_notehead` / `over_or_under_notehead`, curved forms) next to the heads | representation gap: accidental/curved forms unread; the bar stays refused whatever the digit count |
| 1 (Lesson-6) | event is a chord that is both a tie stop (one head) and a tie start, inside a tied chain | representation gap: which head of the chord starts the tie is not read (REFUSE-12 deliberately excludes `tie.start`; copying would invent ties on other heads) |
| 1 (Melodic_Expressions_Chap_19_) | 6-head chord, 4 digits, two heads are tie stops from a previous 2-head chord | representation gap, same tie-ownership; no reference .gp (not independently verifiable) |
| 1 (E_Chord_Lick_Chord) | 2-head chord, 1 digit, no tie on the event; the event before ends a tie on one head | unknown: the located evidence does not settle which head lacks its digit |

No bar in the class has a slur arc between adjacent heads that fixes a hammer-on or pull-off: the reader records no such arc on any of the 11 events, and the unread curved forms are accidentals, not technique arcs.

## Stop condition

The class cannot be read from the drawn notation alone: the eight overlapping-form bars need accidental/curved-form reading, the two tie-chain bars need per-head tie ownership, and the last bar is not settled. Reading any of them would mean inferring which head owns a missing digit. No rule was added; no gate was loosened. Every converted source keeps a byte-identical inner `Content/score.gpif` (code unchanged), 863 bars written before and after.
