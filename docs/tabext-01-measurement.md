# TABEXT-01 measurement: fret digits that TAB extraction excluded before the route

Normal CLI (`convert --pdf-only-tab`) over every approved PDF in the private set (43 `*.pdf` files in `fixtures/private/`;
REFUSE-13/15 counted 46 files including the `.gp` references), `main` at a53b74a. Counts, codes and labels only.

## Before / after (whole set)

Bars written 863 -> 869 (+6). Refused bars by code (after; the only ranks that moved are marked):

| bars (before -> after) | code / cause | gap kind |
|---|---|---|
| 53 | note_duration_event_unread / tab_column_without_rhythm_mark | reader gap |
| 29 | bar_without_notation_event | reader gap |
| 25 -> 19 | notation_note_without_tab_digit (15 -> 9 `no_tab_column_at_notation_event`; 10 `tie_stop_without_written_predecessor`) | see below |
| 11 | notehead_digit_count_mismatch | reader gap / representation gap (REFUSE-15) |
| 9 | note_duration_event_unread / unsupported_overlapping_form | representation gap |
| 6 | note_duration_event_unread / symbol_unclassified | unknown |
| 4 | note_duration_event_unread / rest_glyph_unidentified | reader gap |
| 5 | bar_total_mismatch | reader gap / unknown |
| 3 | mixed_percussive_tie_ownership_unread | representation gap |
| 3 | note_duration_event_unread / concurrent_events | unknown |
| 2 each | mixed_notehead_kinds, tuplet_number_unassociated, filled_notehead_without_stem | unknown |
| 1 each | overlapping_tuplets, grace_note_beat_too_far | unknown |

Exit codes are identical for all 43 sources. Sources whose written GPIF changed: 3 (12 Bar Blues Solo Guitar Jam +4, E_Chord_Lick_Chord +1, Ex 2 Hands Up +1). The other 34 converting
sources keep a byte-identical inner `Content/score.gpif` (SHA-256 compared before/after). Six sources end without a
route record (CLI refusal before bars) before and after; the pass adds systems to two of them
(`PARANOID - BLACK SABBATH.pdf`, `Melodic_Expressions.pdf`: pages 7 and 31 gain systems; pages 9 and 12, the DUR-03 negative controls, gain none) but their refusal is earlier (time signature unread /
earlier gate), so no bar of theirs changes.

Excluded digit candidates outside every system (`pdf_fret_page_or_legend_number_excluded`): 987 -> 918 across the set.

## The 15 bars of `no_tab_column_at_notation_event`: located cause

| bars | sources | located cause | result |
|---|---|---|---|
| 4 | 12 Bar Blues Solo Guitar Jam (page 0, system 5, bars 20-23) | a TAB-only system whose painted rows are cut by every digit (knock-out gap) is not detected, so all its digits are excluded as page/legend numbers | written, no reference .gp: checked against the printed page (beat and note counts); NOT independently verified against a file |
| 1 | E_Chord_Lick_Chord (page 0, system 4, bar 15) | same system-detection gap; tied chord printed in brackets at a system start | written, no reference .gp: printed page; NOT independently verified against a file |
| 1 | The_EXACT_System_Pros... (page 0, system 4, bar 24) | same system-detection gap (chord-diagram page); only 2 legacy rows intact, below the DUR-03 evidence bar (3 intact or 5 legacy rows) | unfinished: reader gap, stays refused with its located reason |
| 1 | Ex 2 Hands Up (page 0, system 1, bar 5, event 6) | "0" glyph merged with the next digits into `012` (fret 12), the open string lost | written; bar equals the reference .gp bar (found by content) |
| 1 | Am-blues-lick (bar 0) | bracketed head is a bend target on a grace-note beam (REFUSE-13) | unfinished: representation gap |
| 1 | Back_In_Black (system 3, bar 7) | two adjacent two-digit/one-digit frets arrive as one PDF word of three digits (`chord_text_digit_excluded`) | unfinished: reader gap; one glyph run cannot be split into frets from spacing alone |
| 1 | Black_Dog (bar 1, event 2) | tied chord printed as empty brackets; no digit exists on the page | unfinished: representation gap |
| 1 | The_EXACT_System_Pros... (page 0, bar 18, event 6) | three adjacent two-digit frets arrive as one four-digit word (`digits_not_merged_exceeds_max_fret`) | unfinished: reader gap, glyph run not settleable |
| 1 | The_EXACT_System_Pros... (page 0, bar 19, event 0) | two stacked two-digit candidates kept with `pdf_candidate_outside_system` | unfinished: reader gap, cause not settled |
| 3 | The_EXACT_System_Pros... (page 1 bar 40, page 3 bar 93), This_Boring... (page 1 bar 46) | no excluded digit located at the event; cause not settled by the located evidence | unfinished: unknown |

No refused class is a correct refusal; every approved fixture except the blank No Notes file is real teaching material.

## What the excluded digit groups are on the printed page (viewed)

* Digits between systems on a TAB-only page, in rows of equal spacing under a chord name: fret digits of an undetected system.
* Bracketed `(0)(0)(6)` under a notation staff at a system start: a tied chord's fret digits.
* Digits above/below systems that are bar numbers, section numbers and chord-diagram fret labels: not frets, stay excluded.
* `1110`/`107`-style runs: adjacent frets with no printed gap; stay excluded.

## Method note

The paint-recovery detection pass (`_recover_paint=True`) already joins digit-interrupted rows but ran only on
music-font pages or pages with no accepted system. `_digit_interrupted_systems_added` now runs it on a page whose base
systems carry no warning and that has a digit word outside every base system, and accepts it only when every base
system keeps its rows, it adds a system, it has no grouping warning and each added system has six rows, the DUR-03
legacy-row evidence (three rows intact over the staff width, or five rows already drawn by the 75 pt filter) and a fret
digit (bracketed allowed) on its own rows. Base system objects are kept unchanged. Cost: the pass ran on 73 pages of
the set; summed wall-clock of the 43 conversions 885 s -> 1005 s (4 in parallel, noisy).
