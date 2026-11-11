# REFUSE-20: refusal census and unread-inventory diagnostic

This revision remains unfinished: 0 newly written bars; no finished reader, holdout reader result or drop-reader-rule acceptance test.

Baseline: `06206ccc108ea31ab4265996f9d409682c3d21e6`. All 43 approved PDFs exist and match the manifest hashes.
Both whole-set runs used the checkout virtualenv and normal strict CLI:
`python -m score2gp.cli convert --pdf <approved-pdf> --pdf-only-tab --out <ignored-output> --work-dir <ignored-build> --json-report <ignored-report>`.
No sidecar or reference was supplied. Exact commands, exit statuses, inputs and outputs remain in ignored storage.
The after run includes the diagnostic-retention change in `src/score2gp/cli.py`; it is a working-tree result, not an exact published-head receipt.

## Measurement boundary

The CLI previously discarded the fallback TAB inventory when its read-event count was zero. Source 3 has 9 inventory bars and 52 unread event records.
The unchanged reader was probed before the edit; the modified normal CLI retains its complete result in `tab-rhythm.json`.
Those 9 bars are now included. Their refusal code is the source CLI code propagated to its inventory bars; their located causes come from the retained unread event records.
The baseline normal CLI did not retain these per-bar diagnostics; the supplemental baseline reader probe is not claimed as baseline CLI evidence.

The maintainer exclusion applies only to source indices 22, 25, 27 and 33: these four sources have no bar inventory and remain unfinished reader gaps.
They are measured at source level and excluded from the bar-count ranking. No refusal is labelled correct.
The ranking describes first located diagnostic causes, not a verified semantic reading of a class. The largest page-settled implementable class remains unproven.

## Before and after

| Channel | Before | After |
|---|---:|---:|
| Packages | 38 | 38 |
| Written bars | 1423 | 1423 |
| Refused inventory bars, including the 9 discarded diagnostics | 237 | 237 |
| Sources without a bar inventory | 4 | 4 |
| Newly written bars | 0 | 0 |
| Changed inner GPIF packages | 0 | 0 |

All 38 existing inner `Content/score.gpif` members are byte-identical in the fresh before/after comparison. Every CLI exit status is unchanged. No changed written source exists to list.
No new bar exists for reference/page verification. No conversion fidelity improvement or independent verification is claimed. Reference-less sources remain not independently verified.

## Refused bars by code

| Code ID | Code | Before | After |
|---|---|---:|---:|
| R01 | `pdf_only_tab_no_notation_bars` | 9 | 9 |
| R02 | `note_duration_event_unread` | 130 | 130 |
| R03 | `bar_without_notation_event` | 20 | 20 |
| R04 | `notation_note_without_tab_digit` | 53 | 53 |
| R05 | `duration_off_tick_grid` | 1 | 1 |
| R06 | `notehead_digit_count_mismatch` | 10 | 10 |
| R07 | `bar_total_mismatch` | 6 | 6 |
| R08 | `tie_head_ownership_unconfirmed` | 2 | 2 |
| R09 | `tab_system_digit_unassigned_to_bar` | 2 | 2 |
| R10 | `notation_tab_column_ambiguous` | 1 | 1 |
| R11 | `tab_digit_without_notation_event` | 2 | 2 |
| R12 | `tab_chord_arrow_unread` | 1 | 1 |

## First causes ranked by bar count

