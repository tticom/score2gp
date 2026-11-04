# REFUSE-13 measurement: `notation_note_without_tab_digit` / `no_tab_column_at_notation_event`

Normal CLI (`convert --pdf-only-tab`) over every approved PDF in the private set (46 PDFs), current `main` (5e68461).
Counts and codes only. No source changed: this task stopped at its stop condition (see below).

Whole-set result before (and after: nothing changed): 857 bars written. Refused bars by code (ranked):

| bars | code / cause | gap kind |
|---|---|---|
| 53 | note_duration_event_unread / tab_column_without_rhythm_mark | reader gap |
| 29 | bar_without_notation_event / bar_without_notation_or_tab_item | reader gap |
| 15 | notation_note_without_tab_digit / no_tab_column_at_notation_event | split below |
| 11 | notehead_digit_count_mismatch | reader gap |
| 10 | notation_note_without_tab_digit / tie_stop_without_written_predecessor | reader gap (predecessor refused) |
| 9 | note_duration_event_unread / unsupported_overlapping_form | representation gap |
| 6 | note_duration_event_unread / symbol_unclassified | unknown |
| 6 | note_duration_event_unread / parenthesized_head_unrepresented | representation gap |
| 4 | bar_total_mismatch / notation_total_below_meter | reader gap |
| 4 | note_duration_event_unread / rest_glyph_unidentified | reader gap |
| 3 | mixed_percussive_tie_ownership_unread | representation gap |
| 3 | note_duration_event_unread / concurrent_events | unknown |
| 2 | mixed_notehead_kinds, 2 tuplet_number_unassociated, 2 filled_notehead_without_stem | unknown |
| 1 | bar_total_mismatch / above_meter, overlapping_tuplets, grace_note_beat_too_far | unknown |

## The 15 bars of the task class (8 sources) are not "mostly bend-target heads"

Re-measured by looking at the located bar on the printed page and at the TabRaw candidates in it:

| bars | what is printed | why no TAB column | kind |
|---|---|---|---|
| 8 (4 sources) | ordinary fret digits (chords, single notes) | TabRaw excluded them before the route: `pdf_fret_page_or_legend_number_excluded`, `pdf_fret_multidigit_extracted`, `pdf_fret_digits_not_merged_exceeds_max_fret`, `pdf_fret_digit_symbol_overlap_ambiguous` | reader gap in TAB extraction, not notation |
| 1 | a tied chord whose TAB digits are bracketed, at a system start | bracketed digits excluded as `pdf_fret_page_or_legend_number_excluded` | reader gap |
| 1 (Am-blues-lick) | two bracketed heads on beamed 16ths after a grace note, bend label "full" over the TAB | the bracketed head is the bend target; no digit | representation gap (bend on a grace note) |
| 5 (4 sources) | the first unmatched event has fewer TAB columns than heads; cause not settled by the located evidence (adjacent digits, slide/grace digit) | not settled | unknown |

Only one bar prints a bend-target head. It also carries `accidental_beside_notehead` and `over_or_under_notehead`
unread symbols, so reading the bend target alone would not write it.

## Stop condition

Reading the bend-target head needs the target fret (string and fret of a note with no printed digit) derived from the
bend amount, plus a representation for a grace-note bend whose destination is a duration-bearing beat. TABRHY-01 only
established that a bend target is no note; it records no representation for a duration-bearing target head. No
bend-target head is read; no gate was loosened. The eight TAB-extraction bars are the larger real class and belong to a
separate TabRaw task.
