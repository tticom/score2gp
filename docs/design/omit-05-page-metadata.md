# OMIT-05 page-one metadata evidence

Geometry probe: PyMuPDF page-one `get_text("dict")`, line span font and maximum size, PDF-point bounding boxes. Source indices follow lexicographic PDF filename order in `fixtures/private`; source text is not stored. No reference GP values enter classification. `T` is the unique largest centered title candidate (size at least 17 pt, x-center within 8% of page width, top within 18% of page height); `C` is an explicit music-credit line in the same top band. Blank means no qualifying line. `lines` counts nonempty page-one lines; `blocks` counts text blocks. `bbox` is x0,y0,x1,y1, rounded to points. These measurements cover every mounted PDF, including pages with no selectable title.

| source index | page pt | blocks | lines | T font / size / bbox / block:line | C font / size / bbox / block:line |
|---:|---:|---:|---:|---|---|
| 1 | 901-1275 | 38 | 329 | TimesNewRomanPSMT / 37.8 / (224, 64, 677, 106) / 0:0 | - |
| 2 | 901-1275 | 39 | 174 | TimesNewRomanPSMT / 37.8 / (138, 64, 763, 106) / 0:0 | - |
| 3 | 612-792 | 52 | 172 | Baskerville / 22.4 / (244, 67, 369, 93) / 0:0 | - |
| 4 | 612-792 | 58 | 179 | Baskerville / 22.4 / (260, 59, 354, 85) / 0:0 | - |
| 5 | 612-792 | 59 | 163 | Baskerville / 22.0 / (249, 57, 365, 82) / 0:0 | - |
| 6 | 595-842 | 62 | 205 | Baskerville-Bold / 21.0 / (171, 28, 424, 53) / 0:0 | - |
| 7 | 612-792 | 44 | 190 | Baskerville / 22.4 / (208, 55, 408, 81) / 0:0 | - |
| 8 | 612-792 | 64 | 176 | Baskerville / 22.4 / (259, 47, 357, 73) / 0:0 | - |
| 9 | 595-842 | 86 | 352 | - (Bravura glyph excluded; 17.0 pt / (281, 90, 298, 112) / 5:0) | - |
| 10 | 595-842 | 59 | 159 | TimesNewRomanRegular / 22.9 / (241, 46, 350, 69) / 0:0 | - |
| 11 | 901-1275 | 19 | 124 | - | - |
| 12 | 595-842 | 35 | 100 | TimesNewRomanPSMT / 25.0 / (266, 43, 329, 70) / 0:0 | - |
| 13 | 524-680 | 1 | 0 | - | - |
| 14 | 612-792 | 50 | 111 | Baskerville / 22.4 / (247, 52, 368, 78) / 0:0 | - |
| 15 | 612-792 | 72 | 192 | Baskerville / 22.4 / (272, 51, 343, 77) / 0:0 | - |
| 16 | 609-842 | 1 | 0 | - | - |
| 17 | 595-842 | 23 | 74 | TimesNewRoman-0-50 / 25.0 / (121, 40, 476, 71) / 0:0 | - |
| 18 | 595-842 | 24 | 57 | - | - |
| 19 | 612-792 | 26 | 130 | TimesNewRomanPSMT / 25.0 / (195, 18, 417, 45) / 0:0 | TimesNewRomanPSMT / 10.0 / (491, 45, 575, 56) / 1:0 |
| 20 | 612-792 | 27 | 127 | TimesNewRomanPSMT / 25.0 / (194, 18, 418, 45) / 0:0 | TimesNewRomanPSMT / 10.0 / (491, 59, 575, 70) / 2:0 |
| 21 | 612-792 | 31 | 249 | TimesNewRomanPSMT / 25.0 / (133, 18, 479, 45) / 0:0 | TimesNewRomanPSMT / 10.0 / (491, 45, 575, 56) / 1:0 |
| 22 | 612-792 | 44 | 211 | TimesNewRomanPSMT / 25.0 / (140, 18, 472, 45) / 0:0 | - |
| 23 | 612-792 | 35 | 167 | TimesNewRomanPSMT / 25.0 / (236, 18, 376, 45) / 0:0 | TimesNewRomanPSMT / 10.0 / (491, 45, 575, 56) / 0:1 |
| 24 | 595-842 | 14 | 32 | - | - |
| 25 | 2480-3508 | 51 | 150 | Montserrat-Bold / 66.7 / (913, 177, 1567, 258) / 0:0 | - |
| 26 | 595-842 | 30 | 91 | TimesNewRomanPSMT / 25.0 / (192, 43, 403, 70) / 0:0 | - |
| 27 | 595-842 | 40 | 189 | TimesNewRomanPSMT / 25.0 / (192, 43, 403, 70) / 0:0 | - |
| 28 | 612-792 | 75 | 190 | Baskerville / 22.4 / (247, 54, 368, 80) / 0:0 | - |
| 29 | 595-842 | 48 | 115 | TimesNewRoman-0-50 / 25.0 / (33, 40, 563, 71) / 0:0 | - |
| 30 | 595-842 | 28 | 141 | TimesNewRoman-0-50 / 25.0 / (29, 40, 567, 71) / 0:0 | - |

