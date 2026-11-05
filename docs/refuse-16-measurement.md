# REFUSE-16 measurement: accidental and curved forms beside / over or under noteheads

Normal CLI (`convert --pdf-only-tab`) over every approved PDF (43 `*.pdf` in `fixtures/private/`), `main` at 3f07d4c. Counts and codes only.

Bars written 869 -> 871. Refused bars by code after (before in brackets where it moved):

| bars | code / cause | gap kind |
|---|---|---|
| 53 | note_duration_event_unread / tab_column_without_rhythm_mark | reader gap |
| 29 | bar_without_notation_event | reader gap |
| 11 | notehead_digit_count_mismatch | reader gap (8 carry hammer-on/pull-off arcs on chord pairs, one TAB digit for two heads: which head lacks its digit is not settled) |
| 10 | notation_note_without_tab_digit / tie_stop_without_written_predecessor | reader gap |
| 9 | notation_note_without_tab_digit / no_tab_column_at_notation_event | reader gap |
| 9 -> 8 | note_duration_event_unread / unsupported_overlapping_form | see below |
| 6 | symbol_unclassified | unknown |
| 4 / 3 | bar_total_mismatch, mixed_percussive_tie_ownership_unread, concurrent_events | unknown / representation gap |
| 4 -> 3 | rest_glyph_unidentified (the glyph of Derek bar 2 was an accidental in ghost parentheses; that bar now refuses for its tie onto a grace) | reader gap |

## The nine `unsupported_overlapping_form` bars (6 sources), per form on the printed page

| bars | printed form | result |
|---|---|---|
| 1 (Pride and Joy 4) | flat set at grace size left of a grace head | read: written |
| 1 (Derek Trucks 13) | natural inside the parentheses of a ghost head | read: written, equals reference (only a zero-duration dot tag on a grace differs, as the reference tags graces) |
| 1 (Derek Trucks 2) | same form, plus a printed tie from a quarter onto the next grace note (the reference carries the tie) | accidental read, but the reader does not carry ties onto graces: the arc is now located (`over_or_under_notehead`) and the bar stays refused, unfinished (reader gap) |
| 2 (Derek Trucks 4, 6) | grace-size flat whose size does not fit the head-derived scale; slide line and slur | reader gap, stays refused (unfinished) |
| 2 (Derek Trucks 5, 15) | arc under a grace group (grace slur) | reader gap, stays refused |
| 1 (Pride and Joy 5) and 2 (Castles Made of Sand 2, 3) | bend arrows ("Full") | representation gap for the pdf route: needs `Note.techniques` bend points filled by the reader (IR/GPIF already carry a bend technique) |
| 1 (Can't Find My Way Home 6) | rolled-chord wave with arrow | reader gap (REFUSE-07 wave column plus arrow) |

The 8 digit-count-mismatch bars REFUSE-15 attributed to "unread accidental forms" in fact carry H/P arcs between chord pairs: no rule added, still refused.

## Change

1. A sharp/flat/natural left of a small (grace) head is judged at that staff's own grace-head scale (small head width over median full head width).
2. An arc joining a note and an adjacent grace head at one staff position is located as an unread overlap (no silent drop), which keeps Derek bar 2 refused.
3. A ghost head's left parenthesis may abut the head's own recognised accidental.
The accidental never sets string or fret (TAB digit stays authoritative).
