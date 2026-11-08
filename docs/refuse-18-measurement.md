# REFUSE-18 measurement: the largest remaining unread-duration class

Normal CLI (`convert --pdf-only-tab`) over every approved PDF (43 `*.pdf` in `fixtures/private/`), `main` at 064caee. Counts and codes only; a sample of every class was viewed on the printed page.

## Before

Bars written 1408. Refused 242: 120 `note_duration_event_unread`, 59 `notation_note_without_tab_digit`, 34 `bar_without_notation_event`, 11 `notehead_digit_count_mismatch`, 10 `bar_total_mismatch`, 2 `tie_head_ownership_unconfirmed`, 2 `tab_system_digit_unassigned_to_bar`, 2 `tab_digit_without_notation_event`, 1 `duration_off_tick_grid`, 1 `notation_tab_column_ambiguous`.

The 120 `note_duration_event_unread` bars by cause (the brief's 88 is stale; PERCX/TABEXT routed more TAB-only bars):

| bars | cause | kind | decision |
|---|---|---|---|
| 58 | `tab_column_without_rhythm_mark` (53 `7_Grateful_Dead_Melodies`, 5 `PARANOID`) | reader/representation gap: TAB prints no stem, beam, flag or dot | stays refused. Only spacing or count inference could settle it, which is not allowed |
| 18 | `rest_glyph_unidentified` | reader gap (none is a rest, see below) | **partly read** (see Change) |
| 15 | `unsupported_overlapping_form` | reader gap | refused, located |
| 11 | `symbol_unclassified` | reader gap | refused, located |
| 4+3+3+1+1+1 | `concurrent_events`, `mixed_notehead_kinds`, `filled_notehead_without_stem`, `unclassified_mark_below_strings`, `grace_note_beat_too_far`, `overlapping_tuplets` | reader gaps | refused, located |
| 2+2+1+1+1 | `tuplet_number_unassociated`, `parenthesized_head_unrepresented`, `rest_glyph_beside_note`, others | reader gaps | refused, located |

No class is a correct refusal; every one is a reader gap, a representation gap (no per-note notation for the printed mark) or unknown. Bars the evidence cannot settle stay refused and are reported as unfinished.

### What the 18 `rest_glyph_unidentified` glyphs are (shape class in brackets; all unread, none is a rest)

| bars | printed symbol | shape class |
|---|---|---|
| 4 | tall parenthesis pair around a stacked chord (a ghost chord) | rest_sized_curve / other_curved_form |
| 5 | single-head parenthesis whose left stroke abuts an arrow-accidental or a dotted head | narrow_curved_stroke |
| 3 | flat at a bar start | straight_form / other_curved_form |
| 3 | diamond note head | straight_form |
| 2 | meter digit | rest_sized_curve |
| 1 | piece of an accidental | rest_sized_curve |

## Change

`notation_omr/note_duration.py`: `_notehead_parentheses` already paired a left and right stroke around one head (REFUSE-14). A tall pair (above 1.25 and up to 6.5 staff spaces) that encloses two or more stacked heads of one event is now paired by `_chord_parentheses`: equal-height strokes of one measured form, the left abutting the chord's left edge (or a recognised accidental of one), the right abutting its right edge, every enclosed head owned by that pair only. When every head of the event is enclosed, the event is a ghost chord, exactly as a single enclosed head already is. No duration is guessed: the value still comes from the note shape. A bar the base reader already wrote keeps its un-ghosted notes (REFUSE-14 rule, unchanged).

## After

Bars written 1410 (+2). Refused 240: `note_duration_event_unread` 117 (-3), `notation_note_without_tab_digit` 60 (+1: a bar whose ghost chord now reads fails on a located tie predecessor instead), all other codes unchanged. Exit codes unchanged for all 43 PDFs. Inner `Content/score.gpif`: 42 of 43 sources byte-identical; the one changed is `Melodic_Expressions` (two bars written).

Newly written bars (`Melodic_Expressions`, source bars 358 and 576): no reference `.gp` exists, so each was checked against the printed page: a 2-head and a 3-head ghost chord, every head ghost-flagged, other events of the bar unchanged. **Not independently verified** (no reference). A 5-head hollow ghost chord in an already written bar was not changed.