## Classification and refusals

The measured lesson pages have one centered 25 pt title each. Four have a separate 10 pt explicit music-credit line at the right; one has no credit line. Across all 30 sources, the reader accepts 24 titles, 4 explicit music credits, and 2 copyright holder lines; it refuses 6, 26, and 28 respectively. No source caused a reader error. Other corpus pages contain centered subtitles or artist names without a music attribution, right-side transcription notices, page furniture, tempo marks, and section labels. The reader leaves Music empty unless an explicit `Music by` line is present. A tie between large centered title lines leaves Title empty. Missing or conflicting values emit a page-one located diagnostic; Copyright is copied from a unique non-boilerplate copyright-marked line, or from the centered line immediately above GP rights boilerplate in the same text block. These rules do not infer a composer from a subtitle or a filename.

## GP rights-line geometry

Across 30 page-one probes, three sources print the standard GP rights line. Indices 9 and 25 have a centered holder line immediately above it in the same text block, with 3 pt and 1 pt vertical gaps; both match the reference Copyright. Index 10 has a page-number line as its same-block predecessor, off center and vertically overlapping the rights line. It has no measurable holder, so the reader emits a located `pdf_copyright_ambiguous` and leaves Copyright empty. Its reference stores the boilerplate itself, which the task rule forbids returning. The 27 other sources have no accepted copyright line.

## GP page-template policy

The writer emits Guitar Pro 7 default Qt-rich-text page templates with ordered tokens `TITLE`, `SUBTITLE`, `ARTIST`, `ALBUM`, `WORDS&MUSIC` in FirstPageHeader and `page`, `pages` in FirstPageFooter and PageFooter. PageHeader is empty. Provenance is the app-created GP 7 page-layout shape inspected in the mounted reference files; their text values are never inputs to conversion. The independent oracle compares ordered tokens from parsed GPIF text without an extra HTML unescape, and separately rejects literal score title or music embedded in templates.

## Public fixture

`tests/fixtures/pdf/omit_05/engraved_title_credit.pdf` uses the existing public engraved notation and TAB page as its base. A large centered title, a smaller right-aligned music attribution, and a copyright footer were added with ordinary PDF text spans. The production CLI test copies it to a neutral path before conversion, then reads the final GPIF through the independent reader.

## Top-band secondary text geometry

The following inventory retains the smaller text lines from the top 18% of page one, where printed attribution and subtitles occur. Selection uses only font size (6 to 16 pt) and alphabetic characters, excluding music-symbol fonts. Entries give font, size, bbox, and block:line; no text is stored. This captures unlabeled credits that the conservative reader refuses.

