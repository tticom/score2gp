# REFUSE-20: fresh refusal census and corrected limits

Measured at `6e97078938b36ced93f1eaecd76b8123fe3eb19e` using the checkout virtualenv and the normal strict CLI:
`python -m score2gp.cli convert --pdf <approved-pdf> --pdf-only-tab --out <ignored-output> --work-dir <ignored-build> --json-report <ignored-report>`.
All 43 approved PDFs exist and match their manifest hashes. No sidecar or reference was supplied.
Private source names, commands, inputs and generated content remain in ignored storage.
Source indices below follow the sorted PDF inventory; all page, system, bar and event indices are zero-based.

## Outcome and measurement boundary

This remains **unfinished**, with no reader change and no newly written bar.
The fresh run produced 38 packages, 1423 located written bars and 228 located refused bars.
Five sources have no usable bar route. Their refused bar totals and page/system/bar/event locations are unknown;
they are not zero-bar sources and are excluded from the numeric bar ranking below.
Consequently this is a ranking of routed bars, **not a proved whole-corpus ranking**.
Every refusal is a reader gap, a representation gap or unknown; none is a correct-refusal classification.

The earlier claim that the 44 missing-column bars are a representation gap is withdrawn.
`BendTechnique` already exists in `src/score2gp/ir.py:285`, including semitones, points, bend type,
destination value and graphic duration. `src/score2gp/gpif.py:2095` writes bends and points and
`src/score2gp/gpif.py:2379` writes the Bended property. Fractional semitone values are representable.
The bend branches at `src/score2gp/build_ir.py:2906` and `src/score2gp/build_ir.py:4844` also exist.
Those detailed emission paths belong to the legacy layout. The normal writer defaults to the relational layout
(`gpif.py:13`), whose bend branch at `gpif.py:1001` only enables Bended. Presence of legacy support does not
prove normal-output bend fidelity.

A read-only probe of all 12 approved GP references found 11 readable packages and 1 XML parse failure.
Four readable references contain 16 Bended properties and 48 origin/middle/destination value properties.
Reference extraction produced 18 bend techniques with 0 nonempty point lists; the count expansion is not
explained by this probe. Re-emitting through the normal relational writer produced 18 Bended properties,
0 Bend nodes, 0 points and 0 origin/middle/destination value properties. The reference parser at
`gp_package.py:941` checks Bended but reads points only from a Bend node, whereas these references encode
their curves in properties. Both parser and default writer therefore need fidelity work before this route can
serve as a bend oracle. The legacy writer's fallback emission is not evidence of preserving those reference curves.
These are counts-only capability-probe results, not PDF recognition or new-reader acceptance.
No reference values were supplied to a PDF conversion or copied into product code.

The PDF-only route goes through `build_ir.py:1909`, digit recovery and the bar assembler.
`pdf_tab_digit_recovery.py:97` can withhold parenthesized/run digits; its technique and ink guards
can also withhold recovery. The no-column branch in `pdf_tab_bar_assembler.py` then refuses an unmatched event.
`pdf_tab_event_factory.py:130` constructs ties and palm mutes but does not construct a BendTechnique.
The later PDF-only attachment call at `build_ir.py:2122` can reach the bend branch at `build_ir.py:4844`;
that branch appends a bend with unspecified semitones and no points to an already written note.
It cannot recover the missing TAB ownership of a bar the assembler has already refused, nor does its
existence prove that a labelled bend amount or release curve reached the normal GPIF output.
These are reader/handoff gaps in addition to the measured default-layout fidelity gap;
they do not establish that the IR or every writer layout lacks bends.
Simply dropping a guard would lose printed content and is not a repair.

The earlier assertions that all 73 rhythm-mark failures are not settled by the page, all 13 unidentified
rest forms are bend heads, and a 54-bar withheld-recovery family is uniformly bends are also withdrawn.
The diagnostic codes do not establish those page-level conclusions. Page samples show multiple techniques
and multiple reader seams; they do not establish a per-bar semantic oracle for the entire class.
No class is declared globally largest or unplayable. The page/reference verification, reader,
held-out finished-reader run and real-source drop-rule mutant remain unperformed.
Synthetic tests carry zero acceptance weight.