| Cause ID | Cause code | Bars | Classification |
|---|---|---:|---|
| C01 | `tab_column_without_rhythm_mark` | 82 | reader_gap |
| C02 | `no_tab_column_at_notation_event` | 44 | reader_gap |
| C03 | `bar_without_notation_or_tab_item` | 15 | unknown |
| C04 | `unsupported_overlapping_form` | 15 | reader_gap |
| C05 | `rest_glyph_unidentified` | 13 | reader_gap |
| C06 | `symbol_unclassified` | 11 | reader_gap |
| C07 | `tie_stop_without_written_predecessor` | 9 | reader_gap |
| C08 | `printed_technique_owner_unread` | 4 | reader_gap |
| C09 | `concurrent_events` | 4 | unknown |
| C10 | `notehead_digit_count_mismatch` | 4 | reader_gap |
| C11 | `notation_total_below_meter` | 4 | unknown |
| C12 | `tab_digits_without_notation_event` | 4 | reader_gap |
| C13 | `mixed_notehead_kinds` | 3 | unknown |
| C14 | `filled_notehead_without_stem` | 3 | reader_gap |
| C15 | `notation_total_above_meter` | 2 | unknown |
| C16 | `tuplet_number_unassociated` | 2 | reader_gap |
| C17 | `tab_digit_run_or_parenthesis_unread` | 2 | reader_gap |
| C18 | `tie_head_ownership_unconfirmed` | 2 | reader_gap |
| C19 | `tab_system_digit_unassigned_to_bar` | 2 | reader_gap |
| C20 | `tab_digit_without_notation_event` | 2 | reader_gap |
| C21 | `parenthesized_head_unrepresented` | 2 | reader_gap |
| C22 | `duration_not_whole_ticks` | 1 | representation_gap |
| C23 | `overlapping_tuplets` | 1 | reader_gap |
| C24 | `grace_note_beat_too_far` | 1 | reader_gap |
| C25 | `notation_tab_column_ambiguous` | 1 | reader_gap |
| C26 | `rest_glyph_beside_note` | 1 | unknown |
| C27 | `straight_chord_arrow_unread` | 1 | reader_gap |
| C28 | `tab_digits_printed_but_not_grouped` | 1 | reader_gap |
| C29 | `unclassified_mark_below_strings` | 1 | reader_gap |

## Source-level unfinished gaps

| Source index | Refusal code | Located cause code | Classification |
|---:|---|---|---|
| 22 | `pdf_only_tab_grouping_unsafe` | `scanned_raster_source_without_vector_tab` | reader_gap |
| 25 | `pdf_only_tab_grouping_unsafe` | `scanned_raster_source_without_vector_tab` | reader_gap |
| 27 | `pdf_only_tab_grouping_unsafe` | `text_without_tab_rows` | reader_gap |
| 33 | `pdf_only_tab_grouping_unsafe` | `ascii_tab_rows_without_barlines_or_rhythm` | reader_gap |

## REFUSE-19 exclusion

REFUSE-19 addressed bare palm marks and positively read bar-key glyphs. Its 1 palm-mark bar and 2 key-glyph bars remain written in both fresh runs; these addressed causes are absent from this refused-bar selection.

## Diagnostic regression and limit

`test_cli_retains_every_unread_tab_bar_without_writing_music` fails at the baseline on the missing diagnostic file. After the change it and 6 existing PERCX/NOROUTE tests pass.
`DROP_UNREAD_TAB_INVENTORY` suppresses only the new diagnostic write and causes the same real-source test to fail. This is persistence evidence only; it is not the required drop-new-reader-rule mutant.
Synthetic tests carry zero recognition, grouping, geometry, timing or fidelity acceptance weight. No synthetic test was added.
The 52-record assertion checks retained diagnostics, not independent correctness of every event grouping. The printed page independently establishes the 9-bar inventory.

## Reader disconfirmation

A tied-parenthesis prototype tentatively accepted source-index 35 bars 68, 71 and 523.
The builder produced 0 vibrato techniques in each of these 3 bars despite printed waves.
The production prototype was withdrawn; the existing reader remains unchanged.
`test_printed_tied_tab_parentheses_keep_the_chord_and_rhythm` retains the unmet requirement,
including tie, rhythm and vibrato assertions in the output channels. It is not a passing acceptance test.
The finished reader, largest settled-class selection, holdout and real-source drop-reader-rule mutant remain unfinished.

## Located refused-bar inventory

Source indices follow the sorted PDF inventory. Page, system, bar and event indices are zero-based. Each bar appears once; `?` denotes an unavailable event index, never an invented event.
These are diagnostic locations, not completed per-bar semantic verification. All listed bars remain unfinished.

