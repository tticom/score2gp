# REFUSE-20: tied TAB chords and refusal census

REFUSE-20 remains incomplete: the reader delivers a two-bar settled subset; selection of the largest settled class and a positive cross-source holdout remain unproven.

Baseline: `afe4f352634f03fbaa06e7019afcd5abdb68319d`. All 43 approved PDFs exist and match their manifest hashes.
Both fresh whole-set runs use the checkout virtualenv and normal strict CLI:
`python -m score2gp.cli convert --pdf <approved-pdf> --pdf-only-tab --out <ignored-output> --work-dir <ignored-build> --json-report <ignored-report>`.
No sidecar or reference supplies conversion inputs. Exact commands, exit statuses and hashes remain in ignored local receipts.
The after run is a working-tree result; the launcher owns commit, publication and exact-head reconciliation.

## Before and after

| Channel | Before | After |
|---|---:|---:|
| Packages | 38 | 38 |
| Written bars | 1423 | 1425 |
| Refused inventory bars | 237 | 235 |
| Source-level unfinished gaps | 4 | 4 |
| Newly written bars | 0 | 2 |
| Changed inner GPIF packages | 0 | 1 |

Source index 35 is the only changed inner GPIF: source bars 68 and 71 become written. The other 37 existing packages retain byte-identical `Content/score.gpif`.
Every previously written IR bar in all 38 packages is unchanged, including every previously written bar inside source 35. Every source exit status is unchanged.

## Refused bars by code

| Code ID | Code | Before | After |
|---|---|---:|---:|
| R01 | `pdf_only_tab_no_notation_bars` | 9 | 9 |
| R02 | `note_duration_event_unread` | 130 | 130 |
| R03 | `bar_without_notation_event` | 20 | 20 |
| R04 | `notation_note_without_tab_digit` | 53 | 51 |
| R05 | `duration_off_tick_grid` | 1 | 1 |
| R06 | `notehead_digit_count_mismatch` | 10 | 10 |
| R07 | `bar_total_mismatch` | 6 | 6 |
| R08 | `tie_head_ownership_unconfirmed` | 2 | 2 |
| R09 | `tab_system_digit_unassigned_to_bar` | 2 | 2 |
| R10 | `notation_tab_column_ambiguous` | 1 | 1 |
| R11 | `tab_digit_without_notation_event` | 2 | 2 |
| R12 | `tab_chord_arrow_unread` | 1 | 1 |

## First located causes ranked by baseline bar count

These are first diagnostic causes, not a semantic partition proving that each class has one repair. All outstanding bars remain unfinished. No refusal is classified as correct.

| Cause ID | Cause code | Before | After | Classification |
|---|---|---:|---:|---|
| C01 | `tab_column_without_rhythm_mark` | 82 | 82 | reader_gap |
| C02 | `no_tab_column_at_notation_event` | 44 | 42 | reader_gap |
| C03 | `bar_without_notation_or_tab_item` | 15 | 15 | unknown |
| C04 | `unsupported_overlapping_form` | 15 | 15 | reader_gap |
| C05 | `rest_glyph_unidentified` | 13 | 13 | reader_gap |
| C06 | `symbol_unclassified` | 11 | 11 | reader_gap |
| C07 | `tie_stop_without_written_predecessor` | 9 | 9 | reader_gap |
| C08 | `printed_technique_owner_unread` | 4 | 4 | reader_gap |
| C09 | `concurrent_events` | 4 | 4 | unknown |
| C10 | `notehead_digit_count_mismatch` | 4 | 4 | reader_gap |
| C11 | `notation_total_below_meter` | 4 | 4 | unknown |
| C12 | `tab_digits_without_notation_event` | 4 | 4 | reader_gap |
| C13 | `mixed_notehead_kinds` | 3 | 3 | unknown |
| C14 | `filled_notehead_without_stem` | 3 | 3 | reader_gap |
| C15 | `notation_total_above_meter` | 2 | 2 | unknown |
| C16 | `tuplet_number_unassociated` | 2 | 2 | reader_gap |
| C17 | `tab_digit_run_or_parenthesis_unread` | 2 | 1 | reader_gap |
| C18 | `tie_head_ownership_unconfirmed` | 2 | 2 | reader_gap |
| C19 | `tab_system_digit_unassigned_to_bar` | 2 | 2 | reader_gap |
| C20 | `tab_digit_without_notation_event` | 2 | 2 | reader_gap |
| C21 | `parenthesized_head_unrepresented` | 2 | 2 | reader_gap |
| C22 | `duration_not_whole_ticks` | 1 | 1 | representation_gap |
| C23 | `overlapping_tuplets` | 1 | 1 | reader_gap |
| C24 | `grace_note_beat_too_far` | 1 | 1 | reader_gap |
| C25 | `notation_tab_column_ambiguous` | 1 | 1 | reader_gap |
| C26 | `rest_glyph_beside_note` | 1 | 1 | unknown |
| C27 | `straight_chord_arrow_unread` | 1 | 1 | reader_gap |
| C28 | `tab_digits_printed_but_not_grouped` | 1 | 1 | reader_gap |
| C29 | `unclassified_mark_below_strings` | 1 | 1 | reader_gap |
| C30 | `printed_vibrato_chord_owner_unread` | 0 | 1 | reader_gap |

