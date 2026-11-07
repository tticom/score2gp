# TABEXT-02 measurement: bars that still lack a TAB column

Normal CLI (`convert --pdf-only-tab`) over every approved PDF in the private set (43 PDFs), `main` at 35e0b82 vs this branch.
Counts, codes and labels only.

## Before / after (whole set)

Bars written 899 -> 901. Refused 157 -> 155. Exit codes identical for all 43 sources. Sources whose inner `Content/score.gpif`
changed: 1 (`The_EXACT_System_Pros...`, +2 written bars, source bars 18 and 93). The other 36 converting sources are byte-identical
(SHA-256). Summed conversion wall-clock (4 in parallel) 757 s -> 722 s: no slowdown; the new pass only reads a page's glyphs
when a digit word that is not a fret (e.g. "1110") lies on a TAB system.

Refused by code, after: 58 tab_column_without_rhythm_mark; 23 bar_without_notation_or_tab_item; 13 no_tab_column_at_notation_event
(was 15); 9 notehead_digit_count_mismatch; 9 unsupported_overlapping_form; 8 tie_stop_without_written_predecessor;
7 tab_digits_printed_but_not_grouped; 6 symbol_unclassified; 6 bar_total_mismatch; 3 each concurrent_events, rest_glyph_unidentified;
2 each mixed_notehead_kinds, tuplet_number_unassociated, filled_notehead_without_stem; 1 each duration_off_tick_grid (new, see below),
overlapping_tuplets, grace_note_beat_too_far, tie_head_ownership_unconfirmed, unclassified_mark_below_strings.

## The 13 remaining `no_tab_column_at_notation_event` bars (all reader or representation gaps, none a correct refusal)

| bars | source | cause | kind |
|---|---|---|---|
| 6 | PARANOID - BLACK SABBATH (pages 0 and 2) | event 0 of three consecutive bars with no TAB column; not measured further | reader gap, unknown |
| 2 | The_EXACT (page 0 bar 19; page 1 bar 40), 1 This_Boring (page 1 bar 46), 1 The_EXACT (page 0 bar 24) | digits printed (bar 19: two stacked two-digit frets kept as `pdf_candidate_outside_system` / `outside_bar`, i.e. just after a barline outside the detected system geometry); bar 24 is the 2-legacy-row system | reader gap |
| 1 | Am-blues-lick bar 0 | bend target on a grace-note beam | representation gap |
| 1 | Black Dog bar 1 | tied chord printed as empty brackets | representation gap |

(The_EXACT page 1 bar 40 and This_Boring bar 46 have no digit located at the event: unknown.)

## Read by this task

* A PDF word of adjacent fret digits ("1110", "1314", "107") is split at the glyph-pitch breaks where the page's own in-fret
  pitch for that digit pair (same font and size, taken from two-digit frets on the same page) settles it. Each piece must be a
  printable fret (<= 24, no leading zero). Words that are not frets and cannot be so settled stay as before.
* The_EXACT bar 18 ("1110" = 11, 10) and bar 93 ("1314" = 13, 14): written; no reference .gp: checked against the printed page
  (every fret in order); NOT independently verified against a file.
* Back In Black bar 7 ("107" = 10, 7): the run is read; the bar then matches in full but holds a 22-note tuplet (1/11 quarter)
  that the 960-tick grid cannot hold. That duration used to refuse the WHOLE source (exit 2) once reached; it now refuses that
  bar alone as `duration_off_tick_grid` (representation gap). Unfinished.
