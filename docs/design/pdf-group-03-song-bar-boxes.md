# Songbook bar-box investigation

No recognition or gate change is proposed. Measurements show that the shared layout refusal is not a common short-barline failure. Correcting it for these sources requires distinguishing inherited stems from barlines, repeat primitive provenance, and notation from TAB. These are semantic recognition problems, not a scale adjustment. A scale-only overhang repair would leave missing first bars and false internal boundaries.

The PDF-GROUP-01 close-out already identified the partner-inheritance boundary restriction as a stop condition. Here it recurs alongside newly located false-positive boundaries. The current applicable stop is `gate_requires_changing_meaning_not_scale` (PDF-GROUP-01 used `second_gate_requires_changing_meaning_not_scale`); no claim is made that every possible recognition rule has been disproved.

## Measurement definitions

`ss` is the median adjacent detected TAB-row spacing. `ns` is the median adjacent row spacing of the notation partner actually passed to the production filter. Systems are detector results, not an assertion of correct source systems. In particular Black Dog has a false detected system. Stroke indices are zero-based within `barline_candidates_details`; inherited entries are another filter observation of the same primitive, so totals are observations, not unique physical strokes. A detail marked accepted need not survive the later 15 pt boundary collapse; system boundary counts are the retained result. Warning instances and candidate observations are different counting units. Counts and distances only are retained; no musical events or rendered pages are included.

The measurement uses the ordinary `_detect_tab_systems` path, with a read-only wrapper around `filter_tab_barline_candidates` to record its actual staff arguments. Conversion is through `python -m score2gp.cli convert --pdf <private PDF> --pdf-only-tab --time-signature 4/4 --out <repo>/work/<run>/output.gp --work-dir <repo>/work/<run>/work --json-report <repo>/work/<run>/report.json`; no reference, sidecar, remediation or gate bypass. Detailed per-stroke measurements and commands are in the launcher evidence files.

## Producers and spacings

| Source | Producer | Pages | Detected systems | ss (pt) | ns (pt) |
|---|---|---:|---:|---|---|
| Back In Black | Mac OS X 10.10.3 Quartz PDFContext | 1 | 4 | 6.0 | 4.0 |
| Black Dog | Mac OS X 10.10.3 Quartz PDFContext | 2 | 6 | 4.0, 6.0 | 4.0 |
| Brown Sugar | Mac OS X 10.10.3 Quartz PDFContext | 1 | 4 | 6.0 | 4.0 |
| Castles Made of Sand | Mac OS X 10.10.3 Quartz PDFContext | 2 | 6 | 6.0 | 4.0 |
| Crossroads | Mac OS X 10.10.3 Quartz PDFContext | 3 | 15 | 6.0 | 4.0 |
| Ex 2 Hands Up | Qt 5.15.3 | 1 | 3 | 5.625 | 3.75 |
| Heartbreaker | Mac OS X 10.10.3 Quartz PDFContext | 1 | 3 | 6.0 | 4.0 |
| Hey Joe | Mac OS X 10.10.3 Quartz PDFContext | 2 | 6 | 6.0 | 4.0 |
| Pride and Joy | Mac OS X 10.10.3 Quartz PDFContext | 2 | 6 | 6.0 | 4.0 |
| Lesson-3 | macOS Version 14.1 (Build 23B74) Quartz PDFContext | 4 | 23 | 6.378 | 4.252 |
| Lesson-4 | macOS Version 14.1 (Build 23B74) Quartz PDFContext | 5 | 29 | 6.378 | 4.252 |
| Lesson-5 | macOS Version 14.1 (Build 23B74) Quartz PDFContext | 3 | 14 | 6.378 | 4.252 |
| Lesson-6 | macOS Version 14.1 (Build 23B74) Quartz PDFContext | 6 | 34 | 6.378 | 4.252 |
| Lesson-7 | macOS Version 14.1 (Build 23B74) Quartz PDFContext | 5 | 25 | 6.378 | 4.252 |
| Melodic Soloing Masterclass | macOS Version 12.5 (Build 21G72) Quartz PDFContext | 1 | 3 | 26.575 | 17.7165 |

The eight Quartz song sources use 6 pt TAB spacing and 4 pt notation spacing; Black Dog additionally contains a false 4 pt TAB-spacing detection. Ex 2 Hands Up uses 5.625/3.75 pt. Lessons 3–7 use 6.378/4.252 pt; Masterclass uses 26.575/17.7165 pt. Producer labels support a different export path, not proof of an engraver identity.

## Located blockers