## Output preservation boundary

Direct comparison of the fresh outputs with retained outputs from `d1076ab23ab09e4e469b476d3c48007264ec5139`
found byte-identical inner `Content/score.gpif` in all 38 packages: 0 changed sources and 0 newly written bars.
The source difference between that retained baseline and the reviewed runtime is documentation only.
This is preservation evidence for the unchanged converter, not a finished-reader before/after acceptance run.
No new bar exists to verify against a reference or page; no new-bar fidelity or independent verification is claimed.

## Source-level refusals (bar totals and all locations unknown)

| Source index | Code | Located diagnostic cause code | Classification |
|---:|---|---|---|
| 3 | `pdf_only_tab_no_notation_bars` | `unknown` | unknown |
| 22 | `pdf_only_tab_grouping_unsafe` | `scanned_raster_source_without_vector_tab` | unknown |
| 25 | `pdf_only_tab_grouping_unsafe` | `scanned_raster_source_without_vector_tab` | unknown |
| 27 | `pdf_only_tab_grouping_unsafe` | `text_without_tab_rows` | unknown |
| 33 | `pdf_only_tab_grouping_unsafe` | `ascii_tab_rows_without_barlines_or_rhythm` | unknown |

## Routed refusals by code

| Code ID | Code | Bars |
|---|---|---:|
| R01 | `note_duration_event_unread` | 130 |
| R02 | `bar_without_notation_event` | 20 |
| R03 | `notation_note_without_tab_digit` | 53 |
| R04 | `duration_off_tick_grid` | 1 |
| R05 | `notehead_digit_count_mismatch` | 10 |
| R06 | `bar_total_mismatch` | 6 |
| R07 | `tie_head_ownership_unconfirmed` | 2 |
| R08 | `tab_system_digit_unassigned_to_bar` | 2 |
| R09 | `notation_tab_column_ambiguous` | 1 |
| R10 | `tab_digit_without_notation_event` | 2 |
| R11 | `tab_chord_arrow_unread` | 1 |

## Routed first causes, ranked by bar count

Each bar contributes its first located refusal once. Additional unread marks may coexist in the same bar.
Reader-gap labels identify an unread association/symbol, not a claim that the page supplies an already-verified reading.
Only the explicit tick-grid failure is classified as a representation gap; uncertain mixed/concurrent/empty/total cases stay unknown.

| Cause ID | Cause code | Bars | Classification |
|---|---|---:|---|
| C01 | `tab_column_without_rhythm_mark` | 73 | reader_gap |
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

## REFUSE-19 exclusion

REFUSE-19 addressed bare palm marks and positively read bar-key glyphs: the 1 palm-mark bar and 2 key-glyph bars
remain written in the fresh whole-source runs. Their addressed classes are excluded from this refused-bar selection.
This does not mean every bar containing a palm mark or key signature is written; other unread evidence remains.

## Per-bar located diagnostic reasons

This is diagnostic evidence, not per-bar printed-page verification. `?` is an unavailable event index for a
bar/system-level failure, never an invented event. 31 event indices are unavailable.
Cause IDs and code IDs resolve to the tables above. Every routed refused bar is listed exactly once.
The five source-level failures above remain additional unfinished coverage.

