# OMIT-03 PDF text labels

The PDF-only route reads each nonempty PyMuPDF text line. It classifies tempo,
music glyphs, technique and dynamics marks, chord symbols, titles, credits, tuning notices,
page furniture, unsupported sizes, and text outside an annotation band before
accepting a free-text label. A line accepted as a label must be uniquely above
one staff, inside one source bar, and have a unique nearest source event by the
horizontal distance from the line's left edge to the event bounding-box centre.
Standalone bracketed timestamps are eligible only with the exact `m:ss`
shape, a supported non-music font, and the same staff-band and bar geometry
as alphabetic labels.
A nearest-event margin under two PDF points, a bar boundary within one point,
an unavailable source beat, or an occupied destination beat causes a refusal.
Rests are eligible source beats. The conversion report stores one located code
for every nonempty line and counts all codes. Unplaced labels also produce a
ScoreIR warning. Accepted beats retain the PDF page, system, bar and compact
text-line provenance; raw candidate lists are not copied into events.

This uses the PDF source alone. The existing GPIF writer serializes event text
as `FreeText`; no ScoreIR field or schema version changed. The independent
reader in `test_dur_02_oracle.py` checks the resulting GPIF beat positions.
The six source conversions at base `f14120b` and this branch produce identical
GPIF XML bytes after removing the added `FreeText` lines. The base copies and
head copies are under ignored `work/omit03/`.

## Reference comparison

The independent GPIF reader checks text equality at every common beat. The
private test pins the exact missing and extra position sets using SHA-256 digests
of sorted one-based `(bar, beat)` pairs, so private positions are not tracked.
The ignored per-position reason record is
`work/omit03/missing-exact-reasons.json`.

| Source | Reference | Written | Missing | Extra | Reason for every missing position |
| --- | ---: | ---: | ---: | ---: | --- |
| Lesson 3 | 12 | 12 | 0 | 0 | none |
| Lesson 4 | 18 | 17 | 1 | 0 | `pdf_text_outside_annotation_band` |
| Lesson 5 | 7 | 7 | 0 | 0 | none |
| Lesson 6 | 26 | 5 | 21 | 0 | `pdf_text_beat_unavailable` |
| Lesson 7 | 25 | 25 | 0 | 0 | none |

All 34 bare timestamp lines in Lessons 5-7 are now classified as source
labels. Four are placed in Lesson 5, four in Lesson 6, and 25 in Lesson 7;
the other Lesson 6 timestamp has a located beat-unavailable refusal.
The Lesson 6 refusals arise because all 21 destination bars have no written
events, including one timestamp and 20 alphabetic labels; no missing position
is attributed to a music glyph. The Lesson 4 line is 6.4 staff spaces above the staff. The
five-space annotation band is retained because a seven-space band would
admit 51 additional label-shaped corpus lines, whose roles are not yet
established. The existing bounded rule records that line as a located refusal.

## Mounted corpus classification

All 30 mounted PDFs were remeasured. There were 14,334 nonempty lines and
143 classifier-eligible labels, including 34 bare timestamps. The 34 timestamps have
staff gaps from 1.07 to 4.40 spaces. Zero tab digits, fret numbers, bar numbers,
page numbers, tempo marks, bar ranges or page footers were accepted as bare
timestamps. The exact bracketed `m:ss` grammar, supported font size, music-font
refusal and five-space label band jointly guard this case; punctuation alone
is never sufficient. The remaining 11,879 numeric and other non-label glyph
lines were refused as `pdf_text_non_label_glyph`.

| Reason code | Count |
| --- | ---: |
| `pdf_text_chord` | 208 |
| `pdf_text_font_size_unsupported` | 62 |
| `pdf_text_label` | 143 |
| `pdf_text_music_symbol` | 33 |
| `pdf_text_non_label_glyph` | 11,879 |
| `pdf_text_outside_annotation_band` | 657 |
| `pdf_text_page_furniture` | 20 |
| `pdf_text_technique` | 1,148 |
| `pdf_text_tempo` | 43 |
| `pdf_text_title_or_subtitle` | 141 |

A separate band probe found 51 label-shaped lines between five and seven
staff spaces above the staff across the corpus. The classifier's refusal is
retained pending a source-role rule that distinguishes them safely.
