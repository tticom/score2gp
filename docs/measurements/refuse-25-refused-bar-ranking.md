# REFUSE-25: refused-bar ranking after REFUSE-24 (measurement; task blocked, no reader change)

Baseline `42acd81` (main after REFUSE-24). Normal CLI (`convert --pdf <approved-pdf> --pdf-only-tab`) over all 43 approved PDFs in `fixtures/private/`, Windows runtime, re-measured from scratch. Counts, codes and indices only. No file under `src/` or `tests/` changed, so after equals before: every inner `Content/score.gpif` is byte-identical and no source's written GPIF changed.

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
| 73 | `note_duration_event_unread` / `tab_column_without_rhythm_mark` | 2 | reader gap; page prints no rhythm, only a spacing guess would settle it (no-guess rule) |
| 50 | `notation_note_without_tab_digit` (cascade of withheld technique digits and tie predecessors) | 5 | reader gap (bend, hammer/pull, vibrato, ties) |
| 15 | `note_duration_event_unread` / `unsupported_overlapping_form` | 5 | reader + representation gap |
| 11 | `bar_without_notation_event` | 4 | reader gap (repeat signs, stub) |
| 11 | `notehead_digit_count_mismatch` | 4 | reader gap (hammer/pull clusters) |
| 8 | `.../symbol_unclassified` | 5 | reader gap (bend arrows) |
| 8 | `.../rest_glyph_unidentified` | 1 | reader gap |
| 6 | `bar_total_mismatch` (4 distinct totals) | 3 | reader gap |
| rest | 1 to 4 each (`concurrent_events`, `mixed_notehead_kinds`, `filled_notehead_without_stem`, tuplet, fermata, parenthesized, grace, ...) | | unknown |

Classes earlier REFUSE tasks addressed are already reduced out of this ranking: ghost heads/detached parentheses (REFUSE-14, -23), empty bars (-17, -22), tied chords and carry-over ties (-11, -12), accidentals/curves (-16), chord ghost (-18), digits at refused bars (-19). Bend (-13) and hammer/pull (-15) stopped without a rule.

## Why no class could be read (acceptance 2 gate)

The identical ranking reproduces the REFUSE-24 finding: the largest class (73) has no printed rhythm and cannot be settled without a guess; every class that a single rule could settle exists in one source only (`rest_glyph_unidentified`, repeat/stub bars) or fails a different gate in each source (bend arrows), so no design/holdout source pair exists with a holdout bar written. The holdout gate is not waived; the task is reported **blocked, not complete**. All 210 refused bars stay refused with located reasons. No test was added (a test needs a rule whose removal it can detect); synthetic tests would carry no acceptance weight.
