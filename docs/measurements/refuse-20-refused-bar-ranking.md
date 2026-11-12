# REFUSE-20: chord-prefix ownership and refusal census

Revision baseline: `14e660ec39432179308ca861208af5749a0365d7`. All 43 approved PDFs exist and match their manifest hashes. Source indices are one-based, case-insensitive PDF-name order on the Windows runtime; page, system, bar and event indices are zero-based.

Both fresh whole-set runs use the checkout virtualenv and normal strict CLI:
`python -m score2gp.cli convert --pdf <approved-pdf> --pdf-only-tab --out <ignored-output> --work-dir <ignored-build> --json-report <ignored-report>`. No sidecar or reference supplies conversion inputs. The after result is a working-tree result; the launcher owns commit, publication and exact-head reconciliation.

## Before and after

| Channel | Before | After |
|---|---:|---:|
| Packages | 38 | 38 |
| Written bars | 1425 | 1428 |
| Refused inventory bars | 235 | 232 |
| Source-level unfinished gaps | 4 | 4 |
| Newly written bars in this revision | 0 | 3 |
| Changed inner GPIF packages | 0 | 3 |

Sources 12, 35 and 36 are the only changed inner GPIF packages: source bars 6, 20 and 4 respectively become written. The other 35 existing packages retain byte-identical `Content/score.gpif`. Every previously written IR bar in all 38 packages is unchanged, including the two tied-chord bars delivered earlier on this branch (source 35 bars 68 and 71). Every source exit status is unchanged.

## Refused bars by code

| Code ID | Code | Before | After |
|---|---|---:|---:|
| R01 | `pdf_only_tab_no_notation_bars` | 9 | 9 |
| R02 | `note_duration_event_unread` | 130 | 126 |
| R03 | `bar_without_notation_event` | 20 | 20 |
| R04 | `notation_note_without_tab_digit` | 51 | 51 |
| R05 | `duration_off_tick_grid` | 1 | 1 |
| R06 | `notehead_digit_count_mismatch` | 10 | 11 |
| R07 | `bar_total_mismatch` | 6 | 6 |
| R08 | `tie_head_ownership_unconfirmed` | 2 | 2 |
| R09 | `tab_system_digit_unassigned_to_bar` | 2 | 2 |
| R10 | `notation_tab_column_ambiguous` | 1 | 1 |
| R11 | `tab_digit_without_notation_event` | 2 | 2 |
| R12 | `tab_chord_arrow_unread` | 1 | 1 |

## First located causes ranked by baseline bar count

These are first diagnostic causes, not a claim that each bin is one repair. Every remaining bar is unfinished. No refusal is classified as correct.

| Cause ID | Cause code | Before | After | Classification |
|---|---|---:|---:|---|
| C01 | `tab_column_without_rhythm_mark` | 82 | 82 | reader_gap |
| C02 | `no_tab_column_at_notation_event` | 42 | 42 | reader_gap |
| C03 | `bar_without_notation_or_tab_item` | 15 | 15 | unknown |
| C04 | `unsupported_overlapping_form` | 15 | 14 | reader_gap |
| C05 | `rest_glyph_unidentified` | 13 | 11 | reader_gap |
| C06 | `symbol_unclassified` | 11 | 10 | reader_gap |
| C07 | `tie_stop_without_written_predecessor` | 9 | 9 | reader_gap |
| C08 | `printed_technique_owner_unread` | 4 | 4 | reader_gap |
| C09 | `concurrent_events` | 4 | 4 | unknown |
| C10 | `notehead_digit_count_mismatch` | 4 | 5 | reader_gap |
| C11 | `notation_total_below_meter` | 4 | 4 | unknown |
| C12 | `tab_digits_without_notation_event` | 4 | 4 | reader_gap |
| C13 | `mixed_notehead_kinds` | 3 | 3 | unknown |
| C14 | `filled_notehead_without_stem` | 3 | 3 | reader_gap |
| C15 | `notation_total_above_meter` | 2 | 2 | unknown |
| C16 | `tuplet_number_unassociated` | 2 | 2 | reader_gap |
| C18 | `tie_head_ownership_unconfirmed` | 2 | 2 | reader_gap |
| C19 | `tab_system_digit_unassigned_to_bar` | 2 | 2 | reader_gap |
| C20 | `tab_digit_without_notation_event` | 2 | 2 | reader_gap |
| C21 | `parenthesized_head_unrepresented` | 2 | 2 | reader_gap |
| C22 | `duration_not_whole_ticks` | 1 | 1 | representation_gap |
| C23 | `overlapping_tuplets` | 1 | 1 | reader_gap |
| C24 | `grace_note_beat_too_far` | 1 | 1 | reader_gap |
| C17 | `tab_digit_run_or_parenthesis_unread` | 1 | 1 | reader_gap |
| C25 | `notation_tab_column_ambiguous` | 1 | 1 | reader_gap |
| C30 | `printed_vibrato_chord_owner_unread` | 1 | 1 | reader_gap |
| C26 | `rest_glyph_beside_note` | 1 | 1 | unknown |
| C27 | `straight_chord_arrow_unread` | 1 | 1 | reader_gap |
| C28 | `tab_digits_printed_but_not_grouped` | 1 | 1 | reader_gap |
| C29 | `unclassified_mark_below_strings` | 1 | 1 | reader_gap |

