# REFUSE-20: refused-bar ranking after REFUSE-19 (counts and codes only)

Measured at `d1076ab` with the normal CLI (`convert --pdf-only-tab`) over all 43 approved PDFs.
No private content is recorded here. No reader change was made by this task (see "Outcome").

## Totals (before = after; no code changed)

- Bars written: 1423. Bars refused: 228. Sources refused whole: 5 (`pdf_only_tab_grouping_unsafe` x4, `pdf_only_tab_no_notation_bars` x1).
- Refused by code: note_duration_event_unread 130, notation_note_without_tab_digit 53, bar_without_notation_event 20,
  notehead_digit_count_mismatch 10, bar_total_mismatch 6, tie_head_ownership_unconfirmed 2,
  tab_system_digit_unassigned_to_bar 2, tab_digit_without_notation_event 2, duration_off_tick_grid 1,
  notation_tab_column_ambiguous 1, tab_chord_arrow_unread 1.

## Causes ranked by bar count (classification is never "correct refusal")

| bars | cause | classification |
|---:|---|---|
| 73 | tab_column_without_rhythm_mark (TAB prints no rhythm; only spacing/counting would give one) | reader gap, not settled by the page |
| 44 | no_tab_column_at_notation_event | representation gap (bend/technique heads, see below) |
| 15 | bar_without_notation_or_tab_item | unknown (stub/empty bars; nothing printed to read) |
| 15 | unsupported_overlapping_form | reader gap (accidentals, grace heads, rolled-chord arrow, bend heads) |
| 13 | rest_glyph_unidentified | reader gap (measured glyphs are bend-notehead forms, not rests) |
| 11 | symbol_unclassified | reader gap |
| 9 | tie_stop_without_written_predecessor | reader gap (predecessor bar is itself a bend bar) |
| <=4 each | the remaining 20 causes | reader gap / representation gap / unknown |

Cross-cutting family: 54 refused bars carry a withheld TAB-digit recovery caused by a printed technique mark
(printed_technique_owner_unread 28, tab_digit_run_or_parenthesis_unread 14, printed_tab_mark_unread 10,
printed_rhythm_completion_unread 2). Viewing the pages, these are bend / bend-and-release / quarter-bend
notation: the notation staff prints an extra parenthesised or small head for the bent pitch, and the TAB prints
an arrow with "full", "1/2" or "1/4" instead of a digit. It is the largest page-settled class, but reading it
safely needs a bend representation in the writer (bend origin/destination values, release, quarter tones) and a
rule that the extra heads are not played notes. Writing those bars without the bend would drop printed content.

## REFUSE-19 classes

REFUSE-19 read bare palm marks and bar-key glyphs (3 bars written). They are excluded from this ranking: none of
the refused classes above is a bare palm mark or a bar key glyph.

## Outcome

No class was read: the 73-bar class is not settled by the page (it needs the separate spacing-guess authority),
and the bend/technique family needs a writer representation that this task could not verify against a reference.
Every bar above stays refused with its located reason and is reported as unfinished. No gate was loosened.
