# CASCADE-01: refused bars that follow a refused bar (measurement; task blocked, no reader change)

Baseline `16414f9` (main after REFUSE-26). Normal CLI (`convert --pdf <approved-pdf> --pdf-only-tab`) over all 43 approved PDFs in `fixtures/private/`, Windows runtime, measured from scratch. Counts, codes and indices only. No file under `src/` or `tests/` changed, so after equals before: every inner `Content/score.gpif` is byte-identical and no source's written GPIF changed.

## Before (and after: nothing changed)

- Bars written: 1441. Bars refused: 210 (same totals as REFUSE-26). Exit codes: 38 x 0, 4 x 4, 1 x 2; those 5 sources are unfinished, not correct refusals.
- Refused bars by code: `note_duration_event_unread` 123, `notation_note_without_tab_digit` 50, `bar_without_notation_event` 11, `notehead_digit_count_mismatch` 11, `bar_total_mismatch` 6, `tie_head_ownership_unconfirmed` 2, `tab_system_digit_unassigned_to_bar` 2, `tab_digit_without_notation_event` 2, one each `duration_off_tick_grid`, `notation_tab_column_ambiguous`, `tab_chord_arrow_unread`.

## Cascade census (acceptance 1)

A bar is cascade-only when its own cause is `tie_stop_without_written_predecessor` and the bar before it (source order) is refused. Over the whole private set: **8 of 210 refused bars** (3 Black Dog, 4 Crossroads, 1 `Melodic_Expressions`). The other 202 are refused on their own evidence. All 8 are reader gaps (an unread root), never correct refusals.

| source | cascade bar (source index; page, system) | own cause | root bar and its code / cause |
|---|---|---|---|
| Black Dog | 2 (p0,s0), 3 (p0,s1), 4 (p0,s1) | `notation_note_without_tab_digit` / `tie_stop_without_written_predecessor`, event 0 | 1: `notation_note_without_tab_digit` / `no_tab_column_at_notation_event`, event 2 (14 events, 10 columns, 14 digits, `notation_has_extra`, digit recovery withheld `printed_technique_owner_unread`) |
| Crossroads | 6 (p0,s1) | same, event 0 | 5: `note_duration_event_unread` / `concurrent_events` |
| Crossroads | 7 (p0,s1) | same, event 0 | 6 (cascade of 5) |
| Crossroads | 26 (p2,s0) | same, event 0 | 25: `note_duration_event_unread` / `mixed_notehead_kinds` |
| Crossroads | 29 (p2,s0) | same, event 0 | 28: `note_duration_event_unread` / `tuplet_number_unassociated` |
| Melodic_Expressions | 132 (p11,s3) | same, event 0 | 131 (refused `notation_note_without_tab_digit`) |

Black Dog bars 2, 3 and 4 also each have more TAB digits than TAB columns (17/12, 13/9, 19/15), so a written predecessor alone would not settle them; they carry their own unread printed techniques. Crossroads bars 6/7 hang on a `concurrent_events` root, 26 on `mixed_notehead_kinds`, 29 on `tuplet_number_unassociated`: three different root classes.

## Root refusal in the design source (Black Dog source bar 1)

Located causes at the root, read from the page's vector drawing (no value invented):

- Event 2 and event 9 print no TAB digit. Each is the end of a small arc from the note before it (an `other_curved_form`, `over_or_under_notehead`, 1.49 x 0.56 staff spaces) and each of those notes carries a printed half-step bend label. The shallow-crescent tie reader does not take these arcs, so the event has no TAB column and the cause is `no_tab_column_at_notation_event`.
- Each bend is drawn as an upward shaft with an upward arrowhead followed by a downward shaft with a downward arrowhead (a bend and release). `notation_omr/bends.py` reads only a single labelled upward bend and deliberately excludes releases, so these four `rest_sized_curve` forms stay unread.
- Event 7 additionally has an unread curve beside a chord head (`accidental_beside_notehead`), beside a chord whose tie arcs own heads at ranks 0 and 2 only.

So the root bar has seven located unread forms: two tie arcs, four bend/release shaft and arrow pieces and one chord-side arc. Writing it correctly needs (a) a bend-and-release reading, (b) a representation and GPIF encoding of the release, (c) the arc-to-tie rule for a tie end on a bent note, and (d) the chord-side arc. None of the four can be checked against a reference: Black Dog has no readable reference file, and whether any other readable reference carries a bend-and-release was not checked. Not independently verified; the printed-page check was by eye on the rendered page.

## Holdout source (Crossroads): not applied

No root reader was finished, so the holdout was not tuned on and no reader was applied to it. The holdout's cascade bars (6, 7, 26, 29) hang on roots of three other classes (`concurrent_events`, `mixed_notehead_kinds`, `tuplet_number_unassociated`), none of which is the Black Dog root (bend and release with tied end). Even a finished Black Dog bend/release reader would therefore not write any Crossroads bar by the same mechanism. The gate needs at least one newly written holdout bar; there is none. The gate is not waived and no other source was substituted. All 8 cascade bars and the other 202 refused bars stay refused with located reasons.

## Outcome

Blocked, not complete. No `src/` or `tests/` change. No test was added: a test needs a rule whose removal it can detect, and no rule was written; synthetic tests would carry no acceptance weight. No named mutant exists.

Recommendation for the maintainer: the cascade is small (8 bars) and is downstream of roots of different classes; the cascade rule itself needs no code, because a written predecessor already lets a tie stop write (`tied_from`). The lever is the roots. The bend-and-release plus tied-end form in Black Dog is the only multi-bar chain with a single mechanism, and needs a design decision on release representation before any reader work.