## Source-level unfinished gaps

The maintainer exclusion applies only to sources 22, 25, 27 and 33. They have no bar inventory, remain outside the bar-count ranking, and remain unfinished reader gaps. Their normal CLI diagnostics supply located source-level causes.

| Source | Code | Located source cause | Classification |
|---:|---|---|---|
| 22 | `pdf_only_tab_grouping_unsafe` | `scanned_raster_source_without_vector_tab` | reader_gap |
| 25 | `pdf_only_tab_grouping_unsafe` | `scanned_raster_source_without_vector_tab` | reader_gap |
| 27 | `pdf_only_tab_grouping_unsafe` | `text_without_tab_rows` | reader_gap |
| 33 | `pdf_only_tab_grouping_unsafe` | `ascii_tab_rows_without_barlines_or_rhythm` | reader_gap |

## Class selection and separate-source checks

C01 remains 82 bars of unfinished TAB-rhythm work under the maintainer exclusion. C02 remains 42 unfinished bars: missing TAB columns, unrepresented heads and extraction disagreements do not establish string/fret values. C03 remains an unknown inventory/reading gap. The C04-C06 bins combine several glyph and ownership failures; they are not one interchangeable form.

The selected bounded class is unowned chord-prefix glyphs: positively identified staggered accidentals and an arrowed roll column. The accidental run must consist only of identified accidentals on the same chord, reach one head at its printed staff position, and cross no barline. The existing positive arrow/curl reader now also informs the duration reader. An unread glyph is never discarded merely because a bar total would then fit.

Source 36 was used for staggered-chord design. Its complete page check required retaining both the three internal legato slides and the departing slide across the next barline. The latter requires a printed slide label, one bound stroke/slur pair on one string, adjacent bars, and a timed partly tied chord. No slope threshold alone supplies a slide.

An additional frozen-reader page check used source 35 page 2 before adding its regression assertion: bar 20 becomes written; bar 19 remains refused with a located head-count mismatch. Previous rounds had inspected this source and tried rejected scratch readers, so it is not described as blind. The primary positive separate-source holdout is source 12, held out of design in this round: its first whole-source application writes bar 6. All 21 bars were checked against the two printed pages and the readable reference: 19 written bars and 2 located unfinished refusals. There was no subsequent tuning of the prefix recognizer to that source. Book/chapter cases 35 and 36 are treated as design/auxiliary coverage, not as independent-content holdout evidence; source 12 supplies that evidence.

The larger remaining bins and all their located bars remain unfinished reader, representation or unknown gaps. This measurement claims the bounded positive chord-prefix ownership class; it does not claim the complete C04-C06 bins or a solution for absent printed rhythm. No waiver of the positive separate-source requirement is used.