| Source | Location and geometry | State |
|---|---|---|
| Back In Black | p1/s4: right boundary is 0.5667 ss past the drawn staff. p1/s1: first accepted boundary is 32.0649 ss after detected start. p1/s2 also retains an inherited stem. | Refused |
| Black Dog | p1/s3 and s5: zero accepted boundaries despite 3 and 2 raw full-height 13.1667 ss strokes; all are vetoed as multi-topology ownership. p1/s4: a notation-region detection at approximately 4 pt spacing retains 23 verticals, with 21 of 22 widths below 30 pt. p2/s1: 0.5667 ss final overhang. True left systemic strokes at −3.7833 and −2.1167 ss are also discarded. | Refused |
| Brown Sugar | p1/s4: 0.5667 ss final overhang; true left systemic strokes at −3.7833/−2.1167 ss fail horizontal bounds and inheritance. | Refused |
| Castles Made of Sand | p1/s3 widths 3.9232/4.9040 ss; p2/s1 widths 4.3300/4.5325 ss fail the 30 pt minimum. p2/s2 overhang 0.5667 ss. True left strokes at −3.7500 ss are excluded. | Refused |
| Crossroads | p1/s1 has one boundary, at 14.5925 ss from the start. A notation stroke 2.9432 ss from it is rejected by inheritance distance. Additional narrow boxes: p1/s3, p2/s2, p3/s5; final 0.5667 ss overhang. | Refused |
| Ex 2 Hands Up | p1/s2 widths 4.6737 and 3.6997 ss (26.290/20.811 pt) fail the 30 pt minimum. Seven final inherited boundaries are stems; true repeat clusters are rejected by primitive provenance. | Refused |
| Heartbreaker | p1/s2 has zero boundaries despite 5 raw full-height 13.1667 ss strokes, all vetoed as multi-topology ownership; p1/s3 overhang 0.5667 ss. Left full-height strokes −3.7833/−2.1167 ss fail bounds. | Refused |
| Hey Joe | p2/s2 final boundary overhang 0.5667 ss. p1/s1 first retained boundary lies 18.7243 ss from start, omitting the first source interval. | Refused |
| Pride and Joy | p2/s2 final boundary overhang 0.5667 ss; p1/s1 first retained boundary lies 25.3685 ss from start. | Refused |

All nine refuse globally at `layout-gating`, category `pdf_only_tab_grouping_unsafe`, detail `pdf_bar_box_construction_not_enough_for_build_ir`. They write zero bars. A per-bar refused count does not exist because the bar assembler is never reached; it is not zero and is not inferred from detected boxes. Before/after code changes: none. No correctness claim is made for the eight without a reference.

## Why a scale-only patch would be unsafe

The Quartz final pair has a thin full-height 0.6 pt stroke at the staff end and a 2.4 pt thick stroke 3.4 pt (0.5667 ss) beyond it. The selected thick boundary fails the 2 pt box-bound check. Taking the thin boundary could repair that local overhang, but does not recover first bars or remove inherited stems. This repeats PDF-GROUP-01 C1 rather than establishing a new short-stroke rule. The Quartz line observations have butt caps (0); Qt repeat/bar rectangles are filled, with no line-cap value. Caps do not explain the located stem and provenance failures.

The systemic left stroke is genuinely continuous across notation and TAB, commonly 13.1667 ss tall. It is not a set of short pieces needing a join. Several left strokes are 2.1167–3.7833 ss left of the detector start; the 8 pt candidate margin drops them, and partner inheritance excludes boundaries outside the current TAB-boundary interval. Increasing the margin alone does not repair the second gate. Reinterpreting that interval would repeat PDF-GROUP-01 C2’s stop.

Ex 2 Hands Up draws genuine TAB barlines as 5 ss rectangles and separate notation barlines as 2.6667 ss rectangles. Joining across the staff gap would be wrong. Repeat clusters have more than two rectangle edges from different primitives: the provenance gate rejects them even though they cross all string gaps. A length tolerance cannot repair primitive identity.

The seven false final stem boundaries below were verified against the page rendering. The endpoint classifier returns `barline` because `_has_attached_notehead` is false for each. Their width is 0.0800 ss, compared with 0.1067 ss for the TAB reference barline. The thickness ratio is 0.75, but the classifier returns before using it when no vector notehead contact is found. Reading the text-font notehead evidence, or changing this classification policy, is a recognition/meaning change. Lowering the narrow-box check would admit the false intervals.

| Ex 2 location | Stem index | x from system left (ss) | Length (ss) | Width (ss) | Endpoint contact |
|---|---:|---:|---:|---:|---|
| p1/s1 | 64 | 19.5260 | 4.5577 | 0.0800 | false |
| p1/s1 | 72 | 42.3736 | 3.8377 | 0.0800 | false |
| p1/s1 | 77 | 57.7334 | 4.4512 | 0.0800 | false |
| p1/s2 | 49 | 4.6737 | 3.7924 | 0.0800 | false |
| p1/s2 | 51 | 10.5558 | 4.1257 | 0.0800 | false |
| p1/s2 | 56 | 25.9226 | 4.6169 | 0.0800 | false |
| p1/s2 | 60 | 57.8349 | 4.4510 | 0.0800 | false |

The source has 11 bars by visual counting; current detected adjacent boxes are 7+7+3=17. This count is diagnostic only. Grouping never passes, so no later refusal or written-bar oracle comparison exists. The reference is not used to infer boundaries or repair values.

A read-only return-frame trace of `_detect_tab_systems` additionally located raw full-height strokes excluded before the six diagnostics. Black Dog p1/s3 has three (left offsets −2.1167, 38.4834, 78.9824 ss), p1/s5 has two (−2.1167, 78.9824 ss), and Heartbreaker p1/s2 has five (−2.1167, 30.2344, 50.8873, 59.7044, 78.9824 ss). All are 13.1667 ss tall and receive `primitive_to_system=None` because they overlap multiple discovered topologies. The safety guard is preventing cross-system ownership on a mistaken topology; bypassing it would weaken the no-join guarantee. Missing boundaries here are not shortened source strokes.

## Interpreting the six diagnostics