## Source-level unfinished gaps

The maintainer exclusion applies to source indices 22, 25, 27 and 33 only. These have no bar inventory and stay outside the bar-count ranking. Their normal CLI diagnostics supply the source-level causes.

| Source index | Code | Located source cause | Classification |
|---:|---|---|---|
| 22 | `pdf_only_tab_grouping_unsafe` | `scanned_raster_source_without_vector_tab` | reader_gap |
| 25 | `pdf_only_tab_grouping_unsafe` | `scanned_raster_source_without_vector_tab` | reader_gap |
| 27 | `pdf_only_tab_grouping_unsafe` | `text_without_tab_rows` | reader_gap |
| 33 | `pdf_only_tab_grouping_unsafe` | `ascii_tab_rows_without_barlines_or_rhythm` | reader_gap |

## REFUSE-19 protection

REFUSE-19 addressed bare palm marks and positively read bar-key glyphs. Its 1 palm-mark bar and 2 key-glyph bars remain written; these addressed causes are absent from the refusal ranking.

## New-bar printed-page evidence

The two complete bracketed TAB chords are literal continuations of the preceding printed chord: every string/fret position agrees, the notation events share a drawn tie, and the wave lies above the complete TAB chord.
The wave is retained on both tied events. Another tentative candidate, source 35 bar 523, remains refused: its wave owner is not resolved by this rule.
Both new bars were manually checked against their printed page for ordered positions, rhythm, rests, ties, chord-wide vibrato and palm marks. The ordered positions agree with a local page transcription. Source 35 has no reference: **not independently verified**.

The route retains its existing CLI tempo setting. Reading printed tempo changes is not delivered or claimed by this reader; absolute playback tempo is outside the verified channels above.

All reference-less sources remain **not independently verified**: source indices 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 13, 14, 15, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 33, 35, 36, 39, 40, 41, 42, 43.

| Source | Page | System | Bar | Events | Notes | Tied destination heads | Vibrato-bearing heads | Timing total | Oracle |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 35 | 6 | 1 | 68 | 16 | 27 | 2 | 4 | 3840 | printed page; not independently verified |
| 35 | 6 | 2 | 71 | 13 | 29 | 3 | 6 | 3840 | printed page; not independently verified |

The retained requirement test had an erroneous last-event oracle in bar 68: its tied chord occurs at event 12, followed by three events. The corrected test checks that exact printed location and retains the full event/rhythm requirements; it strengthens wave ownership to every head and checks palm-event indices.

## Mutants and validation boundary

`DROP_TIED_TAB_PARENTHESES` returns no positively read continuation words: the real-page test fails with 7 written bars against 9 required.
`DROP_TIED_CHORD_VIBRATO` omits applying the witnessed wave: the same real-page test fails its per-head vibrato assertion.
The REFUSE-19 guard mutants still fail their output checks when a permissive parenthesis guard writes these bars without the new positive chord/wave proof. No test is skipped or deleted. Synthetic tests carry zero recognition, grouping, geometry, timing or fidelity acceptance weight; none were added.
The real page cut is an unchanged extraction of the approved PDF. The full-source normal CLI independently retains the complete 594-bar inventory.

## Remaining acceptance gap

The delivered subset does not prove selection of the next-largest settled class. No positive cross-source held-out case is claimed. The whole-set after run applies the finished reader once to every source, but non-regression on sources without newly written examples is insufficient holdout acceptance.
The largest diagnostic cause remains C01. All remaining causes in the table and the four source-level reader gaps are unfinished. The first located inventory refusal is source 3, page 0, system 0, bar 0, event 0, R01/C01.
Full validation results and any Windows baseline failure IDs belong in the launcher report and handback packet; a running or interrupted suite is never a pass.

