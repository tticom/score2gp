# DUR-03: TAB staves drawn in broken segments

Task DUR-03 (REQ-0001), branch `feat/dur-03-tab-staff-detection`. Counts and codes only; no private musical content.

## Mechanism (measured)

`_detect_tab_systems` in `src/score2gp/pdf.py` builds TAB staves from the horizontal primitives that pass
`_LineSegment.is_horizontal` (at least 75 pt long), merges collinear ones, and needs five or six equally spaced
rows (`_tab_line_groups`). Two drawing styles defeat that:

1. **Lines broken around digits.** A staff that uses only its upper strings is drawn with those lines cut at every
   digit. The pieces are shorter than 75 pt, so the rows vanish before merging and fewer than five rows remain.
   Lesson 6: 34 TAB staves drawn, 10 accepted at the base, 22 dropped because fewer than five rows survive the
   filter, 2 dropped although five rows survive (a five-line classification case; Lesson 5 has 2 of those).
2. **A final bar narrower than 75 pt.** Every line of that bar is one piece of about 71-74 pt, so it is filtered
   out. The staff and its last barline stop one bar early, and the digits of that bar are
   `pdf_candidate_outside_system`, so the bar stays refused (`notation_note_without_tab_digit`). Lesson 4: 2 staves,
   Lesson 5: 3, Lesson 6: 1.

The assembler thresholds (`MATCH_SPACES`, `COLUMN_SPACES`) are not involved and are unchanged.

## Rules

- `_recovered_segmented_tab_groups` considers drawn pieces of 30 pt or more, merged, and accepts a six-line group only
  with three intact full-width lines (or five legacy rows) **and** a notation partner above it, and only when none of
  its rows is already a line of an accepted staff (otherwise alternate lines of two neighbouring staves, equally
  spaced, form a false six-line group). A recovered staff assigns a digit to a string only within 0.4 line spacing of
  a drawn line; between two lines the digit gets `pdf_string_assignment_between_lines` and no string.
- `_right_extended_tab_groups` extends an accepted TAB group (six lines, or the five of an incomplete candidate)
  only where every one of its own lines continues from its right edge to one common end and three of them do so as a
  single drawn piece. Line y coordinates are unchanged, and notation barlines are inherited with the bounds of the staff
  as drawn before the extension, so earlier barlines are never rejected by the new last bar.

## Not changed

Bars whose chords have tied heads that are not printed in the TAB (Lesson 5 bar index 17, Lesson 6 bar index 26) keep
the refusal `notehead_digit_count_mismatch`.