## Newly written bar evidence

No reference is fed into conversion. Source 12 is checked against its readable GP reference and printed page. Every sounding position and independently read rhythm/technique channel matches, including the roll and native muted strike. There is one raw GPIF fret-placeholder difference on that muted head: neither file represents it as a sounding pitch. Previously written bars retain their original exact reference checks. Sources 35 and 36 are checked against local printed-page transcriptions and are **not independently verified**.

| Source | Page | System | Bar | Events | Notes | Timing total | Oracle |
|---:|---:|---:|---:|---:|---:|---:|---|
| 12 | 0 | 3 | 6 | 10 | 17 | 3840 | reference and printed page |
| 35 | 2 | 0 | 20 | 5 | 21 | 3840 | printed page; not independently verified |
| 36 | 0 | 1 | 4 | 4 | 9 | 3840 | printed page; not independently verified |

The earlier source-35 tied TAB destinations at bars 68 and 71 remain written with their printed rhythm, tied heads, chord-wide vibrato and palm marks. Their real-source regressions remain active. All sources without a readable reference remain **not independently verified**. Printed tempo/tuning changes beyond the pre-existing CLI behavior are not delivered by this reader.

## REFUSE-19 protection

REFUSE-19 addressed bare palm marks and positively read bar-key glyphs. Its 1 palm-mark bar and 2 key-glyph bars remain written; these addressed causes are absent from the refusal ranking.

## Mutants and validation boundary

`DROP_STAGGERED_ACCIDENTALS`, `DROP_CHORD_SLUR_ENVELOPE`, `DROP_LABELED_CHORD_DEPARTURE`, `DROP_ACCIDENTAL_ATTACHMENT` and `DROP_SHARED_ARPEGGIO_READER` fail real-source output assertions. Dropping only the duration-reader extension preserves the exporter and restores the original real-source unresolved case: the original CFW-05 and OMIT-04 located-refusal/strike assertions remain unchanged and active. New default-route tests additionally require the fifth reference roll. CFW-03 now requires 28 reference chord labels instead of 26, and the four newly resolved annotations no longer count as unplaced.

The shared roll reader also positively owns 12 former overlap contours in source 28, with byte-identical GPIF and the same 2 reference rolls. The original 12-contour UNREAD-01 guards remain active under the duration-extension drop control. Source 12 now has 15 reference-owned HOPO origins rather than 14. The PERF-01 and UNREAD-01 source-36 byte digests are unchanged: their control verifies the actual new bar, confirms the saved IR reproduces actual GPIF exactly, then restores only new bar 4 to its former empty state before applying both original whole-file digests.

The original tied-TAB and vibrato rule-drop regressions remain active. No test is deleted or skipped by this change. Synthetic fixtures carry zero recognition, grouping, geometry, timing or fidelity acceptance weight; none were added. Full validation results and existing Windows quarantine IDs belong in the launcher report and packet. A running or interrupted suite is never a pass.

## Located inventory, before and after

Each revision-baseline refused bar appears once. `written` identifies a new complete bar; every remaining row is unfinished. `?` means no event inventory exists, not an invented event. The first remaining inventory refusal is source 3, page 0, system 0, bar 0, event 0, R01/C01.

