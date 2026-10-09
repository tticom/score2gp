# TS-READ-01 printed time signature

`convert --pdf-only-tab` used to take the time signature from the caller
(`--time-signature`) and record every bar as `caller_declared`. The signature is
vector-drawn on the mounted sources, so `notation_omr/time_signature.py` reads it
from the painted contours the way OMIT-01 reads a key signature.

## Reader

* The search starts after the clef (found as in OMIT-01) and ends at the first
  notehead. A numeral must start within 3 staff spaces of the run of header
  glyphs that precedes it (clef, key accidentals); anything further is music.
* A numeral is a glyph inside one half of the staff (top half over the middle
  line, bottom half under it), 1.2 to 2.5 spaces tall and at most 2.4 spaces wide.
  The digits of one number touch or nearly touch (0.6 space); the first such run in
  each row is the number, later glyphs are left over and reported as ignored.
* A digit is classified from its painted form only, as fractions of its own box:
  enclosed counters (8 has two; 4, 6, 9 one), a full-height stem crossed by a flat
  bar (4, open or closed apex), a lone stem (1), a flat top bar (7), a flat base bar
  (2), and for 2, 3, 5 the ink in the lower-right and mid-left regions. A form that
  matches no rule, or only the weak side of one, is not read
  (`numeral_two_three_five_ambiguous`, `numeral_six_nine_ambiguous`, ...).
* Common time (an open C) and cut time (a C with a vertical stroke through it) are
  single contours centred on the middle line; they read as 4/4 and 2/2.
* Both rows must be present and centred on one another, the denominator must be a
  power of two up to 64 and the numerator 1 to 32. A glyph alone in one half staff
  is not a stacked signature: it is `absent`, with the glyph reported as ignored.
  Anything else with a candidate is `unreadable` with a located reason; it is
  never guessed.

## Rule

Per system, in `read_note_durations`:

1. A signature printed as text glyphs (the older reader) or as vector glyphs wins
   and stays in force for later systems until another is printed (`origin`:
   `system_start`, then `carried`).
2. A system with an unreadable candidate drops the carried signature: bars of that
   system use the declared value if one was given (`basis: caller_declared`, with
   the unread reason recorded), otherwise the route refuses with
   `pdf_only_tab_time_signature_unread`.
3. If both a printed and a declared value exist and differ, the bar check status is
   `signature_conflict` and the assembler refuses the bar with
   `time_signature_conflict`, detail `printed 12/8, declared 4/4`, located by page,
   system and bar. Nothing is chosen silently.

`note-duration-records.v0.6` adds `diagnostics.time_signatures` (one reading per
system) and `diagnostics.bar_time_signatures` (per bar: `basis`
`printed`/`caller_declared`, `origin`, `shape`, `declared`, `unread`).
`bar_checks[].time_signature_source` is `text_glyphs`, `vector_glyphs` or
`caller_declared`; the route records `time_signature_basis`.

## Not covered

* A signature change inside a bar line (after a barline mid-system) is not read.
* Notation set in a text font (clef and digits as font glyphs) has no vector clef to
  search from: `time_signature_clef_unread`, and the declared value is used as before.
* Real-source evidence exists for 4/4 and 12/8 (digits 1, 2, 4, 8) only. The other
  numerals, common time and cut time are exercised on synthetic shapes in
  `tests/test_ts_read_01_public.py`, which carry no acceptance weight.