| Source index | Page | System | Bar | Event | Code ID | Cause ID |
|---:|---:|---:|---:|---:|---|---|
| 4 | 0 | 0 | 0 | 0 | R01 | C01 |
| 4 | 0 | 0 | 1 | 0 | R01 | C01 |
| 4 | 0 | 0 | 4 | 0 | R01 | C01 |
| 4 | 0 | 0 | 5 | 0 | R01 | C01 |
| 4 | 0 | 1 | 8 | 0 | R01 | C01 |
| 4 | 0 | 1 | 9 | 0 | R01 | C01 |
| 4 | 0 | 1 | 12 | 0 | R01 | C01 |
| 4 | 0 | 1 | 13 | 0 | R01 | C01 |
| 4 | 0 | 1 | 14 | 0 | R01 | C01 |
| 4 | 0 | 1 | 16 | ? | R02 | C03 |
| 4 | 0 | 2 | 17 | 0 | R01 | C01 |
| 4 | 0 | 2 | 18 | 0 | R01 | C01 |
| 4 | 0 | 2 | 19 | 0 | R01 | C01 |
| 4 | 0 | 2 | 20 | 0 | R01 | C01 |
| 4 | 0 | 2 | 21 | 0 | R01 | C01 |
| 4 | 0 | 3 | 22 | 0 | R01 | C01 |
| 4 | 0 | 3 | 23 | 0 | R01 | C01 |
| 4 | 0 | 3 | 24 | 0 | R01 | C01 |
| 4 | 0 | 3 | 25 | 0 | R01 | C01 |
| 4 | 0 | 3 | 26 | 0 | R01 | C01 |
| 4 | 0 | 4 | 27 | 0 | R01 | C01 |
| 4 | 0 | 4 | 28 | 0 | R01 | C01 |
| 4 | 0 | 4 | 29 | 0 | R01 | C01 |
| 4 | 0 | 4 | 30 | 0 | R01 | C01 |
| 4 | 0 | 4 | 31 | 0 | R01 | C01 |
| 4 | 0 | 4 | 32 | 0 | R01 | C01 |
| 4 | 0 | 4 | 33 | 0 | R01 | C01 |
| 4 | 0 | 4 | 34 | 0 | R01 | C01 |
| 4 | 0 | 4 | 35 | 0 | R01 | C01 |
| 4 | 0 | 5 | 36 | 0 | R01 | C01 |
| 4 | 0 | 5 | 37 | 0 | R01 | C01 |
| 4 | 0 | 5 | 38 | 0 | R01 | C01 |
| 4 | 0 | 5 | 39 | 0 | R01 | C01 |
| 4 | 0 | 5 | 40 | 0 | R01 | C01 |
| 4 | 0 | 5 | 41 | 0 | R01 | C01 |
| 4 | 0 | 5 | 42 | 0 | R01 | C01 |
| 4 | 0 | 5 | 43 | 0 | R01 | C01 |
| 4 | 0 | 5 | 44 | 0 | R01 | C01 |
| 4 | 0 | 6 | 45 | 0 | R01 | C01 |
| 4 | 0 | 6 | 46 | ? | R02 | C03 |
| 4 | 0 | 6 | 47 | 0 | R01 | C01 |
| 4 | 0 | 6 | 48 | 0 | R01 | C01 |
| 4 | 0 | 6 | 49 | ? | R02 | C03 |
| 4 | 0 | 6 | 50 | 0 | R01 | C01 |
| 4 | 0 | 6 | 51 | 0 | R01 | C01 |
| 4 | 0 | 6 | 52 | 0 | R01 | C01 |
| 4 | 0 | 7 | 53 | 0 | R01 | C01 |
| 4 | 0 | 7 | 54 | 0 | R01 | C01 |
| 4 | 0 | 7 | 55 | ? | R02 | C03 |
| 4 | 0 | 7 | 56 | ? | R02 | C03 |
| 4 | 0 | 7 | 57 | 0 | R01 | C01 |
| 4 | 0 | 7 | 58 | 0 | R01 | C01 |
| 4 | 0 | 8 | 59 | 0 | R01 | C01 |
| 4 | 0 | 8 | 60 | 0 | R01 | C01 |
| 4 | 0 | 8 | 61 | 0 | R01 | C01 |
| 4 | 0 | 8 | 62 | ? | R02 | C03 |
| 4 | 0 | 8 | 63 | 0 | R01 | C01 |
| 4 | 0 | 8 | 64 | 0 | R01 | C01 |
| 4 | 0 | 8 | 65 | 0 | R01 | C01 |
| 4 | 0 | 8 | 66 | ? | R02 | C03 |
| 4 | 1 | 0 | 67 | 0 | R01 | C01 |
| 4 | 1 | 0 | 68 | 0 | R01 | C01 |
| 4 | 1 | 0 | 69 | 0 | R01 | C01 |
| 4 | 1 | 0 | 70 | 0 | R01 | C01 |
| 4 | 1 | 0 | 71 | 0 | R01 | C01 |
| 4 | 1 | 0 | 72 | 0 | R01 | C01 |
| 4 | 1 | 0 | 73 | 0 | R01 | C01 |
| 4 | 1 | 0 | 74 | 0 | R01 | C01 |
| 4 | 1 | 0 | 75 | ? | R02 | C03 |
| 4 | 1 | 1 | 76 | 0 | R01 | C01 |
| 4 | 1 | 1 | 77 | 0 | R01 | C01 |
| 4 | 1 | 2 | 78 | 0 | R01 | C01 |
| 4 | 1 | 2 | 79 | 0 | R01 | C01 |
| 4 | 1 | 2 | 80 | 0 | R01 | C01 |
| 4 | 1 | 2 | 81 | 0 | R01 | C01 |
| 4 | 1 | 2 | 82 | 0 | R01 | C01 |
| 7 | 0 | 0 | 0 | 2 | R03 | C02 |
| 8 | 0 | 3 | 7 | ? | R04 | C22 |
| 10 | 0 | 0 | 1 | 2 | R03 | C02 |
| 10 | 0 | 0 | 2 | 0 | R03 | C07 |
| 10 | 0 | 1 | 3 | 0 | R03 | C07 |
| 10 | 0 | 1 | 4 | 0 | R03 | C07 |
| 12 | 0 | 1 | 3 | 2 | R05 | C08 |
| 12 | 0 | 3 | 6 | 5 | R01 | C04 |
| 12 | 0 | 4 | 9 | 6 | R05 | C08 |
| 13 | 0 | 1 | 2 | 9 | R01 | C04 |
| 13 | 0 | 1 | 3 | 1 | R01 | C06 |
| 13 | 0 | 2 | 4 | ? | R06 | C15 |
| 15 | 0 | 1 | 5 | 0 | R01 | C09 |
| 15 | 0 | 1 | 6 | 0 | R03 | C07 |
| 15 | 0 | 1 | 7 | 0 | R03 | C07 |
| 15 | 0 | 3 | 13 | 6 | R01 | C06 |
| 15 | 1 | 1 | 18 | 9 | R01 | C06 |
| 15 | 1 | 4 | 25 | 0 | R01 | C13 |
| 15 | 2 | 0 | 26 | 0 | R03 | C07 |
| 15 | 2 | 0 | 28 | 6 | R01 | C16 |
| 15 | 2 | 0 | 29 | 0 | R03 | C07 |
| 15 | 2 | 1 | 31 | 5 | R01 | C23 |
| 15 | 2 | 4 | 36 | 13 | R01 | C06 |
| 15 | 2 | 4 | 37 | 0 | R03 | C07 |
| 16 | 0 | 1 | 2 | 4 | R01 | C04 |
| 16 | 0 | 2 | 4 | 6 | R01 | C04 |
| 16 | 0 | 2 | 5 | 2 | R01 | C04 |
| 16 | 0 | 3 | 6 | 6 | R01 | C04 |
| 16 | 1 | 1 | 12 | 1 | R01 | C24 |
| 16 | 1 | 3 | 15 | 4 | R01 | C04 |
| 17 | 0 | 2 | 7 | 3 | R05 | C17 |
| 17 | 0 | 3 | 13 | 5 | R05 | C08 |
| 17 | 0 | 3 | 14 | 2 | R05 | C10 |
| 20 | 0 | 0 | 1 | 8 | R05 | C10 |
| 20 | 0 | 1 | 3 | 5 | R05 | C10 |
| 20 | 0 | 1 | 5 | 8 | R05 | C10 |
| 20 | 0 | 2 | 7 | 5 | R01 | C04 |
| 21 | 0 | 0 | 2 | ? | R02 | C03 |
| 21 | 0 | 1 | 5 | ? | R02 | C03 |
| 21 | 0 | 2 | 8 | ? | R02 | C03 |
| 21 | 0 | 3 | 9 | ? | R02 | C03 |
| 24 | 1 | 1 | 11 | 20 | R01 | C06 |
| 26 | 0 | 0 | 0 | 0 | R01 | C14 |
| 31 | 1 | 5 | 26 | 11 | R07 | C18 |
| 35 | 1 | 0 | 9 | 10 | R07 | C18 |
| 35 | 1 | 3 | 15 | ? | R08 | C19 |
| 35 | 1 | 3 | 16 | ? | R08 | C19 |
| 35 | 1 | 4 | 17 | 2 | R03 | C02 |
| 35 | 1 | 4 | 18 | 1 | R01 | C04 |
| 35 | 2 | 0 | 19 | 1 | R01 | C06 |
| 35 | 2 | 0 | 20 | 1 | R01 | C05 |
| 35 | 3 | 1 | 32 | 5 | R03 | C02 |
| 35 | 3 | 1 | 33 | 5 | R03 | C02 |
| 35 | 3 | 1 | 34 | 4 | R03 | C02 |
| 35 | 4 | 2 | 46 | 2 | R01 | C04 |
| 35 | 5 | 0 | 52 | 0 | R01 | C05 |
| 35 | 5 | 4 | 62 | 0 | R01 | C05 |
| 35 | 6 | 1 | 67 | 0 | R03 | C02 |
| 35 | 6 | 1 | 68 | 0 | R03 | C02 |
| 35 | 6 | 2 | 70 | 0 | R03 | C02 |
| 35 | 6 | 2 | 71 | 0 | R03 | C02 |
| 35 | 8 | 1 | 90 | 4 | R09 | C25 |
| 35 | 8 | 3 | 95 | 0 | R03 | C02 |
| 35 | 8 | 3 | 96 | 0 | R03 | C02 |
| 35 | 8 | 3 | 97 | 0 | R03 | C02 |
| 35 | 10 | 1 | 115 | 1 | R05 | C08 |
| 35 | 10 | 4 | 121 | 4 | R03 | C02 |
| 35 | 11 | 2 | 129 | 0 | R03 | C02 |
| 35 | 11 | 3 | 130 | 1 | R03 | C02 |
| 35 | 11 | 3 | 131 | 0 | R03 | C02 |
| 35 | 11 | 3 | 132 | 0 | R03 | C07 |
| 35 | 12 | 0 | 135 | 4 | R03 | C02 |
| 35 | 14 | 3 | 186 | 1 | R03 | C02 |
| 35 | 14 | 4 | 191 | 1 | R03 | C02 |
| 35 | 16 | 3 | 231 | 0 | R01 | C13 |
| 35 | 16 | 3 | 233 | 0 | R01 | C14 |
| 35 | 17 | 0 | 237 | 1 | R01 | C06 |
| 35 | 17 | 0 | 238 | ? | R10 | C20 |
| 35 | 17 | 5 | 258 | 1 | R01 | C06 |
| 35 | 18 | 0 | 262 | 1 | R01 | C06 |
| 35 | 18 | 4 | 275 | ? | R06 | C11 |
| 35 | 18 | 4 | 276 | ? | R02 | C12 |
| 35 | 18 | 4 | 277 | ? | R02 | C12 |
| 35 | 18 | 4 | 278 | ? | R10 | C20 |
| 35 | 19 | 2 | 294 | 1 | R03 | C02 |
| 35 | 20 | 2 | 310 | 0 | R01 | C04 |
| 35 | 20 | 3 | 314 | 1 | R01 | C05 |
| 35 | 20 | 3 | 315 | ? | R02 | C12 |
| 35 | 20 | 3 | 316 | ? | R02 | C12 |
| 35 | 21 | 5 | 346 | ? | R06 | C11 |
| 35 | 21 | 5 | 347 | 0 | R01 | C05 |
| 35 | 22 | 0 | 348 | ? | R06 | C11 |
| 35 | 22 | 1 | 355 | 4 | R03 | C02 |
| 35 | 24 | 0 | 399 | 4 | R01 | C09 |
| 35 | 24 | 3 | 405 | 5 | R03 | C02 |
| 35 | 24 | 4 | 409 | 5 | R03 | C02 |
| 35 | 25 | 3 | 428 | 3 | R01 | C04 |
| 35 | 25 | 4 | 431 | 7 | R01 | C04 |
| 35 | 26 | 2 | 448 | 1 | R01 | C06 |
| 35 | 26 | 4 | 454 | 0 | R01 | C21 |
| 35 | 26 | 5 | 460 | 3 | R01 | C21 |
| 35 | 28 | 0 | 483 | 3 | R01 | C05 |
| 35 | 28 | 1 | 484 | 1 | R01 | C05 |
| 35 | 28 | 1 | 486 | 1 | R03 | C02 |
| 35 | 28 | 2 | 489 | 1 | R03 | C02 |
| 35 | 28 | 3 | 495 | 1 | R01 | C05 |
| 35 | 28 | 4 | 498 | 5 | R01 | C04 |
| 35 | 29 | 1 | 505 | 1 | R05 | C17 |
| 35 | 29 | 2 | 508 | 2 | R03 | C02 |
| 35 | 29 | 2 | 510 | 1 | R03 | C02 |
| 35 | 29 | 3 | 514 | 1 | R01 | C05 |
| 35 | 29 | 3 | 515 | 3 | R03 | C02 |
| 35 | 29 | 4 | 516 | 1 | R03 | C02 |
| 35 | 29 | 4 | 517 | 5 | R03 | C02 |
| 35 | 30 | 0 | 520 | 0 | R01 | C26 |
| 35 | 30 | 0 | 521 | 2 | R03 | C02 |
| 35 | 30 | 0 | 522 | 0 | R03 | C02 |
| 35 | 30 | 0 | 523 | 0 | R03 | C02 |
| 35 | 30 | 1 | 527 | 1 | R03 | C02 |
| 35 | 30 | 2 | 529 | 1 | R03 | C02 |
| 35 | 30 | 2 | 531 | 1 | R03 | C02 |
| 35 | 31 | 3 | 555 | 1 | R01 | C05 |
| 35 | 31 | 4 | 559 | 1 | R03 | C02 |
| 35 | 32 | 0 | 560 | 1 | R03 | C02 |
| 35 | 32 | 2 | 571 | ? | R06 | C11 |
| 35 | 32 | 2 | 572 | 0 | R01 | C05 |
| 35 | 32 | 2 | 573 | 0 | R01 | C05 |
| 35 | 33 | 0 | 587 | 4 | R03 | C02 |
| 36 | 0 | 1 | 4 | 0 | R01 | C05 |
| 36 | 1 | 4 | 28 | 2 | R11 | C27 |
| 37 | 0 | 1 | 3 | 1 | R01 | C16 |
| 39 | 0 | 0 | 0 | 0 | R01 | C01 |
| 39 | 0 | 3 | 6 | ? | R02 | C28 |
| 39 | 0 | 3 | 7 | 0 | R03 | C02 |
| 39 | 0 | 3 | 9 | 0 | R03 | C02 |
| 39 | 1 | 0 | 10 | 0 | R01 | C01 |
| 39 | 1 | 0 | 11 | 0 | R01 | C01 |
| 39 | 1 | 0 | 12 | 0 | R01 | C01 |
| 39 | 1 | 0 | 13 | 0 | R01 | C01 |
| 39 | 1 | 1 | 14 | 5 | R01 | C29 |
| 39 | 1 | 3 | 23 | ? | R06 | C15 |
| 39 | 2 | 0 | 30 | ? | R02 | C03 |
| 39 | 2 | 0 | 31 | 0 | R03 | C02 |
| 39 | 2 | 0 | 33 | 0 | R03 | C02 |
| 40 | 0 | 2 | 5 | 5 | R01 | C04 |
| 40 | 1 | 0 | 10 | 10 | R01 | C09 |
| 40 | 1 | 0 | 11 | 0 | R01 | C09 |
| 40 | 1 | 1 | 12 | 4 | R01 | C06 |
| 42 | 0 | 4 | 23 | 2 | R01 | C14 |
| 42 | 1 | 0 | 25 | 0 | R01 | C13 |
| 42 | 1 | 2 | 42 | ? | R02 | C03 |
| 42 | 1 | 2 | 43 | ? | R02 | C03 |
