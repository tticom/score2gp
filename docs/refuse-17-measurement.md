# REFUSE-17 measurement: bars with no notation event and no TAB item

Normal CLI (`convert --pdf-only-tab`) over every approved PDF (43 `*.pdf` in `fixtures/private/`), `main` at bb09e4a. Counts and codes only; every bar was viewed on the printed page.

## Before

Bars written 899. Refused `bar_without_notation_event`: **31** (the brief's 29 plus 2 `PARANOID` bars since PERCX-01). Other refused: 88 note_duration_event_unread, 23 notation_note_without_tab_digit, 9 notehead_digit_count_mismatch, 6 bar_total_mismatch, 1 tie_head_ownership_unconfirmed.

## What is printed in the 31 bars (reader / representation gaps; none is a correct refusal)

| bars | source | printed content | kind | result |
|---|---|---|---|---|
| 1 | Ex 2 Hands Up (bar 0) | clef, meter and a start-repeat sign only: not a bar | reader gap (topology) | **read**: dropped as a bar; 11 bars = reference |
| 6 + 1 | 7_Grateful_Dead_Melodies, PARANOID | fret digits printed in the bar, extracted as ungrouped text | reader gap (TAB extraction, TABEXT) | stay refused; cause now `tab_digits_printed_but_not_grouped` |
| 8-9 by eye | 7_Grateful_Dead_Melodies | fret digits printed (seen on the page) that TabRaw holds no candidate for | reader gap (TAB extraction) | stay refused, cause still `bar_without_notation_or_tab_item` (unfinished: the assembler cannot see the PDF) |
| 3 | 7_Grateful_Dead_Melodies | one-bar / two-bar repeat sign | representation gap (no simile in ScoreIR) | stay refused. The bars it repeats are themselves refused, so there is nothing to copy |
| 4 | Gloria | blank staff after an end-repeat / the last bar with clef and key only | unknown | stay refused (nothing printed; no rest invented) |
| 2 | The_EXACT_System | blank bars | unknown | stay refused |
| 4-5 by eye | 7_Grateful_Dead_Melodies | blank bars (section ends, final bars) | unknown | stay refused |

No bar is a printed whole-bar rest. The by-eye counts (rows marked "by eye") are not machine-counted and are approximate by one bar; machine counts after the change are 7 `tab_digits_printed_but_not_grouped` (6 Grateful, 1 PARANOID) and 23 `bar_without_notation_or_tab_item` (16 Grateful, 4 Gloria, 2 EXACT, 1 PARANOID).

## Change

1. `notation_omr/note_duration.py` (+ `pdf.py`, `build_ir.py`): a first barline cluster that is a start-repeat sign (thick band left of it, two small discs right of it, only an unbroken header run before it) is no bar boundary. `Ex 2 Hands Up` now has 11 source bars, all written; each equals its reference bar by content, and the repeat flags now sit on the reference's bars (start on bar 1, ends on 4, 6, 8; before, all four were one bar late). The sign is carried to the output as a `bar_start` repeat-start barline signal on the first bar (the system record gains an optional `leading_start_repeat` key, present only there; no schema string was bumped). (tempo, track name and total note count differences are unchanged from before).
2. `pdf_tab_bar_assembler.py` / `build_ir.py`: a refused empty bar in a TAB-only system that holds printed numbers no grouped column owns is located as `tab_digits_printed_but_not_grouped` with the count and ids, instead of "nothing printed".

## After

Bars written 899 (Ex 2: 11 written, the phantom bar is gone, no longer refused). Refused `bar_without_notation_event` 30. Every other refusal count is unchanged. Inner `Content/score.gpif`: 36 of 37 converting sources byte-identical; the one changed is `Ex 2 Hands Up` (phantom empty bar removed). Exit codes unchanged for all 43 PDFs.

## Existing tests updated (not weakened)

Six tests hard-coded `Ex 2 Hands Up` bar indices that counted the phantom bar (one carried a comment about the offset): `test_omit_02_private` (2 tests: partitions 5/4/3 -> 4/4/3, repeat ends 5/7/9 -> 4/6/8), `test_refuse_03_staff_background_private`, `test_refuse_14_ghost_heads_private`, `test_tabext_01_fret_digits_private`, `test_unread_01_parentheses`. Their indices drop by one; every assertion is as strong as before and the reference comparisons are now direct (no `-2` offset).