## Revision round 6: second-ranked class and holdout availability (counts only)

Re-measured on the normal CLI for the source holding most C02 bars (source 35, 594-bar inventory): 36 bars refuse as `no_tab_column_at_notation_event`; in 23 of them exactly one notation event lacks a TAB column while the TAB digit count equals the TAB column count, and 19 of the 36 carry an unread bracketed-head symbol (`parenthesized_head_unrepresented`) at the very event that has no column. A bracketed head with no printed digit is a head whose string/fret the page does not print; reading it would invent a value (the REFUSE-13 finding, unchanged). The other 13 have 2 to 24 extra notation events per bar (the TAB column count is far below the notation count), which is a TAB-extraction disagreement, not a settled page reading.
Result: C02 is not a class the page evidence settles; C01 (82 bars) is unread by maintainer decision except where a rhythm mark is printed, and the only C01 bars not excluded as duration-basis-unproven (source 39) depend on grace/technique ownership. No further class was read.
Holdout: the tied bracketed-chord reader's trigger (`tab_digit_run_or_parenthesis_unread`, `parenthesized_head_unrepresented`) occurs only in source 35 in the whole private set (1 and 2 refused bars remain there, all in that source). No second source prints the form, so a positive separate-source holdout does not exist. Acceptance 2 remains **unmet** and is reported as such, not claimed.

## Located inventory, before and after

Source indices follow the sorted PDF inventory. All indices are zero-based. A missing event is shown as `?`: no event is invented in a bar without an event inventory.
Each baseline-refused bar appears once. `written` identifies the two new bars; every remaining row is unfinished.

