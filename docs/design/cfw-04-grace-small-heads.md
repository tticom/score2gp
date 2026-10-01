# CFW-04 source measurements and reading rule

Measured with the vector note reader on the approved PDFs. Coordinates, sizes and counts below are ratios to each notation staff's own line spacing. The reference GP was used only after conversion to compare written output.

| Input | Recognised heads | Small heads | Stemmed, flagged small heads | Stemless small heads excluded | Outside-band curved stroke fragments excluded | Grace-to-beat gap, staff spaces |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Can't Find My Way Home | 276 | 16 | 8 | 8 | 8 | 1.50–2.746 |
| Just-Practice | 82 | 1 | 1 | 0 | 0 | 1.38 |
| Melodic Expressions, chapter 19 | 323 | 4 | 4 | 0 | 27 | 1.38–2.746 |
| EXACT System | 244 | 2 | 2 | 0 | 0 | 1.38 |

The narrow head width was 0.885 staff spaces in these four inputs. Ordinary heads were 1.18 spaces wide in each; Just-Practice and EXACT also have other, wider head forms. The small head height was 0.75 spaces. The eight excluded curved fragments in Can't Find My Way Home are seven at 1.067 spaces above the top staff line and one at 0.052 spaces below the bottom line. The 27 excluded fragments in Melodic Expressions are at 1.067 spaces outside the band. These are measured glyph-to-band distances, not artwork labels.

The reader classifies a notehead as small when its bounding width is under 1.0 staff space and height is under 0.85. A small head with a stem and one legible flag is a grace candidate. The next full note or chord in the same bar is its beat when the grace's right edge is within 0–3 staff spaces of that beat's left edge. A missing beat, a rest, a larger gap, an unflagged stem, a beam, a dot, or a tuplet keeps it unread. Multiple consecutive graces attach to the same following beat. The written grace is a 32nd, tagged `GraceNotes OnBeat` in GPIF, with zero metrical duration in ScoreIR. The existing ScoreIR grace field and schema already permit zero ticks, so this task does not change the IR contract version. The note-duration diagnostic contract moves from v0.4 to v0.5.

A small filled head without a stem is recorded by page, system, bar and bounding box as `small_notehead_without_stem`, and omitted from the beat count. A curved filled stroke wholly above or below the five-line band, thinner than 0.7 staff spaces, and not recognised as a notehead or rest is recorded at the same location as `stroke_fragment_outside_staff_band`. A possible note, rest, or other ambiguous mark remains an unread event. TAB digit matching and the four-quarter total remain required for any bar to be written.

## Source-only outputs without a reference GP

The full GPIF XML stayed byte-identical on Lessons 3–7, Gloria and Boring Scale against the archived base code. The other three PDFs changed only the bars listed below. Every listed bar has a four-quarter total, no unread notation event, and a TAB column match for every read note; the maximum horizontal notehead-to-digit offset is at most 0.108 staff spaces. The source has no reference GP for these inputs, so this is source consistency evidence rather than an external musical oracle. Other refused bars stay empty.

| Input | Changed one-based bars | Source evidence in those bars |
| --- | --- | --- |
| Just-Practice | 29 | 1 small flagged head, gap 1.38 spaces; 9 notation events and 9 TAB digits |
| Melodic Expressions, chapter 19 | 6, 21 | 2 small flagged heads in each; gaps 2.626/2.746 and 1.38/1.38 spaces; 8/8 and 7/8 notation events/TAB digits |
| Melodic Expressions, chapter 19 | 8, 9, 10, 11, 20 | 4, 8, 4, 8, 3 thin curved fragments outside the staff band; 8 notation events in each, with 20, 16, 24, 16, 12 TAB digits respectively |
| EXACT System | 46 | 2 small flagged heads, each gap 1.38 spaces; 6 notation events and 6 TAB digits |