| Source index | Page | System | Bar | Event | Code ID | Cause ID |
|---:|---:|---:|---:|---:|---|---|
| 3 | 0 | 0 | 0 | 0 | R01 | C01 |
| 3 | 0 | 0 | 1 | 0 | R01 | C01 |
| 3 | 0 | 1 | 2 | 0 | R01 | C01 |
| 3 | 0 | 1 | 3 | 0 | R01 | C01 |
| 3 | 0 | 2 | 4 | 0 | R01 | C01 |
| 3 | 0 | 3 | 5 | 0 | R01 | C01 |
| 3 | 0 | 3 | 6 | 0 | R01 | C01 |
| 3 | 0 | 4 | 7 | 0 | R01 | C01 |
| 3 | 0 | 4 | 8 | 0 | R01 | C01 |
| 4 | 0 | 0 | 0 | 0 | R02 | C01 |
| 4 | 0 | 0 | 1 | 0 | R02 | C01 |
| 4 | 0 | 0 | 4 | 0 | R02 | C01 |
| 4 | 0 | 0 | 5 | 0 | R02 | C01 |
| 4 | 0 | 1 | 8 | 0 | R02 | C01 |
| 4 | 0 | 1 | 9 | 0 | R02 | C01 |
| 4 | 0 | 1 | 12 | 0 | R02 | C01 |
| 4 | 0 | 1 | 13 | 0 | R02 | C01 |
| 4 | 0 | 1 | 14 | 0 | R02 | C01 |
| 4 | 0 | 1 | 16 | ? | R03 | C03 |
| 4 | 0 | 2 | 17 | 0 | R02 | C01 |
| 4 | 0 | 2 | 18 | 0 | R02 | C01 |
| 4 | 0 | 2 | 19 | 0 | R02 | C01 |
| 4 | 0 | 2 | 20 | 0 | R02 | C01 |
| 4 | 0 | 2 | 21 | 0 | R02 | C01 |
| 4 | 0 | 3 | 22 | 0 | R02 | C01 |
| 4 | 0 | 3 | 23 | 0 | R02 | C01 |
| 4 | 0 | 3 | 24 | 0 | R02 | C01 |
| 4 | 0 | 3 | 25 | 0 | R02 | C01 |
| 4 | 0 | 3 | 26 | 0 | R02 | C01 |
| 4 | 0 | 4 | 27 | 0 | R02 | C01 |
| 4 | 0 | 4 | 28 | 0 | R02 | C01 |
| 4 | 0 | 4 | 29 | 0 | R02 | C01 |
| 4 | 0 | 4 | 30 | 0 | R02 | C01 |
| 4 | 0 | 4 | 31 | 0 | R02 | C01 |
| 4 | 0 | 4 | 32 | 0 | R02 | C01 |
| 4 | 0 | 4 | 33 | 0 | R02 | C01 |
| 4 | 0 | 4 | 34 | 0 | R02 | C01 |
| 4 | 0 | 4 | 35 | 0 | R02 | C01 |
| 4 | 0 | 5 | 36 | 0 | R02 | C01 |
| 4 | 0 | 5 | 37 | 0 | R02 | C01 |
| 4 | 0 | 5 | 38 | 0 | R02 | C01 |
| 4 | 0 | 5 | 39 | 0 | R02 | C01 |
| 4 | 0 | 5 | 40 | 0 | R02 | C01 |
| 4 | 0 | 5 | 41 | 0 | R02 | C01 |
| 4 | 0 | 5 | 42 | 0 | R02 | C01 |
| 4 | 0 | 5 | 43 | 0 | R02 | C01 |
| 4 | 0 | 5 | 44 | 0 | R02 | C01 |
| 4 | 0 | 6 | 45 | 0 | R02 | C01 |
| 4 | 0 | 6 | 46 | ? | R03 | C03 |
| 4 | 0 | 6 | 47 | 0 | R02 | C01 |
| 4 | 0 | 6 | 48 | 0 | R02 | C01 |
| 4 | 0 | 6 | 49 | ? | R03 | C03 |
| 4 | 0 | 6 | 50 | 0 | R02 | C01 |
| 4 | 0 | 6 | 51 | 0 | R02 | C01 |
| 4 | 0 | 6 | 52 | 0 | R02 | C01 |
| 4 | 0 | 7 | 53 | 0 | R02 | C01 |
| 4 | 0 | 7 | 54 | 0 | R02 | C01 |
| 4 | 0 | 7 | 55 | ? | R03 | C03 |
| 4 | 0 | 7 | 56 | ? | R03 | C03 |
| 4 | 0 | 7 | 57 | 0 | R02 | C01 |
| 4 | 0 | 7 | 58 | 0 | R02 | C01 |
| 4 | 0 | 8 | 59 | 0 | R02 | C01 |
| 4 | 0 | 8 | 60 | 0 | R02 | C01 |
| 4 | 0 | 8 | 61 | 0 | R02 | C01 |
| 4 | 0 | 8 | 62 | ? | R03 | C03 |
| 4 | 0 | 8 | 63 | 0 | R02 | C01 |
| 4 | 0 | 8 | 64 | 0 | R02 | C01 |
| 4 | 0 | 8 | 65 | 0 | R02 | C01 |
| 4 | 0 | 8 | 66 | ? | R03 | C03 |
| 4 | 1 | 0 | 67 | 0 | R02 | C01 |
| 4 | 1 | 0 | 68 | 0 | R02 | C01 |
| 4 | 1 | 0 | 69 | 0 | R02 | C01 |
| 4 | 1 | 0 | 70 | 0 | R02 | C01 |
| 4 | 1 | 0 | 71 | 0 | R02 | C01 |
| 4 | 1 | 0 | 72 | 0 | R02 | C01 |
| 4 | 1 | 0 | 73 | 0 | R02 | C01 |
| 4 | 1 | 0 | 74 | 0 | R02 | C01 |
| 4 | 1 | 0 | 75 | ? | R03 | C03 |
| 4 | 1 | 1 | 76 | 0 | R02 | C01 |
| 4 | 1 | 1 | 77 | 0 | R02 | C01 |
| 4 | 1 | 2 | 78 | 0 | R02 | C01 |
| 4 | 1 | 2 | 79 | 0 | R02 | C01 |
| 4 | 1 | 2 | 80 | 0 | R02 | C01 |
| 4 | 1 | 2 | 81 | 0 | R02 | C01 |
| 4 | 1 | 2 | 82 | 0 | R02 | C01 |
| 7 | 0 | 0 | 0 | 2 | R04 | C02 |
| 8 | 0 | 3 | 7 | ? | R05 | C22 |
| 10 | 0 | 0 | 1 | 2 | R04 | C02 |
| 10 | 0 | 0 | 2 | 0 | R04 | C07 |
| 10 | 0 | 1 | 3 | 0 | R04 | C07 |
| 10 | 0 | 1 | 4 | 0 | R04 | C07 |
| 12 | 0 | 1 | 3 | 2 | R06 | C08 |
| 12 | 0 | 3 | 6 | 5 | R02 | C04 |
| 12 | 0 | 4 | 9 | 6 | R06 | C08 |
| 13 | 0 | 1 | 2 | 9 | R02 | C04 |
| 13 | 0 | 1 | 3 | 1 | R02 | C06 |
| 13 | 0 | 2 | 4 | ? | R07 | C15 |
| 15 | 0 | 1 | 5 | 0 | R02 | C09 |
| 15 | 0 | 1 | 6 | 0 | R04 | C07 |
| 15 | 0 | 1 | 7 | 0 | R04 | C07 |
| 15 | 0 | 3 | 13 | 6 | R02 | C06 |
| 15 | 1 | 1 | 18 | 9 | R02 | C06 |
| 15 | 1 | 4 | 25 | 0 | R02 | C13 |
| 15 | 2 | 0 | 26 | 0 | R04 | C07 |
| 15 | 2 | 0 | 28 | 6 | R02 | C16 |
| 15 | 2 | 0 | 29 | 0 | R04 | C07 |
| 15 | 2 | 1 | 31 | 5 | R02 | C23 |
| 15 | 2 | 4 | 36 | 13 | R02 | C06 |
| 15 | 2 | 4 | 37 | 0 | R04 | C07 |
| 16 | 0 | 1 | 2 | 4 | R02 | C04 |
| 16 | 0 | 2 | 4 | 6 | R02 | C04 |
| 16 | 0 | 2 | 5 | 2 | R02 | C04 |
| 16 | 0 | 3 | 6 | 6 | R02 | C04 |
| 16 | 1 | 1 | 12 | 1 | R02 | C24 |
| 16 | 1 | 3 | 15 | 4 | R02 | C04 |
| 17 | 0 | 2 | 7 | 3 | R06 | C17 |
| 17 | 0 | 3 | 13 | 5 | R06 | C08 |
| 17 | 0 | 3 | 14 | 2 | R06 | C10 |
| 20 | 0 | 0 | 1 | 8 | R06 | C10 |
| 20 | 0 | 1 | 3 | 5 | R06 | C10 |
| 20 | 0 | 1 | 5 | 8 | R06 | C10 |
| 20 | 0 | 2 | 7 | 5 | R02 | C04 |
| 21 | 0 | 0 | 2 | ? | R03 | C03 |
| 21 | 0 | 1 | 5 | ? | R03 | C03 |
| 21 | 0 | 2 | 8 | ? | R03 | C03 |
| 21 | 0 | 3 | 9 | ? | R03 | C03 |
| 24 | 1 | 1 | 11 | 20 | R02 | C06 |
| 26 | 0 | 0 | 0 | 0 | R02 | C14 |
| 31 | 1 | 5 | 26 | 11 | R08 | C18 |
| 35 | 1 | 0 | 9 | 10 | R08 | C18 |
| 35 | 1 | 3 | 15 | ? | R09 | C19 |
| 35 | 1 | 3 | 16 | ? | R09 | C19 |
| 35 | 1 | 4 | 17 | 2 | R04 | C02 |
| 35 | 1 | 4 | 18 | 1 | R02 | C04 |
| 35 | 2 | 0 | 19 | 1 | R02 | C06 |
| 35 | 2 | 0 | 20 | 1 | R02 | C05 |
| 35 | 3 | 1 | 32 | 5 | R04 | C02 |
| 35 | 3 | 1 | 33 | 5 | R04 | C02 |
| 35 | 3 | 1 | 34 | 4 | R04 | C02 |
| 35 | 4 | 2 | 46 | 2 | R02 | C04 |
| 35 | 5 | 0 | 52 | 0 | R02 | C05 |
| 35 | 5 | 4 | 62 | 0 | R02 | C05 |
| 35 | 6 | 1 | 67 | 0 | R04 | C02 |
| 35 | 6 | 1 | 68 | 0 | R04 | C02 |
| 35 | 6 | 2 | 70 | 0 | R04 | C02 |
| 35 | 6 | 2 | 71 | 0 | R04 | C02 |
| 35 | 8 | 1 | 90 | 4 | R10 | C25 |
| 35 | 8 | 3 | 95 | 0 | R04 | C02 |
| 35 | 8 | 3 | 96 | 0 | R04 | C02 |
| 35 | 8 | 3 | 97 | 0 | R04 | C02 |
| 35 | 10 | 1 | 115 | 1 | R06 | C08 |
| 35 | 10 | 4 | 121 | 4 | R04 | C02 |
| 35 | 11 | 2 | 129 | 0 | R04 | C02 |
| 35 | 11 | 3 | 130 | 1 | R04 | C02 |
| 35 | 11 | 3 | 131 | 0 | R04 | C02 |
| 35 | 11 | 3 | 132 | 0 | R04 | C07 |
| 35 | 12 | 0 | 135 | 4 | R04 | C02 |
| 35 | 14 | 3 | 186 | 1 | R04 | C02 |
| 35 | 14 | 4 | 191 | 1 | R04 | C02 |
| 35 | 16 | 3 | 231 | 0 | R02 | C13 |
| 35 | 16 | 3 | 233 | 0 | R02 | C14 |
| 35 | 17 | 0 | 237 | 1 | R02 | C06 |
| 35 | 17 | 0 | 238 | ? | R11 | C20 |
| 35 | 17 | 5 | 258 | 1 | R02 | C06 |
| 35 | 18 | 0 | 262 | 1 | R02 | C06 |
| 35 | 18 | 4 | 275 | ? | R07 | C11 |
| 35 | 18 | 4 | 276 | ? | R03 | C12 |
| 35 | 18 | 4 | 277 | ? | R03 | C12 |
| 35 | 18 | 4 | 278 | ? | R11 | C20 |
| 35 | 19 | 2 | 294 | 1 | R04 | C02 |
| 35 | 20 | 2 | 310 | 0 | R02 | C04 |
| 35 | 20 | 3 | 314 | 1 | R02 | C05 |
| 35 | 20 | 3 | 315 | ? | R03 | C12 |
| 35 | 20 | 3 | 316 | ? | R03 | C12 |
| 35 | 21 | 5 | 346 | ? | R07 | C11 |
| 35 | 21 | 5 | 347 | 0 | R02 | C05 |
| 35 | 22 | 0 | 348 | ? | R07 | C11 |
| 35 | 22 | 1 | 355 | 4 | R04 | C02 |
| 35 | 24 | 0 | 399 | 4 | R02 | C09 |
| 35 | 24 | 3 | 405 | 5 | R04 | C02 |
| 35 | 24 | 4 | 409 | 5 | R04 | C02 |
| 35 | 25 | 3 | 428 | 3 | R02 | C04 |
| 35 | 25 | 4 | 431 | 7 | R02 | C04 |
| 35 | 26 | 2 | 448 | 1 | R02 | C06 |
| 35 | 26 | 4 | 454 | 0 | R02 | C21 |
| 35 | 26 | 5 | 460 | 3 | R02 | C21 |
| 35 | 28 | 0 | 483 | 3 | R02 | C05 |
| 35 | 28 | 1 | 484 | 1 | R02 | C05 |
| 35 | 28 | 1 | 486 | 1 | R04 | C02 |
| 35 | 28 | 2 | 489 | 1 | R04 | C02 |
| 35 | 28 | 3 | 495 | 1 | R02 | C05 |
| 35 | 28 | 4 | 498 | 5 | R02 | C04 |
| 35 | 29 | 1 | 505 | 1 | R06 | C17 |
| 35 | 29 | 2 | 508 | 2 | R04 | C02 |
| 35 | 29 | 2 | 510 | 1 | R04 | C02 |
| 35 | 29 | 3 | 514 | 1 | R02 | C05 |
| 35 | 29 | 3 | 515 | 3 | R04 | C02 |
| 35 | 29 | 4 | 516 | 1 | R04 | C02 |
| 35 | 29 | 4 | 517 | 5 | R04 | C02 |
| 35 | 30 | 0 | 520 | 0 | R02 | C26 |
| 35 | 30 | 0 | 521 | 2 | R04 | C02 |
| 35 | 30 | 0 | 522 | 0 | R04 | C02 |
| 35 | 30 | 0 | 523 | 0 | R04 | C02 |
| 35 | 30 | 1 | 527 | 1 | R04 | C02 |
| 35 | 30 | 2 | 529 | 1 | R04 | C02 |
| 35 | 30 | 2 | 531 | 1 | R04 | C02 |
| 35 | 31 | 3 | 555 | 1 | R02 | C05 |
| 35 | 31 | 4 | 559 | 1 | R04 | C02 |
| 35 | 32 | 0 | 560 | 1 | R04 | C02 |
| 35 | 32 | 2 | 571 | ? | R07 | C11 |
| 35 | 32 | 2 | 572 | 0 | R02 | C05 |
| 35 | 32 | 2 | 573 | 0 | R02 | C05 |
| 35 | 33 | 0 | 587 | 4 | R04 | C02 |
| 36 | 0 | 1 | 4 | 0 | R02 | C05 |
| 36 | 1 | 4 | 28 | 2 | R12 | C27 |
| 37 | 0 | 1 | 3 | 1 | R02 | C16 |
| 39 | 0 | 0 | 0 | 0 | R02 | C01 |
| 39 | 0 | 3 | 6 | ? | R03 | C28 |
| 39 | 0 | 3 | 7 | 0 | R04 | C02 |
| 39 | 0 | 3 | 9 | 0 | R04 | C02 |
| 39 | 1 | 0 | 10 | 0 | R02 | C01 |
| 39 | 1 | 0 | 11 | 0 | R02 | C01 |
| 39 | 1 | 0 | 12 | 0 | R02 | C01 |
| 39 | 1 | 0 | 13 | 0 | R02 | C01 |
| 39 | 1 | 1 | 14 | 5 | R02 | C29 |
| 39 | 1 | 3 | 23 | ? | R07 | C15 |
| 39 | 2 | 0 | 30 | ? | R03 | C03 |
| 39 | 2 | 0 | 31 | 0 | R04 | C02 |
| 39 | 2 | 0 | 33 | 0 | R04 | C02 |
| 40 | 0 | 2 | 5 | 5 | R02 | C04 |
| 40 | 1 | 0 | 10 | 10 | R02 | C09 |
| 40 | 1 | 0 | 11 | 0 | R02 | C09 |
| 40 | 1 | 1 | 12 | 4 | R02 | C06 |
| 42 | 0 | 4 | 23 | 2 | R02 | C14 |
| 42 | 1 | 0 | 25 | 0 | R02 | C13 |
| 42 | 1 | 2 | 42 | ? | R03 | C03 |
| 42 | 1 | 2 | 43 | ? | R03 | C03 |
