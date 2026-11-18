# REFUSE-27: refused-bar ranking after REFUSE-26 (measurement; task blocked, no reader change)

Baseline `16414f9` (main after REFUSE-26). Normal CLI (`convert --pdf <approved-pdf> --pdf-only-tab`) over the 42 approved PDFs that carry music in `fixtures/private/` (the blank No Notes file excluded), Windows runtime, re-measured from scratch. Counts, codes and indices only. No file under `src/` or `tests/` changed, so after equals before: every inner `Content/score.gpif` is byte-identical and no source's written GPIF changed.

## Before (and after: nothing changed)

- Exit codes: 37 x 0, 4 x 4 (whole-source refusal), 1 x 2 (no bars). Those 5 sources are unfinished, not correct refusals.
- Bars written: 1432 and bars refused: 210, counted from the per-bar `note-type-route.json` of the 38 sources that emit one (the 4 whole-source refusals emit none, so they add no per-bar rows). REFUSE-26 reported 1441 written and the same 210 refused; the written totals differ by 9 because of how whole-source sources are tallied, the refused ranking is identical.

| Refused bars by code | n | sources |
|---|---:|---:|
| `note_duration_event_unread` | 123 | 12 |
| `notation_note_without_tab_digit` | 50 | 5 |
| `bar_without_notation_event` | 11 | 4 |
| `notehead_digit_count_mismatch` | 11 | 4 |
| `bar_total_mismatch` | 6 | 3 |
| `tie_head_ownership_unconfirmed` / `tab_system_digit_unassigned_to_bar` / `tab_digit_without_notation_event` | 2 each | 2 / 1 / 1 |
| `tab_chord_arrow_unread` / `notation_tab_column_ambiguous` / `duration_off_tick_grid` | 1 each | 1 each |

## Located causes ranked by bar count (all unfinished; none a correct refusal)

| bars | code / cause | sources | gap kind |
|---:|---|---:|---|
| 73 | `note_duration_event_unread` / `tab_column_without_rhythm_mark` | 2 (68 + 5) | reader gap; the page prints no rhythm, only a spacing guess would settle it (no-guess rule) |
| 42 | `notation_note_without_tab_digit` / `no_tab_column_at_notation_event` | 4 (37, 4, 4, 1 across them) | reader gap (technique digits withheld, no tab column at the notation event) |
| 15 | `note_duration_event_unread` / `unsupported_overlapping_form` | 5 (7, 5, 1, 1, 1) | reader + representation gap (multi-voice) |
| 8 | `notation_note_without_tab_digit` / `tie_stop_without_written_predecessor` | 3 | cascade, see below |
| 8 | `note_duration_event_unread` / `symbol_unclassified` | 5 | reader gap (bend arrows) |
| 8 | `note_duration_event_unread` / `rest_glyph_unidentified` | 1 | reader gap |
| 9 | `notehead_digit_count_mismatch` (`printed_technique_owner_unread`, count only, vibrato chord, digit run/parenthesis) | 4 | reader gap (hammer/pull clusters) |
| 11 | `bar_without_notation_event` (`bar_without_notation_or_tab_item` 6, digits without notation event 4, digits not grouped 1) | 4 | reader gap (repeat signs, stub) |
| 6 | `bar_total_mismatch` (4 distinct totals) | 3 | reader gap |
| 28 | 1 to 4 each (`concurrent_events`, `mixed_notehead_kinds`, `filled_notehead_without_stem`, tuplet, fermata, parenthesized, grace, tie head, off-grid, chord arrow, ...) | | unknown |

Classes earlier REFUSE tasks addressed are excluded or reduced in this ranking: ghost heads/detached parentheses (REFUSE-14, -23), empty bars (-17, -22), tied chords and carry-over ties (-11, -12), accidentals/curves (-16), chord ghost (-18), digits at refused bars (-19). Bend (-13) and hammer/pull (-15) stopped without a rule. REFUSE-24, -25 and -26 measured the identical ranking and were blocked.

## Why no class could be read (acceptance 2 gate)

- The largest class (73 bars, 2 sources) has no printed rhythm; settling it means inferring durations from column spacing, a guess the recovery design rejects.
- `no_tab_column_at_notation_event` (42 bars): 37 sit in one source and the other three hold 4, 4 and 1 bars with different bar shapes (some with zero tab digits in the bar, some one column short). No single page-settled rule is shared by a design source and a holdout source that writes a bar.
- `tie_stop_without_written_predecessor` (8 bars, 3 sources) was checked this run as a possible shared rule: in every case the bar's predecessor is itself refused (`notation_note_without_tab_digit`, `concurrent_events`, `mixed_notehead_kinds`, `tuplet_number_unassociated`), so the tie stop has no written head to attach to. It is a downstream cascade of other classes, not a class with its own page-settled rule; writing it would require guessing the predecessor's head.
- `unsupported_overlapping_form` needs multi-voice representation in the writer plus a per-bar reader; the bars differ in form across the 5 sources.
- Every other class is one source only or fails a different gate per source.

So no design/holdout source pair exists with a holdout bar written. The holdout gate is not waived; the task is reported **blocked, not complete**. All 210 refused bars stay refused with located reasons. No test was added (a test needs a rule whose removal it can detect); synthetic tests would carry no acceptance weight, and no named mutant exists because no rule was written.