| source index | candidate count | secondary lines (font / pt / bbox / block:line) |
|---:|---:|---|
| 1 | 3 | TimesNewRomanPSMT / 12.1 / (64, 133, 141, 147) / 1:0; TimesNewRomanPS-BoldMT / 15.1 / (94, 177, 134, 193) / 9:0; TimesNewRomanPS-BoldMT / 15.1 / (96, 198, 106, 215) / 10:0 |
| 2 | 9 | TimesNewRomanPSMT / 12.1 / (64, 133, 141, 147) / 1:0; TimesNewRomanPS-BoldMT / 15.1 / (84, 177, 125, 193) / 11:0; ArialMT / 10.6 / (88, 193, 255, 205) / 12:0; ArialMT / 10.6 / (88, 203, 263, 215) / 12:1; TimesNewRomanPSMT / 10.6 / (129, 218, 144, 229) / 13:0; TimesNewRomanPSMT / 10.6 / (278, 218, 292, 229) / 13:1 |
| 3 | 2 | Baskerville / 6.0 / (494, 132, 567, 139) / 1:0; Baskerville / 12.8 / (239, 99, 375, 114) / 4:0 |
| 4 | 2 | Baskerville / 6.0 / (494, 105, 572, 122) / 1:0; Baskerville / 12.8 / (239, 89, 375, 104) / 3:0 |
| 5 | 2 | Baskerville / 6.0 / (494, 120, 567, 127) / 1:0; Baskerville / 12.8 / (239, 88, 375, 103) / 4:0 |
| 6 | 8 | TimesNewRomanPSMT / 13.0 / (231, 53, 364, 67) / 1:0; TimesNewRomanPSMT / 6.0 / (430, 107, 434, 114) / 14:0; TimesNewRomanPSMT / 6.0 / (466, 107, 470, 114) / 14:1; TimesNewRomanPS-ItalicMT / 8.0 / (79, 102, 140, 111) / 14:2; TimesNewRomanPSMT / 10.0 / (66, 89, 92, 100) / 14:3; TimesNewRomanPSMT / 10.0 / (171, 89, 187, 100) / 14:4 |
| 7 | 2 | Baskerville / 6.0 / (494, 122, 567, 129) / 1:0; Baskerville / 12.8 / (239, 89, 375, 104) / 4:0 |
| 8 | 2 | Baskerville / 6.0 / (494, 105, 572, 118) / 1:0; Baskerville / 12.8 / (239, 77, 375, 92) / 3:0 |
| 9 | 15 | TimesNewRomanRegular / 8.0 / (44, 45, 68, 53) / 0:0; TimesNewRomanRegular / 8.0 / (16, 140, 24, 165) / 3:0; TimesNewRomanItalic / 6.0 / (114, 83, 120, 89) / 12:0; TimesNewRomanItalic / 6.0 / (173, 84, 179, 90) / 12:1; TimesNewRomanItalic / 6.0 / (288, 87, 294, 93) / 12:2; TimesNewRomanItalic / 6.0 / (386, 91, 391, 97) / 12:3 |
| 10 | 7 | TimesNewRomanRegular / 11.5 / (279, 70, 317, 82) / 1:0; TimesNewRomanBold / 11.5 / (269, 84, 330, 95) / 1:1; TimesNewRomanBold / 9.7 / (63, 116, 84, 125) / 21:1; TimesNewRomanBold / 9.7 / (63, 128, 78, 137) / 22:1; TimesNewRomanBold / 9.7 / (165, 128, 172, 137) / 22:2; TimesNewRomanBold / 9.7 / (323, 128, 331, 137) / 22:3 |
| 11 | 5 | TimesNewRomanPSMT / 12.1 / (64, 64, 141, 78) / 0:0; TimesNewRomanPSMT / 12.1 / (23, 160, 36, 194) / 3:0; TimesNewRomanPS-BoldMT / 15.1 / (84, 108, 173, 124) / 5:0; ArialMT / 10.6 / (88, 125, 255, 136) / 5:1; ArialMT / 10.6 / (88, 135, 270, 146) / 5:2 |
| 12 | 5 | TimesNewRomanPSMT / 12.0 / (246, 70, 349, 84) / 0:1; TimesNewRomanPS-BoldMT / 12.0 / (235, 84, 360, 97) / 0:2; TimesNewRomanPS-BoldMT / 10.0 / (249, 101, 255, 112) / 1:0; TimesNewRomanPS-BoldMT / 10.0 / (292, 101, 300, 112) / 1:1; TimesNewRomanPS-BoldMT / 10.0 / (336, 101, 344, 112) / 1:2 |
| 13 | 0 | none |
| 14 | 3 | Baskerville / 6.0 / (494, 105, 577, 123) / 1:0; Baskerville / 12.8 / (240, 83, 375, 98) / 3:0; Baskerville / 9.0 / (114, 142, 155, 152) / 7:0 |
| 15 | 2 | Baskerville / 6.0 / (494, 126, 567, 133) / 1:0; Baskerville / 12.8 / (239, 86, 375, 101) / 4:0 |
| 16 | 0 | none |
| 17 | 2 | TimesNewRoman-0-75 / 11.0 / (49, 89, 81, 102) / 5:0; Arial-0-75 / 9.0 / (63, 76, 108, 87) / 6:0 |
| 18 | 5 | Helvetica / 11.0 / (263, 50, 385, 65) / 2:0; Helvetica / 14.0 / (432, 12, 572, 33) / 3:0; Helvetica / 14.0 / (433, 26, 576, 48) / 4:0; Helvetica / 14.0 / (57, 60, 115, 80) / 5:0; Helvetica / 12.0 / (337, 80, 390, 103) / 8:0 |
| 19 | 4 | TimesNewRomanPSMT / 10.0 / (491, 45, 575, 56) / 1:0; TimesNewRomanPSMT / 8.0 / (51, 61, 102, 70) / 2:0; TimesNewRomanPSMT / 8.0 / (24, 131, 32, 153) / 5:0; Arial-BoldMT / 9.0 / (79, 92, 156, 102) / 7:0 |
| 20 | 3 | TimesNewRomanPSMT / 10.0 / (491, 59, 575, 70) / 2:0; TimesNewRomanPSMT / 8.0 / (51, 74, 102, 83) / 3:0; Arial-BoldMT / 9.0 / (83, 105, 162, 115) / 8:0 |
| 21 | 3 | TimesNewRomanPSMT / 10.0 / (491, 45, 575, 56) / 1:0; TimesNewRomanPSMT / 8.0 / (51, 61, 102, 70) / 2:0; Arial-BoldMT / 9.0 / (71, 92, 231, 102) / 9:0 |
| 22 | 3 | TimesNewRomanPSMT / 8.0 / (51, 50, 102, 59) / 1:0; TimesNewRomanPSMT / 8.0 / (24, 126, 32, 148) / 4:0; Arial-BoldMT / 9.0 / (71, 81, 274, 91) / 14:0 |
| 23 | 4 | TimesNewRomanPSMT / 10.0 / (491, 45, 575, 56) / 0:1; TimesNewRomanPSMT / 8.0 / (51, 61, 102, 70) / 1:0; TimesNewRomanPSMT / 8.0 / (24, 142, 32, 164) / 4:0; TimesNewRomanPS-BoldMT / 10.0 / (59, 92, 88, 103) / 9:0 |
| 24 | 6 | Type3 (15 0 R) / 10.1 / (138, 83, 189, 95) / 2:0; Type3 (15 0 R) / 10.1 / (392, 83, 461, 95) / 2:1; Type3 (19 0 R) / 10.1 / (46, 134, 124, 146) / 3:0; Type3 (23 0 R) / 8.6 / (515, 135, 536, 145) / 3:1; Times-Roman / 8.0 / (24, 17, 85, 24) / 12:0; Times-Roman / 8.0 / (244, 17, 442, 24) / 12:1 |
| 25 | 0 | none |
| 26 | 6 | TimesNewRomanPSMT / 12.0 / (263, 70, 332, 83) / 1:0; TimesNewRomanPSMT / 10.0 / (476, 83, 567, 95) / 2:0; TimesNewRomanPSMT / 8.0 / (470, 95, 567, 103) / 2:1; TimesNewRomanPSMT / 8.0 / (43, 108, 93, 117) / 3:0; TimesNewRomanPS-BoldMT / 15.0 / (60, 120, 124, 136) / 6:0; ArialMT / 10.0 / (184, 140, 357, 151) / 7:0 |
| 27 | 6 | TimesNewRomanPSMT / 12.0 / (263, 70, 332, 83) / 1:0; TimesNewRomanPSMT / 10.0 / (476, 83, 567, 95) / 2:0; TimesNewRomanPSMT / 8.0 / (470, 95, 567, 103) / 2:1; TimesNewRomanPSMT / 8.0 / (43, 108, 104, 117) / 3:0; TimesNewRomanPSMT / 8.0 / (51, 117, 65, 126) / 4:0; TimesNewRomanPSMT / 8.0 / (51, 127, 65, 136) / 4:1 |
| 28 | 2 | Baskerville / 6.0 / (494, 105, 572, 120) / 1:0; Baskerville / 12.8 / (239, 86, 375, 101) / 3:0 |
| 29 | 2 | TimesNewRoman-0-75 / 11.0 / (49, 89, 82, 102) / 3:0; Arial-0-75 / 9.0 / (63, 76, 108, 87) / 4:0 |
| 30 | 6 | TimesNewRoman-0-50 / 6.0 / (163, 100, 175, 108) / 6:0; TimesNewRoman-0-75 / 11.0 / (53, 89, 77, 102) / 6:1; TimesNewRoman-0-75 / 11.0 / (206, 89, 220, 102) / 6:2; TimesNewRoman-0-75 / 11.0 / (297, 89, 330, 102) / 6:3; Arial-0-75 / 9.0 / (63, 76, 108, 87) / 7:0; TimesNewRoman-0-50 / 6.0 / (163, 146, 175, 153) / 8:0 |
