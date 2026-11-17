# REFUSE-26: refused-bar ranking after REFUSE-25 (measurement; task blocked, no reader change)

Baseline `545f9e7` (main after REFUSE-25). Normal CLI (`convert --pdf <approved-pdf> --pdf-only-tab`) over all 43 approved PDFs in `fixtures/private/`, Windows runtime, re-measured from scratch (not copied from REFUSE-25). Counts, codes and indices only. No file under `src/` or `tests/` changed, so after equals before: every inner `Content/score.gpif` is byte-identical and no source's written GPIF changed.

## Before (and after: nothing changed)

- Bars written: 1441. Bars refused: 210. Exit codes: 38 x 0, 4 x 4 (whole-source refusal), 1 x 2 (no bars); those 5 sources are unfinished, not correct refusals.

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
| 50 | `notation_note_without_tab_digit` (withheld technique digits, tie predecessors) | 5 (37 in one) | reader gap (bend, hammer/pull, vibrato, ties) |
| 15 | `note_duration_event_unread` / `unsupported_overlapping_form` | 5 (7, 5, 1, 1, 1) | reader + representation gap (multi-voice) |
| 11 | `bar_without_notation_event` | 4 | reader gap (repeat signs, stub) |
| 11 | `notehead_digit_count_mismatch` | 4 | reader gap (hammer/pull clusters) |
| 8 | `.../symbol_unclassified` | 5 | reader gap (bend arrows) |
| 8 | `.../rest_glyph_unidentified` | 1 | reader gap |
| 6 | `bar_total_mismatch` (4 distinct totals) | 3 | reader gap |
| 21 | 1 to 4 each (`concurrent_events`, `mixed_notehead_kinds`, `filled_notehead_without_stem`, tuplet, fermata, parenthesized, grace, ...) | | unknown |

Classes earlier REFUSE tasks addressed are excluded or reduced in this ranking: ghost heads/detached parentheses (REFUSE-14, -23), empty bars (-17, -22), tied chords and carry-over ties (-11, -12), accidentals/curves (-16), chord ghost (-18), digits at refused bars (-19). Bend (-13) and hammer/pull (-15) stopped without a rule. REFUSE-24 and -25 measured the identical ranking and were blocked.

## Why no class could be read (acceptance 2 gate)

- The largest class (73 bars, 2 sources) has no printed rhythm; settling it means inferring durations from column spacing, a guess the recovery design rejects.
- `notation_note_without_tab_digit` is a cascade of different withheld-digit causes, 37 of 50 bars in one source; no single rule is shared by a design and a holdout source.
- `unsupported_overlapping_form` needs multi-voice representation in the writer plus a per-bar reader; the bars differ in form across the 5 sources, and no rule is settled by the page across two sources.
- Every other class is one source only or fails a different gate per source.

So no design/holdout source pair exists with a holdout bar written. The holdout gate is not waived; the task is reported **blocked, not complete**. All 210 refused bars stay refused with located reasons. No test was added (a test needs a rule whose removal it can detect); synthetic tests would carry no acceptance weight, and no named mutant exists because no rule was written.