| Diagnostic (prefix `pdf_`) | What is measured | Right or wrong |
|---|---|---|
| barline_too_short | Legacy aggregate increments for *any rejected* observation shorter than 40 pt, including valid-staff-height strokes rejected for another reason; some primary short-height failures increment twice. | Not a primary geometric verdict. Cannot label all its observations non-barlines. |
| barline_does_not_cross_staff | Aggregate alias of the next three staff-crossing codes. | Must inspect the primary code and whether this is the TAB or notation pass. |
| barline_partial_staff_crossing | Intersects the tested staff, crosses many but not all gaps. | Correct for measured short stems; unresolved for uninspected observations. Does not establish a true barline discarded. |
| barline_crosses_insufficient_string_gaps | Fewer than the required tested-staff gaps. | Correct for measured stems that fail to span the tested staff; lowering it would admit them. |
| barline_outside_staff_region | No intersection with the staff under test. | Correct for notation-only barlines in the TAB pass; they are reconsidered in the notation pass. Correct for detached stems/decorations. |
| barline_outside_system_bounds | Candidate beyond the x margin, or notation inheritance beyond the existing accepted interval. | Wrong for the located full-height left systemic strokes. Right when a stem belongs outside the existing bar interval. Also duplicated notation endpoints are already represented by accepted TAB strokes. |

Some true repeat strokes are wrongly excluded by `pdf_barline_mixed_primitive_provenance`, which is absent from the six leads. Some stems are wrongly accepted. Counts of rejections alone cannot discriminate the nine from the lessons. A complete semantic identification of every discarded stroke is unproven; unresolved observations stay refused, not declared correct.

## Per-system measurements

`T/N` counts are TAB/notation filter observations. Lengths are min–max in ss across all observations; detailed individual lengths, indices, widths, caps and rejection codes are in launcher `geometry.json` and `strokes.md`. `O/I/P/R/H` count primary outside-system / insufficient-gaps / partial-crossing / outside-region / short-height codes. `S/D` are legacy too-short / does-not-cross aggregate counters. No observation is counted twice within a primary-code column; inherited observations can repeat physical strokes.

