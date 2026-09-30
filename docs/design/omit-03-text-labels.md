# OMIT-03 PDF text labels

The PDF-only route reads each nonempty PyMuPDF text line. It classifies tempo,
music glyphs, technique marks, chord symbols, titles, credits, tuning notices,
page furniture, unsupported sizes, and text outside an annotation band before
accepting a free-text label. A line accepted as a label must be uniquely above
one staff, inside one source bar, and have a unique nearest source event by the
horizontal distance from the line's left edge to the event bounding-box centre.
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

Numbers are one-based bar and beat indices. Text equality was checked for
every position present in both files; no matching position differed in text.

| Source | Reference | Written | Missing reference positions | Extra positions |
| --- | ---: | ---: | --- | --- |
| Lesson 3 | 12 | 12 | none | none |
| Lesson 4 | 18 | 17 | 65:1 | none |
| Lesson 5 | 7 | 3 | 9:1, 17:1, 19:1, 37:1 | none |
| Lesson 6 | 26 | 1 | 1:1, 5:1, 7:1, 9:1, 14:1, 16:1, 20:1, 24:1, 29:1, 31:1, 33:1, 35:1, 37:1, 39:1, 41:1, 45:1, 47:1, 51:1, 53:1, 57:1, 59:1, 61:1, 65:1, 67:1, 69:1 | none |
| Lesson 7 | 25 | 0 | 1:2, 3:2, 5:2, 7:2, 9:2, 11:2, 13:2, 15:2, 17:2, 19:2, 21:2, 23:2, 25:2, 27:2, 29:2, 31:2, 33:2, 35:2, 37:2, 39:2, 41:2, 43:2, 45:2, 47:2, 49:2 | none |

The lesson 7 printed candidates at those positions contain chord and music
glyph syntax. The classifier refuses them as labels even though the reference
stores them as `FreeText`. This is an intentional source-role refusal pending
more precise chord handling. Other missing positions have no accepted source
line or cannot be placed by the current rule; their individual source reasons
remain in the ignored conversion sidecars.
In Lesson 6, 20 otherwise eligible lines receive `pdf_text_beat_unavailable`
because the source and written event counts disagree; one line is attached.

## Mounted corpus classification

Thirty PDFs were read without classification errors. The next table uses
lexicographic PDF source indices in `fixtures/private`; locations are
`page:block:line`. All nonempty lines were assigned one of the reason codes
in the summary. Accepted source locations are listed without private text.

| Reason code | Count |
| --- | ---: |
| `pdf_text_chord` | 208 |
| `pdf_text_font_size_unsupported` | 62 |
| `pdf_text_label` | 109 |
| `pdf_text_music_symbol` | 33 |
| `pdf_text_non_label_glyph` | 11913 |
| `pdf_text_outside_annotation_band` | 686 |
| `pdf_text_page_furniture` | 20 |
| `pdf_text_technique` | 1119 |
| `pdf_text_tempo` | 43 |
| `pdf_text_title_or_subtitle` | 141 |