| Source | Page | System | Bar | Event | Before code | Before cause | After code | After cause |
|---:|---:|---:|---:|---:|---|---|---|---|
| 3 | 0 | 0 | 0 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 0 | 1 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 1 | 2 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 1 | 3 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 2 | 4 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 3 | 5 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 3 | 6 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 4 | 7 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 4 | 8 | 0 | R01 | C01 | R01 | C01 |
| 4 | 0 | 0 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 0 | 1 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 0 | 4 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 0 | 5 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 8 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 9 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 12 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 13 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 14 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 16 | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 2 | 17 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 2 | 18 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 2 | 19 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 2 | 20 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 2 | 21 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 22 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 23 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 24 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 25 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 26 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 27 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 28 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 29 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 30 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 31 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 32 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 33 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 34 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 35 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 36 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 37 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 38 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 39 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 40 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 41 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 42 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 43 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 44 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 45 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 46 | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 6 | 47 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 48 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 49 | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 6 | 50 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 51 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 52 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 7 | 53 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 7 | 54 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 7 | 55 | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 7 | 56 | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 7 | 57 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 7 | 58 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 59 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 60 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 61 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 62 | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 8 | 63 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 64 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 65 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 66 | ? | R03 | C03 | R03 | C03 |
| 4 | 1 | 0 | 67 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 68 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 69 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 70 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 71 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 72 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 73 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 74 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 75 | ? | R03 | C03 | R03 | C03 |
| 4 | 1 | 1 | 76 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 1 | 77 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 78 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 79 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 80 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 81 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 82 | 0 | R02 | C01 | R02 | C01 |
| 7 | 0 | 0 | 0 | 2 | R04 | C02 | R04 | C02 |
| 8 | 0 | 3 | 7 | ? | R05 | C22 | R05 | C22 |
| 10 | 0 | 0 | 1 | 2 | R04 | C02 | R04 | C02 |
| 10 | 0 | 0 | 2 | 0 | R04 | C07 | R04 | C07 |
| 10 | 0 | 1 | 3 | 0 | R04 | C07 | R04 | C07 |
| 10 | 0 | 1 | 4 | 0 | R04 | C07 | R04 | C07 |
| 12 | 0 | 1 | 3 | 2 | R06 | C08 | R06 | C08 |
| 12 | 0 | 3 | 6 | 5 | R02 | C04 | R02 | C04 |
| 12 | 0 | 4 | 9 | 6 | R06 | C08 | R06 | C08 |
| 13 | 0 | 1 | 2 | 9 | R02 | C04 | R02 | C04 |
| 13 | 0 | 1 | 3 | 1 | R02 | C06 | R02 | C06 |
| 13 | 0 | 2 | 4 | ? | R07 | C15 | R07 | C15 |
| 15 | 0 | 1 | 5 | 0 | R02 | C09 | R02 | C09 |
| 15 | 0 | 1 | 6 | 0 | R04 | C07 | R04 | C07 |
| 15 | 0 | 1 | 7 | 0 | R04 | C07 | R04 | C07 |
| 15 | 0 | 3 | 13 | 6 | R02 | C06 | R02 | C06 |
| 15 | 1 | 1 | 18 | 9 | R02 | C06 | R02 | C06 |
| 15 | 1 | 4 | 25 | 0 | R02 | C13 | R02 | C13 |
| 15 | 2 | 0 | 26 | 0 | R04 | C07 | R04 | C07 |
| 15 | 2 | 0 | 28 | 6 | R02 | C16 | R02 | C16 |
| 15 | 2 | 0 | 29 | 0 | R04 | C07 | R04 | C07 |
| 15 | 2 | 1 | 31 | 5 | R02 | C23 | R02 | C23 |
| 15 | 2 | 4 | 36 | 13 | R02 | C06 | R02 | C06 |
| 15 | 2 | 4 | 37 | 0 | R04 | C07 | R04 | C07 |
| 16 | 0 | 1 | 2 | 4 | R02 | C04 | R02 | C04 |
| 16 | 0 | 2 | 4 | 6 | R02 | C04 | R02 | C04 |
| 16 | 0 | 2 | 5 | 2 | R02 | C04 | R02 | C04 |
| 16 | 0 | 3 | 6 | 6 | R02 | C04 | R02 | C04 |
| 16 | 1 | 1 | 12 | 1 | R02 | C24 | R02 | C24 |
| 16 | 1 | 3 | 15 | 4 | R02 | C04 | R02 | C04 |
| 17 | 0 | 2 | 7 | 3 | R06 | C17 | R06 | C17 |
| 17 | 0 | 3 | 13 | 5 | R06 | C08 | R06 | C08 |
| 17 | 0 | 3 | 14 | 2 | R06 | C10 | R06 | C10 |
| 20 | 0 | 0 | 1 | 8 | R06 | C10 | R06 | C10 |
| 20 | 0 | 1 | 3 | 5 | R06 | C10 | R06 | C10 |
| 20 | 0 | 1 | 5 | 8 | R06 | C10 | R06 | C10 |
| 20 | 0 | 2 | 7 | 5 | R02 | C04 | R02 | C04 |
| 21 | 0 | 0 | 2 | ? | R03 | C03 | R03 | C03 |
| 21 | 0 | 1 | 5 | ? | R03 | C03 | R03 | C03 |
| 21 | 0 | 2 | 8 | ? | R03 | C03 | R03 | C03 |
| 21 | 0 | 3 | 9 | ? | R03 | C03 | R03 | C03 |
| 24 | 1 | 1 | 11 | 20 | R02 | C06 | R02 | C06 |
| 26 | 0 | 0 | 0 | 0 | R02 | C14 | R02 | C14 |
| 31 | 1 | 5 | 26 | 11 | R08 | C18 | R08 | C18 |
| 35 | 1 | 0 | 9 | 10 | R08 | C18 | R08 | C18 |
| 35 | 1 | 3 | 15 | ? | R09 | C19 | R09 | C19 |
| 35 | 1 | 3 | 16 | ? | R09 | C19 | R09 | C19 |
| 35 | 1 | 4 | 17 | 2 | R04 | C02 | R04 | C02 |
| 35 | 1 | 4 | 18 | 1 | R02 | C04 | R02 | C04 |
| 35 | 2 | 0 | 19 | 1 | R02 | C06 | R02 | C06 |
| 35 | 2 | 0 | 20 | 1 | R02 | C05 | R02 | C05 |
| 35 | 3 | 1 | 32 | 5 | R04 | C02 | R04 | C02 |
| 35 | 3 | 1 | 33 | 5 | R04 | C02 | R04 | C02 |
| 35 | 3 | 1 | 34 | 4 | R04 | C02 | R04 | C02 |
| 35 | 4 | 2 | 46 | 2 | R02 | C04 | R02 | C04 |
| 35 | 5 | 0 | 52 | 0 | R02 | C05 | R02 | C05 |
| 35 | 5 | 4 | 62 | 0 | R02 | C05 | R02 | C05 |
| 35 | 6 | 1 | 67 | 0 | R04 | C02 | R04 | C02 |
| 35 | 6 | 1 | 68 | 0 | R04 | C02 | written | written |
| 35 | 6 | 2 | 70 | 0 | R04 | C02 | R04 | C02 |
| 35 | 6 | 2 | 71 | 0 | R04 | C02 | written | written |
| 35 | 8 | 1 | 90 | 4 | R10 | C25 | R10 | C25 |
| 35 | 8 | 3 | 95 | 0 | R04 | C02 | R04 | C02 |
| 35 | 8 | 3 | 96 | 0 | R04 | C02 | R04 | C02 |
| 35 | 8 | 3 | 97 | 0 | R04 | C02 | R04 | C02 |
| 35 | 10 | 1 | 115 | 1 | R06 | C08 | R06 | C08 |
| 35 | 10 | 4 | 121 | 4 | R04 | C02 | R04 | C02 |
| 35 | 11 | 2 | 129 | 0 | R04 | C02 | R04 | C02 |
| 35 | 11 | 3 | 130 | 1 | R04 | C02 | R04 | C02 |
| 35 | 11 | 3 | 131 | 0 | R04 | C02 | R04 | C02 |
| 35 | 11 | 3 | 132 | 0 | R04 | C07 | R04 | C07 |
| 35 | 12 | 0 | 135 | 4 | R04 | C02 | R04 | C02 |
| 35 | 14 | 3 | 186 | 1 | R04 | C02 | R04 | C02 |
| 35 | 14 | 4 | 191 | 1 | R04 | C02 | R04 | C02 |
| 35 | 16 | 3 | 231 | 0 | R02 | C13 | R02 | C13 |
| 35 | 16 | 3 | 233 | 0 | R02 | C14 | R02 | C14 |
| 35 | 17 | 0 | 237 | 1 | R02 | C06 | R02 | C06 |
| 35 | 17 | 0 | 238 | ? | R11 | C20 | R11 | C20 |
| 35 | 17 | 5 | 258 | 1 | R02 | C06 | R02 | C06 |
| 35 | 18 | 0 | 262 | 1 | R02 | C06 | R02 | C06 |
| 35 | 18 | 4 | 275 | ? | R07 | C11 | R07 | C11 |
| 35 | 18 | 4 | 276 | ? | R03 | C12 | R03 | C12 |
| 35 | 18 | 4 | 277 | ? | R03 | C12 | R03 | C12 |
| 35 | 18 | 4 | 278 | ? | R11 | C20 | R11 | C20 |
| 35 | 19 | 2 | 294 | 1 | R04 | C02 | R04 | C02 |
| 35 | 20 | 2 | 310 | 0 | R02 | C04 | R02 | C04 |
| 35 | 20 | 3 | 314 | 1 | R02 | C05 | R02 | C05 |
| 35 | 20 | 3 | 315 | ? | R03 | C12 | R03 | C12 |
| 35 | 20 | 3 | 316 | ? | R03 | C12 | R03 | C12 |
| 35 | 21 | 5 | 346 | ? | R07 | C11 | R07 | C11 |
| 35 | 21 | 5 | 347 | 0 | R02 | C05 | R02 | C05 |
| 35 | 22 | 0 | 348 | ? | R07 | C11 | R07 | C11 |
| 35 | 22 | 1 | 355 | 4 | R04 | C02 | R04 | C02 |
| 35 | 24 | 0 | 399 | 4 | R02 | C09 | R02 | C09 |
| 35 | 24 | 3 | 405 | 5 | R04 | C02 | R04 | C02 |
| 35 | 24 | 4 | 409 | 5 | R04 | C02 | R04 | C02 |
| 35 | 25 | 3 | 428 | 3 | R02 | C04 | R02 | C04 |
| 35 | 25 | 4 | 431 | 7 | R02 | C04 | R02 | C04 |
| 35 | 26 | 2 | 448 | 1 | R02 | C06 | R02 | C06 |
| 35 | 26 | 4 | 454 | 0 | R02 | C21 | R02 | C21 |
| 35 | 26 | 5 | 460 | 3 | R02 | C21 | R02 | C21 |
| 35 | 28 | 0 | 483 | 3 | R02 | C05 | R02 | C05 |
| 35 | 28 | 1 | 484 | 1 | R02 | C05 | R02 | C05 |
| 35 | 28 | 1 | 486 | 1 | R04 | C02 | R04 | C02 |
| 35 | 28 | 2 | 489 | 1 | R04 | C02 | R04 | C02 |
| 35 | 28 | 3 | 495 | 1 | R02 | C05 | R02 | C05 |
| 35 | 28 | 4 | 498 | 5 | R02 | C04 | R02 | C04 |
| 35 | 29 | 1 | 505 | 1 | R06 | C17 | R06 | C30 |
| 35 | 29 | 2 | 508 | 2 | R04 | C02 | R04 | C02 |
| 35 | 29 | 2 | 510 | 1 | R04 | C02 | R04 | C02 |
| 35 | 29 | 3 | 514 | 1 | R02 | C05 | R02 | C05 |
| 35 | 29 | 3 | 515 | 3 | R04 | C02 | R04 | C02 |
| 35 | 29 | 4 | 516 | 1 | R04 | C02 | R04 | C02 |
| 35 | 29 | 4 | 517 | 5 | R04 | C02 | R04 | C02 |
| 35 | 30 | 0 | 520 | 0 | R02 | C26 | R02 | C26 |
| 35 | 30 | 0 | 521 | 2 | R04 | C02 | R04 | C02 |
| 35 | 30 | 0 | 522 | 0 | R04 | C02 | R04 | C02 |
| 35 | 30 | 0 | 523 | 0 | R04 | C02 | R04 | C02 |
| 35 | 30 | 1 | 527 | 1 | R04 | C02 | R04 | C02 |
| 35 | 30 | 2 | 529 | 1 | R04 | C02 | R04 | C02 |
| 35 | 30 | 2 | 531 | 1 | R04 | C02 | R04 | C02 |
| 35 | 31 | 3 | 555 | 1 | R02 | C05 | R02 | C05 |
| 35 | 31 | 4 | 559 | 1 | R04 | C02 | R04 | C02 |
| 35 | 32 | 0 | 560 | 1 | R04 | C02 | R04 | C02 |
| 35 | 32 | 2 | 571 | ? | R07 | C11 | R07 | C11 |
| 35 | 32 | 2 | 572 | 0 | R02 | C05 | R02 | C05 |
| 35 | 32 | 2 | 573 | 0 | R02 | C05 | R02 | C05 |
| 35 | 33 | 0 | 587 | 4 | R04 | C02 | R04 | C02 |
| 36 | 0 | 1 | 4 | 0 | R02 | C05 | R02 | C05 |
| 36 | 1 | 4 | 28 | 2 | R12 | C27 | R12 | C27 |
| 37 | 0 | 1 | 3 | 1 | R02 | C16 | R02 | C16 |
| 39 | 0 | 0 | 0 | 0 | R02 | C01 | R02 | C01 |
| 39 | 0 | 3 | 6 | ? | R03 | C28 | R03 | C28 |
| 39 | 0 | 3 | 7 | 0 | R04 | C02 | R04 | C02 |
| 39 | 0 | 3 | 9 | 0 | R04 | C02 | R04 | C02 |
| 39 | 1 | 0 | 10 | 0 | R02 | C01 | R02 | C01 |
| 39 | 1 | 0 | 11 | 0 | R02 | C01 | R02 | C01 |
| 39 | 1 | 0 | 12 | 0 | R02 | C01 | R02 | C01 |
| 39 | 1 | 0 | 13 | 0 | R02 | C01 | R02 | C01 |
| 39 | 1 | 1 | 14 | 5 | R02 | C29 | R02 | C29 |
| 39 | 1 | 3 | 23 | ? | R07 | C15 | R07 | C15 |
| 39 | 2 | 0 | 30 | ? | R03 | C03 | R03 | C03 |
| 39 | 2 | 0 | 31 | 0 | R04 | C02 | R04 | C02 |
| 39 | 2 | 0 | 33 | 0 | R04 | C02 | R04 | C02 |
| 40 | 0 | 2 | 5 | 5 | R02 | C04 | R02 | C04 |
| 40 | 1 | 0 | 10 | 10 | R02 | C09 | R02 | C09 |
| 40 | 1 | 0 | 11 | 0 | R02 | C09 | R02 | C09 |
| 40 | 1 | 1 | 12 | 4 | R02 | C06 | R02 | C06 |
| 42 | 0 | 4 | 23 | 2 | R02 | C14 | R02 | C14 |
| 42 | 1 | 0 | 25 | 0 | R02 | C13 | R02 | C13 |
| 42 | 1 | 2 | 42 | ? | R03 | C03 | R03 | C03 |
| 42 | 1 | 2 | 43 | ? | R03 | C03 | R03 | C03 |