| Source | p/s | ss/ns (pt) | T/N | Length range (ss) | Boundaries / boxes | O/I/P/R/H | S/D |
|---|---|---|---|---|---|---|---|
| Back In Black | 1/1 | 6.0/4.0 | 29/28 | 2.1500–13.1667 | 2 / 1 | 2/6/4/27/5 | 51/37 |
| Back In Black | 1/2 | 6.0/4.0 | 33/33 | 2.1500–13.2282 | 3 / 2 | 2/15/4/31/0 | 55/50 |
| Back In Black | 1/3 | 6.0/4.0 | 29/29 | 2.1222–13.1667 | 3 / 2 | 4/7/5/27/6 | 52/39 |
| Back In Black | 1/4 | 6.0/4.0 | 39/39 | 2.0852–13.2530 | 4 / 3 | 1/7/3/36/0 | 68/46 |
| Black Dog | 1/1 | 6.0/4.0 | 32/32 | 2.1302–14.6450 | 4 / 3 | 5/16/1/28/0 | 46/45 |
| Black Dog | 1/2 | 6.0/4.0 | 29/29 | 2.1578–14.9795 | 3 / 2 | 5/11/2/26/1 | 40/39 |
| Black Dog | 1/3 | 6.0/4.0 | 28/28 | 2.0968–4.1667 | 0 / 0 | 0/21/3/28/2 | 56/52 |
| Black Dog | 1/4 | 4.0/4.0 | 31/0 | 3.9990–6.5795 | 23 / 22 | 0/4/4/0/0 | 8/8 |
| Black Dog | 1/5 | 6.0/4.0 | 0/0 | none | 0 / 0 | 0/0/0/0/0 | 0/0 |
| Black Dog | 2/1 | 6.0/4.0 | 24/22 | 2.5667–13.1667 | 2 / 1 | 2/0/8/20/0 | 28/28 |
| Brown Sugar | 1/1 | 6.0/4.0 | 28/28 | 2.1500–13.1667 | 4 / 3 | 4/11/3/23/2 | 41/37 |
| Brown Sugar | 1/2 | 6.0/4.0 | 30/30 | 2.0940–13.1667 | 2 / 1 | 5/5/11/27/4 | 51/43 |
| Brown Sugar | 1/3 | 6.0/4.0 | 35/35 | 2.1623–13.1667 | 4 / 3 | 6/17/3/32/1 | 55/52 |
| Brown Sugar | 1/4 | 6.0/4.0 | 16/16 | 2.1645–13.1667 | 2 / 1 | 4/8/2/12/1 | 24/22 |
| Castles Made of Sand | 1/1 | 6.0/4.0 | 31/31 | 2.1127–13.1667 | 3 / 2 | 5/8/6/29/2 | 50/43 |
| Castles Made of Sand | 1/2 | 6.0/4.0 | 32/31 | 1.8333–13.9682 | 4 / 3 | 6/13/7/28/1 | 50/48 |
| Castles Made of Sand | 1/3 | 6.0/4.0 | 25/25 | 2.2357–13.1667 | 5 / 4 | 2/1/2/23/0 | 26/26 |
| Castles Made of Sand | 1/4 | 6.0/4.0 | 33/33 | 2.1657–13.1667 | 2 / 1 | 4/19/6/30/0 | 56/55 |
| Castles Made of Sand | 2/1 | 6.0/4.0 | 32/32 | 2.1642–14.9680 | 4 / 3 | 7/14/8/29/0 | 48/51 |
| Castles Made of Sand | 2/2 | 6.0/4.0 | 25/23 | 2.5000–13.1667 | 3 / 2 | 13/11/0/20/0 | 31/31 |
| Crossroads | 1/1 | 6.0/4.0 | 3/3 | 2.5667–14.9795 | 1 / 0 | 2/0/0/1/0 | 2/1 |
| Crossroads | 1/2 | 6.0/4.0 | 17/17 | 2.1643–14.9795 | 3 / 2 | 2/7/5/14/0 | 25/26 |
| Crossroads | 1/3 | 6.0/4.0 | 29/29 | 2.1500–13.8962 | 5 / 4 | 2/15/7/25/0 | 46/47 |
| Crossroads | 1/4 | 6.0/4.0 | 33/33 | 2.1027–13.1667 | 3 / 2 | 2/9/14/30/4 | 62/53 |
| Crossroads | 1/5 | 6.0/4.0 | 29/28 | 2.1500–13.1667 | 4 / 3 | 2/9/8/25/4 | 50/42 |
| Crossroads | 2/1 | 6.0/4.0 | 30/28 | 2.1575–13.9680 | 4 / 3 | 5/10/5/27/3 | 48/42 |
| Crossroads | 2/2 | 6.0/4.0 | 26/26 | 2.1500–13.1667 | 6 / 5 | 2/10/2/24/2 | 40/36 |
| Crossroads | 2/3 | 6.0/4.0 | 26/26 | 2.1623–13.1667 | 2 / 1 | 2/13/4/24/4 | 49/41 |
| Crossroads | 2/4 | 6.0/4.0 | 29/29 | 2.1295–13.5198 | 2 / 1 | 2/20/2/27/1 | 51/49 |
| Crossroads | 2/5 | 6.0/4.0 | 28/28 | 2.1500–14.1347 | 3 / 2 | 2/12/6/25/2 | 46/43 |
| Crossroads | 3/1 | 6.0/4.0 | 31/30 | 2.1647–13.5013 | 4 / 3 | 2/25/2/26/0 | 53/53 |
| Crossroads | 3/2 | 6.0/4.0 | 32/32 | 2.1500–13.1667 | 2 / 1 | 2/17/9/30/2 | 60/56 |
| Crossroads | 3/3 | 6.0/4.0 | 23/23 | 2.1667–14.9795 | 2 / 1 | 4/19/0/21/0 | 39/40 |
| Crossroads | 3/4 | 6.0/4.0 | 29/29 | 2.1025–13.1667 | 3 / 2 | 2/15/4/27/2 | 50/46 |
| Crossroads | 3/5 | 6.0/4.0 | 17/15 | 2.1645–13.4670 | 4 / 3 | 0/4/6/14/0 | 24/24 |
| Ex 2 Hands Up | 1/1 | 5.625/3.75 | 50/41 | 1.7844–11.5724 | 8 / 7 | 2/9/5/40/3 | 73/54 |
| Ex 2 Hands Up | 1/2 | 5.625/3.75 | 41/33 | 1.7842–11.8402 | 8 / 7 | 2/12/2/32/0 | 57/46 |
| Ex 2 Hands Up | 1/3 | 5.625/3.75 | 17/12 | 2.1577–12.8140 | 4 / 3 | 2/6/0/11/0 | 21/17 |
| Heartbreaker | 1/1 | 6.0/4.0 | 33/33 | 2.1413–13.1667 | 2 / 1 | 4/18/7/30/3 | 61/55 |
| Heartbreaker | 1/2 | 6.0/4.0 | 0/0 | none | 0 / 0 | 0/0/0/0/0 | 0/0 |
| Heartbreaker | 1/3 | 6.0/4.0 | 9/9 | 2.1250–14.1667 | 2 / 1 | 4/2/2/5/0 | 9/9 |
| Hey Joe | 1/1 | 6.0/4.0 | 31/31 | 2.1630–14.1348 | 3 / 2 | 3/10/6/28/4 | 51/44 |
| Hey Joe | 1/2 | 6.0/4.0 | 29/29 | 2.1108–14.1348 | 4 / 3 | 4/19/2/26/0 | 46/47 |
| Hey Joe | 1/3 | 6.0/4.0 | 19/19 | 2.1500–6.2167 | 3 / 2 | 0/6/4/19/2 | 33/29 |
| Hey Joe | 1/4 | 6.0/4.0 | 13/13 | 2.1657–13.2573 | 3 / 2 | 0/4/2/12/0 | 18/18 |
| Hey Joe | 2/1 | 6.0/4.0 | 29/29 | 2.6670–14.3015 | 2 / 1 | 0/10/10/28/0 | 48/48 |
| Hey Joe | 2/2 | 6.0/4.0 | 23/23 | 2.1637–13.1667 | 2 / 1 | 0/2/3/21/1 | 28/26 |
| Pride and Joy | 1/1 | 6.0/4.0 | 19/18 | 2.0000–13.1667 | 3 / 2 | 2/14/1/16/0 | 31/31 |
| Pride and Joy | 1/2 | 6.0/4.0 | 23/22 | 2.1387–13.1667 | 2 / 1 | 3/7/4/21/4 | 40/32 |
| Pride and Joy | 1/3 | 6.0/4.0 | 28/28 | 2.0992–13.1667 | 4 / 3 | 2/14/4/26/1 | 46/44 |
| Pride and Joy | 1/4 | 6.0/4.0 | 32/31 | 2.0000–14.9682 | 5 / 4 | 4/7/6/29/5 | 52/42 |
| Pride and Joy | 2/1 | 6.0/4.0 | 27/27 | 2.1248–13.1667 | 2 / 1 | 3/2/1/25/5 | 38/28 |
| Pride and Joy | 2/2 | 6.0/4.0 | 16/15 | 1.8333–13.1667 | 2 / 1 | 2/8/3/12/1 | 25/23 |
| Lesson-3 | 1/1 | 6.378/4.252 | 25/21 | 1.9752–10.9125 | 4 / 3 | 2/3/6/20/0 | 33/29 |
| Lesson-3 | 1/2 | 6.378/4.252 | 22/19 | 1.9828–10.3333 | 3 / 2 | 2/4/6/19/0 | 29/29 |
| Lesson-3 | 1/3 | 6.378/4.252 | 21/18 | 1.9570–10.9124 | 3 / 2 | 2/9/3/17/0 | 33/29 |
| Lesson-3 | 1/4 | 6.378/4.252 | 30/27 | 1.8435–10.9124 | 4 / 3 | 2/6/6/26/0 | 38/38 |
| Lesson-3 | 1/5 | 6.378/4.252 | 25/21 | 2.2114–10.9122 | 4 / 3 | 2/7/4/20/0 | 33/31 |
| Lesson-3 | 1/6 | 6.378/4.252 | 18/16 | 1.7507–10.3332 | 3 / 2 | 2/6/5/15/0 | 26/26 |
| Lesson-3 | 2/1 | 6.378/4.252 | 30/26 | 1.9712–10.9124 | 4 / 3 | 2/7/7/25/0 | 43/39 |
| Lesson-3 | 2/2 | 6.378/4.252 | 35/31 | 1.6235–10.9125 | 5 / 4 | 2/12/8/30/0 | 52/50 |
| Lesson-3 | 2/3 | 6.378/4.252 | 27/23 | 1.6408–11.8084 | 4 / 3 | 2/8/6/22/0 | 38/36 |
| Lesson-3 | 2/4 | 6.378/4.252 | 25/21 | 1.9873–10.3333 | 4 / 3 | 2/2/5/20/0 | 31/27 |
| Lesson-3 | 2/5 | 6.378/4.252 | 31/28 | 1.9675–10.3332 | 4 / 3 | 2/8/8/27/0 | 43/43 |
| Lesson-3 | 2/6 | 6.378/4.252 | 30/26 | 1.9712–10.7847 | 4 / 3 | 2/9/7/25/0 | 43/41 |
| Lesson-3 | 2/7 | 6.378/4.252 | 30/27 | 1.8435–10.7877 | 4 / 3 | 2/8/7/26/0 | 41/41 |
| Lesson-3 | 3/1 | 6.378/4.252 | 25/21 | 1.9755–10.3332 | 4 / 3 | 2/6/4/20/0 | 32/30 |
| Lesson-3 | 3/2 | 6.378/4.252 | 29/26 | 1.7606–10.7739 | 4 / 3 | 2/6/9/25/0 | 40/40 |
| Lesson-3 | 3/3 | 6.378/4.252 | 30/27 | 1.8435–10.6899 | 4 / 3 | 2/7/8/26/0 | 41/41 |
| Lesson-3 | 3/4 | 6.378/4.252 | 23/19 | 1.8435–10.5466 | 4 / 3 | 2/11/2/18/0 | 33/31 |
| Lesson-3 | 3/5 | 6.378/4.252 | 21/19 | 1.9826–10.3332 | 3 / 2 | 2/9/5/18/0 | 32/32 |
| Lesson-3 | 3/6 | 6.378/4.252 | 23/20 | 1.9826–10.3333 | 3 / 2 | 2/9/5/19/0 | 35/33 |
| Lesson-3 | 3/7 | 6.378/4.252 | 31/28 | 1.9820–10.3333 | 4 / 3 | 2/8/7/27/0 | 42/42 |
| Lesson-3 | 4/1 | 6.378/4.252 | 30/26 | 1.9840–10.7065 | 4 / 3 | 2/8/6/25/0 | 43/39 |
| Lesson-3 | 4/2 | 6.378/4.252 | 28/25 | 1.8862–10.7739 | 4 / 3 | 2/6/7/24/0 | 37/37 |
| Lesson-3 | 4/3 | 6.378/4.252 | 39/33 | 1.9583–11.8082 | 5 / 4 | 2/17/4/32/0 | 57/53 |
| Lesson-4 | 1/1 | 6.378/4.252 | 23/20 | 2.1485–10.9124 | 3 / 2 | 2/2/6/19/0 | 31/27 |
| Lesson-4 | 1/2 | 6.378/4.252 | 22/19 | 1.9826–10.3332 | 3 / 2 | 2/4/6/19/0 | 29/29 |
| Lesson-4 | 1/3 | 6.378/4.252 | 21/18 | 1.9567–10.9124 | 3 / 2 | 2/9/3/17/0 | 33/29 |
| Lesson-4 | 1/4 | 6.378/4.252 | 30/27 | 1.8435–10.9124 | 4 / 3 | 2/6/6/26/0 | 38/38 |
| Lesson-4 | 1/5 | 6.378/4.252 | 21/19 | 1.9826–10.9122 | 3 / 2 | 2/2/5/18/0 | 27/25 |
| Lesson-4 | 1/6 | 6.378/4.252 | 25/21 | 2.0450–10.5441 | 4 / 3 | 2/9/5/20/0 | 36/34 |
| Lesson-4 | 2/1 | 6.378/4.252 | 18/16 | 1.7509–10.3333 | 3 / 2 | 2/6/5/15/0 | 26/26 |
| Lesson-4 | 2/2 | 6.378/4.252 | 30/26 | 1.9708–10.9125 | 4 / 3 | 2/7/7/25/0 | 43/39 |
| Lesson-4 | 2/3 | 6.378/4.252 | 35/31 | 1.6231–10.9124 | 5 / 4 | 2/12/8/30/0 | 52/50 |
| Lesson-4 | 2/4 | 6.378/4.252 | 30/26 | 1.6428–11.8082 | 4 / 3 | 2/10/7/25/0 | 44/42 |
| Lesson-4 | 2/5 | 6.378/4.252 | 25/21 | 1.9873–10.3332 | 4 / 3 | 2/2/5/20/0 | 31/27 |
| Lesson-4 | 2/6 | 6.378/4.252 | 31/28 | 1.9672–10.3332 | 4 / 3 | 2/8/8/27/0 | 43/43 |
| Lesson-4 | 2/7 | 6.378/4.252 | 32/28 | 1.9683–10.7876 | 4 / 3 | 2/11/7/27/0 | 49/45 |
| Lesson-4 | 3/1 | 6.378/4.252 | 34/27 | 1.8435–10.7957 | 5 / 4 | 2/8/7/28/0 | 44/43 |
| Lesson-4 | 3/2 | 6.378/4.252 | 34/27 | 1.8435–10.7957 | 5 / 4 | 2/8/7/28/0 | 44/43 |
| Lesson-4 | 3/3 | 6.378/4.252 | 30/27 | 1.8435–10.7880 | 4 / 3 | 2/8/7/26/0 | 41/41 |
| Lesson-4 | 3/4 | 6.378/4.252 | 25/21 | 2.0448–10.7107 | 4 / 3 | 2/7/4/20/0 | 33/31 |
| Lesson-4 | 3/5 | 6.378/4.252 | 19/17 | 1.7509–10.3332 | 3 / 2 | 2/4/6/16/0 | 26/26 |
| Lesson-4 | 3/6 | 6.378/4.252 | 30/26 | 1.9602–10.7088 | 4 / 3 | 2/7/7/25/0 | 43/39 |
| Lesson-4 | 3/7 | 6.378/4.252 | 23/20 | 1.9823–10.3333 | 3 / 2 | 2/9/5/19/0 | 35/33 |
| Lesson-4 | 4/1 | 6.378/4.252 | 23/20 | 1.9823–10.3333 | 3 / 2 | 2/9/5/19/0 | 35/33 |
| Lesson-4 | 4/2 | 6.378/4.252 | 25/21 | 2.0450–10.7107 | 4 / 3 | 2/10/4/20/0 | 36/34 |
| Lesson-4 | 4/3 | 6.378/4.252 | 26/22 | 1.9760–10.8663 | 4 / 3 | 2/7/6/21/0 | 36/34 |
| Lesson-4 | 4/4 | 6.378/4.252 | 21/19 | 2.0378–11.8230 | 3 / 2 | 2/9/5/19/0 | 33/33 |
| Lesson-4 | 4/5 | 6.378/4.252 | 22/19 | 1.8705–11.1262 | 3 / 2 | 2/10/3/18/0 | 35/31 |
| Lesson-4 | 4/6 | 6.378/4.252 | 21/19 | 2.0379–10.3332 | 3 / 2 | 2/6/4/18/0 | 28/28 |
| Lesson-4 | 5/1 | 6.378/4.252 | 28/24 | 1.9047–12.1055 | 4 / 3 | 2/8/6/23/0 | 39/37 |
| Lesson-4 | 5/2 | 6.378/4.252 | 30/27 | 1.8865–10.7741 | 4 / 3 | 2/10/7/26/0 | 43/43 |
| Lesson-4 | 5/3 | 6.378/4.252 | 31/26 | 1.8801–10.7062 | 4 / 3 | 2/11/5/26/0 | 48/42 |
| Lesson-5 | 1/1 | 6.378/4.252 | 57/53 | 2.1410–11.9442 | 5 / 4 | 2/22/11/52/1 | 92/85 |
| Lesson-5 | 1/2 | 6.378/4.252 | 54/49 | 1.8909–11.9323 | 5 / 4 | 2/15/13/48/6 | 96/76 |
| Lesson-5 | 1/3 | 6.378/4.252 | 57/53 | 1.8821–11.9415 | 5 / 4 | 2/23/13/52/2 | 98/88 |
| Lesson-5 | 1/4 | 6.378/4.252 | 47/40 | 1.9047–11.9183 | 5 / 4 | 2/13/10/41/5 | 81/64 |
| Lesson-5 | 1/5 | 6.378/4.252 | 31/28 | 1.8827–11.1982 | 3 / 2 | 2/12/4/28/1 | 48/44 |
| Lesson-5 | 2/1 | 6.378/4.252 | 49/42 | 2.2288–13.2441 | 5 / 4 | 2/16/10/43/2 | 79/69 |
| Lesson-5 | 2/2 | 6.378/4.252 | 43/40 | 1.9059–11.9061 | 4 / 3 | 2/15/8/39/1 | 66/62 |
| Lesson-5 | 2/3 | 6.378/4.252 | 26/23 | 2.2912–11.3645 | 3 / 2 | 2/8/2/22/0 | 34/32 |
| Lesson-5 | 2/4 | 6.378/4.252 | 55/52 | 2.0933–11.3288 | 4 / 3 | 2/17/8/51/0 | 90/76 |
| Lesson-5 | 2/5 | 6.378/4.252 | 52/49 | 2.2617–11.8390 | 4 / 3 | 2/27/7/48/2 | 93/82 |
| Lesson-5 | 2/6 | 6.378/4.252 | 46/42 | 1.9410–11.1767 | 4 / 3 | 2/15/7/41/1 | 71/63 |
| Lesson-5 | 3/1 | 6.378/4.252 | 37/35 | 1.9563–10.4572 | 3 / 2 | 2/14/4/34/0 | 52/52 |
| Lesson-5 | 3/2 | 6.378/4.252 | 39/35 | 1.9458–10.3332 | 3 / 2 | 2/8/9/36/2 | 59/53 |
| Lesson-5 | 3/3 | 6.378/4.252 | 41/33 | 2.2413–11.1823 | 4 / 3 | 2/12/4/35/0 | 53/51 |
| Lesson-6 | 1/1 | 6.378/4.252 | 29/27 | 2.4055–10.8743 | 3 / 2 | 2/12/5/26/0 | 43/43 |
| Lesson-6 | 1/2 | 6.378/4.252 | 31/28 | 2.2824–10.8735 | 3 / 2 | 2/13/4/27/2 | 50/44 |
| Lesson-6 | 1/3 | 6.378/4.252 | 31/28 | 2.2825–10.8735 | 3 / 2 | 2/12/5/27/1 | 48/44 |
| Lesson-6 | 1/4 | 6.378/4.252 | 31/28 | 2.2824–10.8736 | 3 / 2 | 2/13/4/27/1 | 50/44 |
| Lesson-6 | 1/5 | 6.378/4.252 | 29/27 | 2.2828–10.8732 | 3 / 2 | 2/8/6/26/2 | 46/40 |
| Lesson-6 | 1/6 | 6.378/4.252 | 33/29 | 1.9301–11.9997 | 4 / 3 | 2/14/5/28/2 | 53/47 |
| Lesson-6 | 2/1 | 6.378/4.252 | 13/11 | 2.6667–10.3332 | 3 / 2 | 2/5/1/10/0 | 16/16 |
| Lesson-6 | 2/2 | 6.378/4.252 | 29/27 | 2.4040–11.3733 | 3 / 2 | 2/7/7/26/0 | 40/40 |
| Lesson-6 | 2/3 | 6.378/4.252 | 31/28 | 2.4044–11.7065 | 3 / 2 | 2/7/6/27/0 | 42/40 |
| Lesson-6 | 2/4 | 6.378/4.252 | 27/22 | 2.6667–10.3332 | 5 / 4 | 2/0/2/21/0 | 29/23 |
| Lesson-6 | 2/5 | 6.378/4.252 | 29/27 | 2.4040–11.8733 | 3 / 2 | 2/8/5/26/0 | 39/39 |
| Lesson-6 | 2/6 | 6.378/4.252 | 33/27 | 2.2717–12.4111 | 4 / 3 | 2/8/5/28/1 | 44/41 |
| Lesson-6 | 3/1 | 6.378/4.252 | 31/28 | 2.4055–11.1399 | 3 / 2 | 2/9/6/27/0 | 44/42 |
| Lesson-6 | 3/2 | 6.378/4.252 | 31/28 | 2.2813–11.1399 | 3 / 2 | 2/9/6/27/1 | 48/42 |
| Lesson-6 | 3/3 | 6.378/4.252 | 31/28 | 2.2813–11.1397 | 3 / 2 | 2/10/5/27/2 | 48/42 |
| Lesson-6 | 3/4 | 6.378/4.252 | 15/12 | 2.6667–10.3333 | 3 / 2 | 2/0/0/11/0 | 13/11 |
| Lesson-6 | 3/5 | 6.378/4.252 | 31/28 | 2.4056–11.1400 | 3 / 2 | 2/8/5/27/0 | 44/40 |
| Lesson-6 | 3/6 | 6.378/4.252 | 15/12 | 2.6667–10.3332 | 3 / 2 | 2/0/0/11/0 | 15/11 |
| Lesson-6 | 4/1 | 6.378/4.252 | 29/27 | 2.0721–11.1397 | 3 / 2 | 2/10/3/26/0 | 39/39 |
| Lesson-6 | 4/2 | 6.378/4.252 | 31/28 | 1.9481–11.1399 | 3 / 2 | 2/10/3/27/0 | 42/40 |
| Lesson-6 | 4/3 | 6.378/4.252 | 15/12 | 2.6667–10.3333 | 3 / 2 | 2/0/1/11/0 | 16/12 |
| Lesson-6 | 4/4 | 6.378/4.252 | 29/27 | 2.0724–11.1399 | 3 / 2 | 2/10/5/26/1 | 43/41 |
| Lesson-6 | 4/5 | 6.378/4.252 | 31/28 | 1.9476–11.1403 | 3 / 2 | 2/10/5/27/2 | 48/42 |
| Lesson-6 | 4/6 | 6.378/4.252 | 15/12 | 2.6667–10.3332 | 3 / 2 | 2/0/0/11/0 | 13/11 |
| Lesson-6 | 5/1 | 6.378/4.252 | 29/27 | 2.0728–11.1399 | 3 / 2 | 2/12/2/26/0 | 40/40 |
| Lesson-6 | 5/2 | 6.378/4.252 | 31/28 | 1.9475–11.1402 | 3 / 2 | 2/12/2/27/0 | 43/41 |
| Lesson-6 | 5/3 | 6.378/4.252 | 15/12 | 2.6667–10.3332 | 3 / 2 | 2/0/0/11/0 | 13/11 |
| Lesson-6 | 5/4 | 6.378/4.252 | 15/12 | 2.6667–10.3332 | 3 / 2 | 2/0/2/11/0 | 15/13 |
| Lesson-6 | 5/5 | 6.378/4.252 | 29/27 | 2.0720–11.1395 | 3 / 2 | 2/10/8/26/3 | 50/44 |
| Lesson-6 | 5/6 | 6.378/4.252 | 29/26 | 1.9511–10.3333 | 3 / 2 | 2/9/7/25/5 | 53/41 |
| Lesson-6 | 5/7 | 6.378/4.252 | 15/12 | 2.6667–10.3332 | 3 / 2 | 2/0/0/11/0 | 13/11 |
| Lesson-6 | 6/1 | 6.378/4.252 | 31/28 | 2.0721–10.3332 | 3 / 2 | 2/7/7/27/2 | 47/41 |
| Lesson-6 | 6/2 | 6.378/4.252 | 13/11 | 2.6667–10.3333 | 3 / 2 | 2/0/0/10/0 | 10/10 |
| Lesson-6 | 6/3 | 6.378/4.252 | 33/29 | 1.9517–10.5111 | 3 / 2 | 2/10/6/28/4 | 56/44 |
| Lesson-7 | 1/1 | 6.378/4.252 | 29/26 | 2.0532–10.7027 | 3 / 2 | 2/8/7/25/1 | 46/40 |
| Lesson-7 | 1/2 | 6.378/4.252 | 29/26 | 2.0525–10.7037 | 3 / 2 | 2/8/7/25/1 | 46/40 |
| Lesson-7 | 1/3 | 6.378/4.252 | 31/28 | 2.0550–10.3788 | 3 / 2 | 2/10/4/27/0 | 45/41 |
| Lesson-7 | 1/4 | 6.378/4.252 | 26/23 | 1.9716–10.3333 | 3 / 2 | 2/6/3/22/1 | 35/31 |
| Lesson-7 | 1/5 | 6.378/4.252 | 31/28 | 2.0552–10.3788 | 3 / 2 | 2/10/4/27/0 | 45/41 |
| Lesson-7 | 2/1 | 6.378/4.252 | 26/24 | 2.1151–10.3333 | 3 / 2 | 2/8/3/23/1 | 38/34 |
| Lesson-7 | 2/2 | 6.378/4.252 | 28/25 | 2.1135–10.5367 | 3 / 2 | 2/7/5/24/1 | 42/36 |
| Lesson-7 | 2/3 | 6.378/4.252 | 26/24 | 2.1151–10.5310 | 3 / 2 | 2/7/4/23/1 | 38/34 |
| Lesson-7 | 2/4 | 6.378/4.252 | 28/25 | 2.1146–10.3332 | 3 / 2 | 2/8/3/24/1 | 41/35 |
| Lesson-7 | 2/5 | 6.378/4.252 | 28/25 | 2.1148–10.3333 | 3 / 2 | 2/8/3/24/1 | 41/35 |
| Lesson-7 | 2/6 | 6.378/4.252 | 24/21 | 2.1232–11.2817 | 3 / 2 | 2/7/3/20/2 | 36/30 |
| Lesson-7 | 3/1 | 6.378/4.252 | 26/23 | 2.1769–11.2852 | 3 / 2 | 2/9/3/22/1 | 40/34 |
| Lesson-7 | 3/2 | 6.378/4.252 | 26/23 | 2.1769–11.2860 | 3 / 2 | 2/9/3/22/1 | 40/34 |
| Lesson-7 | 3/3 | 6.378/4.252 | 26/23 | 2.1769–11.2860 | 3 / 2 | 2/9/3/22/1 | 40/34 |
| Lesson-7 | 3/4 | 6.378/4.252 | 26/23 | 2.1769–10.5400 | 3 / 2 | 2/9/4/22/1 | 41/35 |
| Lesson-7 | 3/5 | 6.378/4.252 | 24/22 | 2.1769–10.5400 | 3 / 2 | 2/9/4/21/1 | 38/34 |
| Lesson-7 | 3/6 | 6.378/4.252 | 29/26 | 2.0533–10.3333 | 3 / 2 | 2/8/2/25/1 | 41/35 |
| Lesson-7 | 4/1 | 6.378/4.252 | 26/23 | 1.9710–11.2858 | 3 / 2 | 2/7/3/22/3 | 40/32 |
| Lesson-7 | 4/2 | 6.378/4.252 | 22/19 | 2.1769–10.3332 | 3 / 2 | 2/6/2/18/0 | 28/26 |
| Lesson-7 | 4/3 | 6.378/4.252 | 22/19 | 2.1769–10.3332 | 3 / 2 | 2/6/2/18/0 | 28/26 |
| Lesson-7 | 4/4 | 6.378/4.252 | 22/19 | 2.1769–10.3332 | 3 / 2 | 2/6/2/18/0 | 28/26 |
| Lesson-7 | 4/5 | 6.378/4.252 | 22/19 | 2.1769–10.3332 | 3 / 2 | 2/6/2/18/0 | 28/26 |
| Lesson-7 | 4/6 | 6.378/4.252 | 22/19 | 2.1770–10.3333 | 3 / 2 | 2/6/2/18/0 | 28/26 |
| Lesson-7 | 5/1 | 6.378/4.252 | 22/19 | 2.1769–10.3332 | 3 / 2 | 2/6/2/18/0 | 28/26 |
| Lesson-7 | 5/2 | 6.378/4.252 | 24/20 | 2.1769–10.3333 | 3 / 2 | 2/6/2/19/0 | 31/27 |
| Melodic Soloing Masterclass | 1/1 | 26.575/17.7165 | 72/57 | 0.3787–13.1258 | 5 / 4 | 2/39/7/58/0 | 25/104 |
| Melodic Soloing Masterclass | 1/2 | 26.575/17.7165 | 41/32 | 0.3787–12.9156 | 3 / 2 | 2/22/6/32/0 | 13/60 |
| Melodic Soloing Masterclass | 1/3 | 26.575/17.7165 | 42/31 | 0.3787–12.7490 | 3 / 2 | 2/24/4/28/0 | 11/56 |

## Evidence limits

No production code, tests, build_ir gating set, or fixture is changed. No mutant is claimed. The required real-source negative controls cannot pass at this base: the seven located stems currently become final boundaries, and Black Dog contains a false notation-region TAB detection. A changed-behaviour test suite and clean-archive proof belong to a separately authorised recognition repair; they are not claimed by this stopped scale-only investigation. Ledger-line and between-staves negative controls are not proved. No synthetic domain acceptance is used.