| Source index | Accepted locations | Refusals by reason |
| ---: | --- | --- |
| 1 | none | `pdf_text_chord`=9, `pdf_text_non_label_glyph`=827, `pdf_text_outside_annotation_band`=12, `pdf_text_page_furniture`=1, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=2 |
| 2 | none | `pdf_text_non_label_glyph`=115, `pdf_text_outside_annotation_band`=28, `pdf_text_page_furniture`=1, `pdf_text_technique`=27, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=2 |
| 3 | none | `pdf_text_font_size_unsupported`=4, `pdf_text_non_label_glyph`=147, `pdf_text_outside_annotation_band`=11, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=9 |
| 4 | none | `pdf_text_font_size_unsupported`=2, `pdf_text_non_label_glyph`=202, `pdf_text_outside_annotation_band`=10, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=11 |
| 5 | none | `pdf_text_font_size_unsupported`=2, `pdf_text_non_label_glyph`=143, `pdf_text_outside_annotation_band`=8, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=9 |
| 6 | none | `pdf_text_chord`=30, `pdf_text_music_symbol`=5, `pdf_text_non_label_glyph`=295, `pdf_text_outside_annotation_band`=6, `pdf_text_technique`=50, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=1 |
| 7 | none | `pdf_text_font_size_unsupported`=11, `pdf_text_non_label_glyph`=240, `pdf_text_outside_annotation_band`=33, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=13 |
| 8 | none | `pdf_text_font_size_unsupported`=7, `pdf_text_non_label_glyph`=483, `pdf_text_outside_annotation_band`=47, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=29 |
| 9 | none | `pdf_text_chord`=2, `pdf_text_music_symbol`=12, `pdf_text_non_label_glyph`=497, `pdf_text_outside_annotation_band`=5, `pdf_text_page_furniture`=1, `pdf_text_technique`=101 |
| 10 | none | `pdf_text_chord`=10, `pdf_text_music_symbol`=2, `pdf_text_non_label_glyph`=139, `pdf_text_outside_annotation_band`=6, `pdf_text_page_furniture`=1, `pdf_text_title_or_subtitle`=1 |
| 11 | none | `pdf_text_non_label_glyph`=110, `pdf_text_outside_annotation_band`=12, `pdf_text_page_furniture`=1, `pdf_text_tempo`=1 |
| 12 | none | `pdf_text_chord`=13, `pdf_text_non_label_glyph`=79, `pdf_text_outside_annotation_band`=5, `pdf_text_page_furniture`=1, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=1 |
| 13 | none | none |
| 14 | none | `pdf_text_non_label_glyph`=92, `pdf_text_outside_annotation_band`=11, `pdf_text_title_or_subtitle`=8 |
| 15 | none | `pdf_text_font_size_unsupported`=9, `pdf_text_non_label_glyph`=216, `pdf_text_outside_annotation_band`=29, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=13 |
| 16 | none | none |
| 17 | none | `pdf_text_chord`=14, `pdf_text_non_label_glyph`=89, `pdf_text_outside_annotation_band`=7, `pdf_text_technique`=2, `pdf_text_title_or_subtitle`=1 |
| 18 | none | `pdf_text_chord`=1, `pdf_text_non_label_glyph`=15, `pdf_text_outside_annotation_band`=34, `pdf_text_technique`=1, `pdf_text_title_or_subtitle`=6 |
| 19 | 1:7:0, 1:9:0, 1:19:0, 1:25:0, 2:10:0, 2:14:0, 2:17:0, 2:30:0, 3:8:0, 3:18:0, 3:23:0, 4:7:0 | `pdf_text_non_label_glyph`=543, `pdf_text_outside_annotation_band`=1, `pdf_text_page_furniture`=2, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=1 |
| 20 | 1:8:0, 1:10:0, 1:22:0, 2:5:0, 2:15:0, 2:20:0, 2:23:0, 3:8:0, 3:19:0, 3:28:0, 3:36:0, 3:40:0, 4:2:0, 4:5:0, 4:9:1, 4:28:0, 5:8:0 | `pdf_text_non_label_glyph`=642, `pdf_text_outside_annotation_band`=2, `pdf_text_page_furniture`=2, `pdf_text_technique`=18, `pdf_text_tempo`=2, `pdf_text_title_or_subtitle`=1 |
| 21 | 1:9:0, 2:16:0, 2:30:0 | `pdf_text_non_label_glyph`=586, `pdf_text_outside_annotation_band`=1, `pdf_text_page_furniture`=2, `pdf_text_technique`=17, `pdf_text_tempo`=3, `pdf_text_title_or_subtitle`=1 |
| 22 | 1:14:0, 2:8:0, 2:19:0, 2:47:0, 2:58:0, 3:10:0, 3:26:0, 3:37:0, 3:47:0, 4:11:0, 4:26:0, 4:37:0, 4:51:0, 5:12:0, 5:34:0, 5:44:0, 5:54:0, 5:69:0, 6:10:0, 6:20:0, 6:24:0 | `pdf_text_non_label_glyph`=1111, `pdf_text_outside_annotation_band`=1, `pdf_text_page_furniture`=1, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=1 |
| 23 | none | `pdf_text_chord`=12, `pdf_text_music_symbol`=13, `pdf_text_non_label_glyph`=704, `pdf_text_outside_annotation_band`=1, `pdf_text_page_furniture`=2, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=1 |
| 24 | none | `pdf_text_non_label_glyph`=1, `pdf_text_outside_annotation_band`=30, `pdf_text_title_or_subtitle`=1 |
| 25 | none | `pdf_text_chord`=8, `pdf_text_non_label_glyph`=84, `pdf_text_page_furniture`=3, `pdf_text_technique`=42, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=12 |
| 26 | 1:7:0, 1:15:1, 1:20:0, 1:27:2, 2:53:1, 2:53:2, 2:74:1, 3:17:2, 3:19:0, 3:23:0, 3:27:0, 3:32:0, 4:14:0, 4:22:16, 5:12:1, 6:17:1, 6:30:0, 6:55:0, 6:55:1, 7:18:1, 7:32:0, 7:41:0, 9:6:2, 9:35:0, 11:8:0, 11:8:1, 11:17:0, 11:22:1, 11:25:0, 12:6:2, 12:6:3, 12:19:1, 13:26:7, 14:4:1, 14:23:1, 15:2:1, 16:15:1, 17:7:1, 17:7:2, 17:14:2, 17:14:3, 21:25:0, 25:10:0, 28:23:0, 28:26:0, 34:8:0 | `pdf_text_chord`=37, `pdf_text_font_size_unsupported`=20, `pdf_text_music_symbol`=1, `pdf_text_non_label_glyph`=3563, `pdf_text_outside_annotation_band`=324, `pdf_text_page_furniture`=1, `pdf_text_technique`=754, `pdf_text_tempo`=22, `pdf_text_title_or_subtitle`=1 |
| 27 | 1:14:1, 1:32:1, 2:32:1, 2:32:2, 2:43:0 | `pdf_text_non_label_glyph`=327, `pdf_text_outside_annotation_band`=18, `pdf_text_technique`=73, `pdf_text_tempo`=1, `pdf_text_title_or_subtitle`=1 |
| 28 | none | `pdf_text_font_size_unsupported`=6, `pdf_text_non_label_glyph`=232, `pdf_text_outside_annotation_band`=23, `pdf_text_page_furniture`=1, `pdf_text_title_or_subtitle`=13 |
| 29 | 1:14:0, 2:18:0, 2:23:0 | `pdf_text_chord`=38, `pdf_text_non_label_glyph`=241, `pdf_text_outside_annotation_band`=13, `pdf_text_technique`=30, `pdf_text_title_or_subtitle`=1 |
| 30 | 1:11:0, 1:22:0 | `pdf_text_chord`=34, `pdf_text_font_size_unsupported`=1, `pdf_text_non_label_glyph`=190, `pdf_text_outside_annotation_band`=8, `pdf_text_technique`=4, `pdf_text_title_or_subtitle`=1 |
