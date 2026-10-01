# OMIT-04 rolled-chord marks

The PDF-only path reads a repeated stack of short vertical filled curl paths
ending in a filled triangular arrow. The arrow tip determines the source roll
direction; the PDF's upward arrow maps to GPIF `Down`, as verified against the
independent reference reader. A candidate must lie in a notation or TAB staff,
inside one source bar, immediately left of exactly one multi-note source beat,
and span the notation chord when printed beside the notation staff. The
attached event cites the PDF page and drawing indices. An unattached candidate
gets a located reason in `arpeggios.json` and a ScoreIR warning. Paired
notation and TAB marks represent one roll and are counted once.

The writer emits only the reference GPIF form, `<Arpeggio>Down</Arpeggio>` or
`<Arpeggio>Up</Arpeggio>`. It adds no duration attribute or redundant property.
No ScoreIR or schema version changed; the existing `Event.arpeggio` field is
used.

## Source survey and comparison

All 30 mounted PDFs were inspected before changing recognition. The vector
candidate recognizer found 25 mark drawings across four PDFs: four in Lesson
3, two in Lesson 4, ten in Can't Find My Way Home, and nine in one other
source. The other 26 PDFs yielded zero candidates. Candidate
width was 4.00 PDF points; height ranged from 26.35 to 51.86 points. The
Lesson 3 and 4 notation marks had a 2.66 point gap to their chord heads.
An additional arrow-like drawing in that other source failed the continuous
curl-stack rule and was not attached; its musical role remains unverified.
The public negative control includes a slur, a diagonal glissando line and a
trill label beside the staff; none is recognized as an arpeggio. The public
marked-chord fixture also converts through the full PDF-only route to one
Arpeggio on its source beat; TAB-only and reversed-arrow fixtures exercise the
attachment seam and direction rule.

The independent GPIF beat reader reports Lesson 3 as 2 reference / 2 written,
Lesson 4 as 1 / 1, and Lessons 5–7 as 0 / 0. Can't Find My Way Home has five
reference beat occurrences and zero written: all five source candidates are
located but their destination beats are unavailable in the existing output.
This is a coverage refusal, not an arpeggio value inferred from the reference.
The ignored per-candidate reports are under `work/omit04/head/`.

Six before/after `Content/score.gpif` pairs are byte identical after deleting
only the newly added Arpeggio lines from the after copy. This checks earlier
duration, rest, fret, string, FreeText, layout and memory behavior in the
written GPIF. The actual before/after files remain under ignored `work/omit04/`.
