# TECH-02: bends the reference files have, checked by the independent oracle

Status: **oracle and measurement only. Goal 3 (the reader) is blocked, not complete.** No file under `src/` changed.

Baseline `577ff5a` (main after TECH-01), Windows runtime. Normal CLI `convert --pdf <pdf> --pdf-only-tab --time-signature 4/4` over all 43 approved PDFs. Counts, positions and codes only.

## Goal 1: oracle

`tests/test_dur_02_oracle.py` now reads, per note, `Bended` and the seven native properties `BendOriginValue`, `BendOriginOffset`, `BendMiddleValue`, `BendMiddleOffset1`, `BendMiddleOffset2`, `BendDestinationValue`, `BendDestinationOffset` verbatim, and compares them as the event field `bend` (by bar and event). A property the file lacks reads as absent, not zero. It does not import score2gp. Existing oracle tests pass unchanged (`TECHNIQUE_FIELDS` is unchanged; `bend` is added to `EVENT_FIELDS` beside it).

## Goal 2: measurement (reference bends the output lacks, writes differently, or adds)

| source | reference bends | written by product | missing | different | extra | printed mark on the page |
|---|---:|---:|---:|---:|---:|---|
| Melodic Soloing Masterclass (design) | 3 (bars 1/5/7, events 5/7/4) | 0 | 3 | 0 | 0 | labelled `full` up-arrow, then a release arrow to the next note (bend-and-release) |
| Ex 2 Hands Up (holdout) | 1 (bar 9, event 0) | 0 | 1 | 0 | 0 | labelled `full` up-arrow, then a release arrow to the tied next note |
| Can't Find My Way Home | 6 (bars 10, 11, 15 x2, 18, 19) | 0 | 6 | 0 | 0 | one `1/2` label extracted as text; the other marks are not extracted as text |
| Derek Trucks BB King | 8 (bars 10, 12 x4, 13 x2, 14; track 0) | no output | 8 | - | - | whole source refused (`pdf_only_tab_no_bar_written`); one `1/2` label |
| Bebop, Lesson-3..7 | 0 | 0 | 0 | 0 | 0 | none (Lesson-3 prints `1/4`, `3/4` text, no reference bend) |
| Mixing Lead & Rhythm pt1, no-notes | not readable by the oracle (reference is not an XML GPIF zip) | | | | | |

The product adds no bend any reference lacks. Whole-source refusals and the 10 reference tracks: see `tests/test_tech_02_private.py`.

## Goal 3: blocked, with the located cause

The page evidences the *amount* (`full`) and the *shape* (up-arrow, release arrow landing on the next note). It does not evidence the stored offsets, and the oracle compares them exactly:

- The three design bends store one envelope. The holdout bend prints the same labelled shape, and stores the same origin, origin offset, peak value and release value, but a different second middle offset and destination offset (two of seven values differ).
- Measured printed geometry, as a fraction of the digit-to-next-digit span: design arrow peak about 44 % and release tip about 73 %; holdout peak about 51 % and release tip about 94 %. Stored destination offsets move 50 to 99, so there is no one function of the printed geometry that gives both. Other references store further different offsets (Can't Find My Way Home: three more destination offsets), for marks the page does not separate by shape.
- Writing the offsets that match the design source would be copying reference values (forbidden); writing a geometric guess would write a bend that the oracle marks different. A bend the page does not fully evidence stays unwritten and located, so the reader is not changed. The gate (a newly matching holdout bend) cannot be met, and it is not waived; no other holdout is substituted.

## Goal 4 / acceptance 4: before and after the whole private set

Nothing in `src/` changed, so after equals before: every inner `Content/score.gpif` is byte-identical and no source's written GPIF changed. Bars written 1407, refused 244 (35 x exit 0, 4 x exit 2, 4 x exit 4; with `--time-signature 4/4` this adds `time_signature_conflict` 45; the REFUSE-26 figures 1441/210 were measured without that flag).

Refused by code: `note_duration_event_unread` 112, `notation_note_without_tab_digit` 50, `time_signature_conflict` 45, `bar_without_notation_event` 11, `notehead_digit_count_mismatch` 11, `bar_total_mismatch` 6, `tie_head_ownership_unconfirmed` 2, `tab_digit_without_notation_event` 2, `tab_system_digit_unassigned_to_bar` 2, `duration_off_tick_grid` 1, `notation_tab_column_ambiguous` 1, `tab_chord_arrow_unread` 1. Bends added where no reference can check: none.

## Goal 5: other reference differences seen (located, not fixed)

Melodic: `double_bar` 1, `master_bar_extra_children` 8, `tie` 2 (unchanged from TECH-01). Can't Find My Way Home: 2 of 21 bars refused; Lesson-6: 1 of 72 refused; Derek Trucks: whole source refused. Slide differences are those recorded by TECH-01.