| Source | Page | System | Bar | Before event | After event | Before code | Before cause | After code | After cause |
|---:|---:|---:|---:|---:|---:|---|---|---|---|
| 3 | 0 | 0 | 0 | 0 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 0 | 1 | 0 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 1 | 2 | 0 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 1 | 3 | 0 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 2 | 4 | 0 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 3 | 5 | 0 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 3 | 6 | 0 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 4 | 7 | 0 | 0 | R01 | C01 | R01 | C01 |
| 3 | 0 | 4 | 8 | 0 | 0 | R01 | C01 | R01 | C01 |
| 4 | 0 | 0 | 0 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 0 | 1 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 0 | 4 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 0 | 5 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 8 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 9 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 12 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 13 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 14 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 1 | 16 | ? | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 2 | 17 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 2 | 18 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 2 | 19 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 2 | 20 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 2 | 21 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 22 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 23 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 24 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 25 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 3 | 26 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 27 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 28 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 29 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 30 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 31 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 32 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 33 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 34 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 4 | 35 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 36 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 37 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 38 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 39 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 40 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 41 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 42 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 43 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 5 | 44 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 45 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 46 | ? | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 6 | 47 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 48 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 49 | ? | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 6 | 50 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 51 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 6 | 52 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 7 | 53 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 7 | 54 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 7 | 55 | ? | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 7 | 56 | ? | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 7 | 57 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 7 | 58 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 59 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 60 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 61 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 62 | ? | ? | R03 | C03 | R03 | C03 |
| 4 | 0 | 8 | 63 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 64 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 65 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 0 | 8 | 66 | ? | ? | R03 | C03 | R03 | C03 |
| 4 | 1 | 0 | 67 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 68 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 69 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 70 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 71 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 72 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 73 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 74 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 0 | 75 | ? | ? | R03 | C03 | R03 | C03 |
| 4 | 1 | 1 | 76 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 1 | 77 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 78 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 79 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 80 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 81 | 0 | 0 | R02 | C01 | R02 | C01 |
| 4 | 1 | 2 | 82 | 0 | 0 | R02 | C01 | R02 | C01 |
| 7 | 0 | 0 | 0 | 2 | 2 | R04 | C02 | R04 | C02 |
| 8 | 0 | 3 | 7 | ? | ? | R05 | C22 | R05 | C22 |
| 10 | 0 | 0 | 1 | 2 | 2 | R04 | C02 | R04 | C02 |
| 10 | 0 | 0 | 2 | 0 | 0 | R04 | C07 | R04 | C07 |
| 10 | 0 | 1 | 3 | 0 | 0 | R04 | C07 | R04 | C07 |
| 10 | 0 | 1 | 4 | 0 | 0 | R04 | C07 | R04 | C07 |
| 12 | 0 | 1 | 3 | 2 | 2 | R06 | C08 | R06 | C08 |
| 12 | 0 | 3 | 6 | 5 | written | R02 | C04 | written | written |
| 12 | 0 | 4 | 9 | 6 | 6 | R06 | C08 | R06 | C08 |
| 13 | 0 | 1 | 2 | 9 | 9 | R02 | C04 | R02 | C04 |
| 13 | 0 | 1 | 3 | 1 | 1 | R02 | C06 | R02 | C06 |
| 13 | 0 | 2 | 4 | ? | ? | R07 | C15 | R07 | C15 |
| 15 | 0 | 1 | 5 | 0 | 0 | R02 | C09 | R02 | C09 |
| 15 | 0 | 1 | 6 | 0 | 0 | R04 | C07 | R04 | C07 |
| 15 | 0 | 1 | 7 | 0 | 0 | R04 | C07 | R04 | C07 |
| 15 | 0 | 3 | 13 | 6 | 6 | R02 | C06 | R02 | C06 |
| 15 | 1 | 1 | 18 | 9 | 9 | R02 | C06 | R02 | C06 |
| 15 | 1 | 4 | 25 | 0 | 0 | R02 | C13 | R02 | C13 |
| 15 | 2 | 0 | 26 | 0 | 0 | R04 | C07 | R04 | C07 |
| 15 | 2 | 0 | 28 | 6 | 6 | R02 | C16 | R02 | C16 |
| 15 | 2 | 0 | 29 | 0 | 0 | R04 | C07 | R04 | C07 |
| 15 | 2 | 1 | 31 | 5 | 5 | R02 | C23 | R02 | C23 |
| 15 | 2 | 4 | 36 | 13 | 13 | R02 | C06 | R02 | C06 |
| 15 | 2 | 4 | 37 | 0 | 0 | R04 | C07 | R04 | C07 |
| 16 | 0 | 1 | 2 | 4 | 4 | R02 | C04 | R02 | C04 |
| 16 | 0 | 2 | 4 | 6 | 6 | R02 | C04 | R02 | C04 |
| 16 | 0 | 2 | 5 | 2 | 2 | R02 | C04 | R02 | C04 |
| 16 | 0 | 3 | 6 | 6 | 6 | R02 | C04 | R02 | C04 |
| 16 | 1 | 1 | 12 | 1 | 1 | R02 | C24 | R02 | C24 |
| 16 | 1 | 3 | 15 | 4 | 4 | R02 | C04 | R02 | C04 |
| 17 | 0 | 2 | 7 | 3 | 3 | R06 | C17 | R06 | C17 |
| 17 | 0 | 3 | 13 | 5 | 5 | R06 | C08 | R06 | C08 |
| 17 | 0 | 3 | 14 | 2 | 2 | R06 | C10 | R06 | C10 |
| 20 | 0 | 0 | 1 | 8 | 8 | R06 | C10 | R06 | C10 |
| 20 | 0 | 1 | 3 | 5 | 5 | R06 | C10 | R06 | C10 |
| 20 | 0 | 1 | 5 | 8 | 8 | R06 | C10 | R06 | C10 |
| 20 | 0 | 2 | 7 | 5 | 5 | R02 | C04 | R02 | C04 |
| 21 | 0 | 0 | 2 | ? | ? | R03 | C03 | R03 | C03 |
| 21 | 0 | 1 | 5 | ? | ? | R03 | C03 | R03 | C03 |
| 21 | 0 | 2 | 8 | ? | ? | R03 | C03 | R03 | C03 |
| 21 | 0 | 3 | 9 | ? | ? | R03 | C03 | R03 | C03 |
| 24 | 1 | 1 | 11 | 20 | 20 | R02 | C06 | R02 | C06 |
| 26 | 0 | 0 | 0 | 0 | 0 | R02 | C14 | R02 | C14 |
| 31 | 1 | 5 | 26 | 11 | 11 | R08 | C18 | R08 | C18 |
| 35 | 1 | 0 | 9 | 10 | 10 | R08 | C18 | R08 | C18 |
| 35 | 1 | 3 | 15 | ? | ? | R09 | C19 | R09 | C19 |
| 35 | 1 | 3 | 16 | ? | ? | R09 | C19 | R09 | C19 |
| 35 | 1 | 4 | 17 | 2 | 2 | R04 | C02 | R04 | C02 |
| 35 | 1 | 4 | 18 | 1 | 1 | R02 | C04 | R02 | C04 |
| 35 | 2 | 0 | 19 | 1 | 1 | R02 | C06 | R06 | C10 |
| 35 | 2 | 0 | 20 | 1 | written | R02 | C05 | written | written |
| 35 | 3 | 1 | 32 | 5 | 5 | R04 | C02 | R04 | C02 |
| 35 | 3 | 1 | 33 | 5 | 5 | R04 | C02 | R04 | C02 |
| 35 | 3 | 1 | 34 | 4 | 4 | R04 | C02 | R04 | C02 |
| 35 | 4 | 2 | 46 | 2 | 2 | R02 | C04 | R02 | C04 |
| 35 | 5 | 0 | 52 | 0 | 0 | R02 | C05 | R02 | C05 |
| 35 | 5 | 4 | 62 | 0 | 0 | R02 | C05 | R02 | C05 |
| 35 | 6 | 1 | 67 | 0 | 0 | R04 | C02 | R04 | C02 |
| 35 | 6 | 2 | 70 | 0 | 0 | R04 | C02 | R04 | C02 |
| 35 | 8 | 1 | 90 | 4 | 4 | R10 | C25 | R10 | C25 |
| 35 | 8 | 3 | 95 | 0 | 0 | R04 | C02 | R04 | C02 |
| 35 | 8 | 3 | 96 | 0 | 0 | R04 | C02 | R04 | C02 |
| 35 | 8 | 3 | 97 | 0 | 0 | R04 | C02 | R04 | C02 |
| 35 | 10 | 1 | 115 | 1 | 1 | R06 | C08 | R06 | C08 |
| 35 | 10 | 4 | 121 | 4 | 4 | R04 | C02 | R04 | C02 |
| 35 | 11 | 2 | 129 | 0 | 0 | R04 | C02 | R04 | C02 |
| 35 | 11 | 3 | 130 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 11 | 3 | 131 | 0 | 0 | R04 | C02 | R04 | C02 |
| 35 | 11 | 3 | 132 | 0 | 0 | R04 | C07 | R04 | C07 |
| 35 | 12 | 0 | 135 | 4 | 4 | R04 | C02 | R04 | C02 |
| 35 | 14 | 3 | 186 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 14 | 4 | 191 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 16 | 3 | 231 | 0 | 0 | R02 | C13 | R02 | C13 |
| 35 | 16 | 3 | 233 | 0 | 0 | R02 | C14 | R02 | C14 |
| 35 | 17 | 0 | 237 | 1 | 1 | R02 | C06 | R02 | C06 |
| 35 | 17 | 0 | 238 | ? | ? | R11 | C20 | R11 | C20 |
| 35 | 17 | 5 | 258 | 1 | 1 | R02 | C06 | R02 | C06 |
| 35 | 18 | 0 | 262 | 1 | 1 | R02 | C06 | R02 | C06 |
| 35 | 18 | 4 | 275 | ? | ? | R07 | C11 | R07 | C11 |
| 35 | 18 | 4 | 276 | ? | ? | R03 | C12 | R03 | C12 |
| 35 | 18 | 4 | 277 | ? | ? | R03 | C12 | R03 | C12 |
| 35 | 18 | 4 | 278 | ? | ? | R11 | C20 | R11 | C20 |
| 35 | 19 | 2 | 294 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 20 | 2 | 310 | 0 | 0 | R02 | C04 | R02 | C04 |
| 35 | 20 | 3 | 314 | 1 | 1 | R02 | C05 | R02 | C05 |
| 35 | 20 | 3 | 315 | ? | ? | R03 | C12 | R03 | C12 |
| 35 | 20 | 3 | 316 | ? | ? | R03 | C12 | R03 | C12 |
| 35 | 21 | 5 | 346 | ? | ? | R07 | C11 | R07 | C11 |
| 35 | 21 | 5 | 347 | 0 | 0 | R02 | C05 | R02 | C05 |
| 35 | 22 | 0 | 348 | ? | ? | R07 | C11 | R07 | C11 |
| 35 | 22 | 1 | 355 | 4 | 4 | R04 | C02 | R04 | C02 |
| 35 | 24 | 0 | 399 | 4 | 4 | R02 | C09 | R02 | C09 |
| 35 | 24 | 3 | 405 | 5 | 5 | R04 | C02 | R04 | C02 |
| 35 | 24 | 4 | 409 | 5 | 5 | R04 | C02 | R04 | C02 |
| 35 | 25 | 3 | 428 | 3 | 3 | R02 | C04 | R02 | C04 |
| 35 | 25 | 4 | 431 | 7 | 7 | R02 | C04 | R02 | C04 |
| 35 | 26 | 2 | 448 | 1 | 1 | R02 | C06 | R02 | C06 |
| 35 | 26 | 4 | 454 | 0 | 0 | R02 | C21 | R02 | C21 |
| 35 | 26 | 5 | 460 | 3 | 3 | R02 | C21 | R02 | C21 |
| 35 | 28 | 0 | 483 | 3 | 3 | R02 | C05 | R02 | C05 |
| 35 | 28 | 1 | 484 | 1 | 1 | R02 | C05 | R02 | C05 |
| 35 | 28 | 1 | 486 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 28 | 2 | 489 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 28 | 3 | 495 | 1 | 1 | R02 | C05 | R02 | C05 |
| 35 | 28 | 4 | 498 | 5 | 5 | R02 | C04 | R02 | C04 |
| 35 | 29 | 1 | 505 | 1 | 1 | R06 | C30 | R06 | C30 |
| 35 | 29 | 2 | 508 | 2 | 2 | R04 | C02 | R04 | C02 |
| 35 | 29 | 2 | 510 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 29 | 3 | 514 | 1 | 1 | R02 | C05 | R02 | C05 |
| 35 | 29 | 3 | 515 | 3 | 3 | R04 | C02 | R04 | C02 |
| 35 | 29 | 4 | 516 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 29 | 4 | 517 | 5 | 5 | R04 | C02 | R04 | C02 |
| 35 | 30 | 0 | 520 | 0 | 0 | R02 | C26 | R02 | C26 |
| 35 | 30 | 0 | 521 | 2 | 2 | R04 | C02 | R04 | C02 |
| 35 | 30 | 0 | 522 | 0 | 0 | R04 | C02 | R04 | C02 |
| 35 | 30 | 0 | 523 | 0 | 0 | R04 | C02 | R04 | C02 |
| 35 | 30 | 1 | 527 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 30 | 2 | 529 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 30 | 2 | 531 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 31 | 3 | 555 | 1 | 1 | R02 | C05 | R02 | C05 |
| 35 | 31 | 4 | 559 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 32 | 0 | 560 | 1 | 1 | R04 | C02 | R04 | C02 |
| 35 | 32 | 2 | 571 | ? | ? | R07 | C11 | R07 | C11 |
| 35 | 32 | 2 | 572 | 0 | 0 | R02 | C05 | R02 | C05 |
| 35 | 32 | 2 | 573 | 0 | 0 | R02 | C05 | R02 | C05 |
| 35 | 33 | 0 | 587 | 4 | 4 | R04 | C02 | R04 | C02 |
| 36 | 0 | 1 | 4 | 0 | written | R02 | C05 | written | written |
| 36 | 1 | 4 | 28 | 2 | 2 | R12 | C27 | R12 | C27 |
| 37 | 0 | 1 | 3 | 1 | 1 | R02 | C16 | R02 | C16 |
| 39 | 0 | 0 | 0 | 0 | 0 | R02 | C01 | R02 | C01 |
| 39 | 0 | 3 | 6 | ? | ? | R03 | C28 | R03 | C28 |
| 39 | 0 | 3 | 7 | 0 | 0 | R04 | C02 | R04 | C02 |
| 39 | 0 | 3 | 9 | 0 | 0 | R04 | C02 | R04 | C02 |
| 39 | 1 | 0 | 10 | 0 | 0 | R02 | C01 | R02 | C01 |
| 39 | 1 | 0 | 11 | 0 | 0 | R02 | C01 | R02 | C01 |
| 39 | 1 | 0 | 12 | 0 | 0 | R02 | C01 | R02 | C01 |
| 39 | 1 | 0 | 13 | 0 | 0 | R02 | C01 | R02 | C01 |
| 39 | 1 | 1 | 14 | 5 | 5 | R02 | C29 | R02 | C29 |
| 39 | 1 | 3 | 23 | ? | ? | R07 | C15 | R07 | C15 |
| 39 | 2 | 0 | 30 | ? | ? | R03 | C03 | R03 | C03 |
| 39 | 2 | 0 | 31 | 0 | 0 | R04 | C02 | R04 | C02 |
| 39 | 2 | 0 | 33 | 0 | 0 | R04 | C02 | R04 | C02 |
| 40 | 0 | 2 | 5 | 5 | 5 | R02 | C04 | R02 | C04 |
| 40 | 1 | 0 | 10 | 10 | 10 | R02 | C09 | R02 | C09 |
| 40 | 1 | 0 | 11 | 0 | 0 | R02 | C09 | R02 | C09 |
| 40 | 1 | 1 | 12 | 4 | 4 | R02 | C06 | R02 | C06 |
| 42 | 0 | 4 | 23 | 2 | 2 | R02 | C14 | R02 | C14 |
| 42 | 1 | 0 | 25 | 0 | 0 | R02 | C13 | R02 | C13 |
| 42 | 1 | 2 | 42 | ? | ? | R03 | C03 | R03 | C03 |
| 42 | 1 | 2 | 43 | ? | ? | R03 | C03 | R03 | C03 |
