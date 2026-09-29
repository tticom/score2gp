# OMIT-02 double barlines

The reader classifies painted barline contours at bar ends already located by
the notation reader. The TAB topology supplies the fallback for inputs without
notation bars. A filled rectangle has two vertical edges with one PDF primitive
ID; it counts as one stroke. A double requires two distinct, full-staff strokes
of the same primitive kind, each 0.45–1.0 pt wide, with a width difference at
most 0.2 pt and a 1.5–3.2 pt gap. These inclusive bounds leave a gap around
the measured wider and more distant near misses. A single stroke does not
produce `DoubleBar`.

These point bounds assume the approximately 3.75–4.26 pt notation staff space
measured in the mounted lesson and repeat-bearing PDFs. At other engraving
scales a pair outside the range is refused; the bounds are not scaled with the
staff. Tests cover values just outside the thin width, thin gap, thick width
and thick gap limits.

The mounted corpus probe covered all 30 PDFs (377 pages). The TAB topology
found 411 systems and 200 provisional pairs, with zero extraction errors.
Of those pairs, 124 were equal 0.68 pt rectangles separated by 2.38 pt. The
remaining 76 had widths from 0.40 to 3.22 pt and gaps from 3.38 to 11.99 pt.
The section-ending pairs in the five numbered lesson PDFs were 0.68/0.68 pt
rectangles at 2.38 pt. The repeat-bearing example had 1.88/0.60 pt pairs at
3.38 pt. Final-style pairs were 2.13/0.68 pt at 3.83 pt. Other sources
included thin line pairs 9.95–11.50 pt apart, which the older topology called
double but which cannot safely be given double-bar semantics. The two long
books yielded no TAB systems, so this measurement makes no claim about their
barline kinds. These are geometry observations, not values copied from GP files.

The notation reader supplies zero-based bar bounds; the new contour reader
uses each measured right bound and emits a one-based source bar index. The
`pdf-barline-signals.v0.1` record carries page, system, bar, status, reason and
PDF primitive IDs with stroke geometry. The TAB fallback emits the same record
using accepted bar boxes. This signal is an additive member of TabRaw's
`structural_signals` extension map; the outer TabRaw model is unchanged.

The CLI records notation stroke decisions in that map during PDF evidence
extraction, before ScoreIR building. An older TabRaw without the key keeps the
existing TAB topology fallback and receives a located
`barline_evidence_unavailable` warning. The build stage never opens
`source_pdf` to classify barlines. An empty list records that extraction ran
and found no notation barline decision, distinct from an absent key. The
simple GPIF writer also emits `DoubleBar` for a double barline.

A thin pair writes `Bar.barline = "double"`; the GPIF writer already emits
`DoubleBar` on that master bar. A thin/wide pair with two small dots in the two
middle notation spaces is a repeat, with the wide-stroke side determining
start or end. The reader searches both filled drawings and text characters.
The real repeat-bearing PDF has 16 `U+E044` characters in its embedded
`GPBravuraRegular` font, two per notated staff repeat mark. Their character
origins, unlike their overlapping 15 pt text boxes, lie about two and three
staff spaces below the top line. Their horizontal offset from the thin stroke
is about 1.86 pt on the repeat-start and 3.98 pt on repeat-ends, so the glyph
side window begins at 1.5 pt; the drawing window remains 2.0–9.0 pt. A
dot-like character or drawing in the side
window that cannot be matched as a pair makes the decision refuse. Only a
final-bar thin/wide pair with no candidate dots in either representation is
read as an end barline. The five private GP references have no master-bar
`Barline/End` element, so the end decision is retained as a located diagnostic
without adding that element to output GPIF.
Conflicting existing bar kinds and unresolved targets produce located warnings
and no new bar kind. A pair of uncertain kind produces
`pdf_barline_pair_kind_unresolved` with its source strokes. Read decisions also
retain their source strokes in informational ScoreIR warnings.

The public PDFs under `tests/fixtures/pdf/omit_02/` are variations of a
standard notation and TAB page. They contain a double, a single, a thick
single, a dotted repeat, a final pair and a system-start bracket. Their
expected GPIF flags were specified from those conventional marks, independent
of the production classifier. The CLI tests inspect every resulting master
bar and the read decision's source-stroke IDs.

`repeat_glyph_final.pdf` embeds Steinberg's Bravura OpenType font under the
[SIL Open Font License 1.1](https://github.com/steinbergmedia/bravura/blob/master/LICENSE.txt)
and places two `U+E044` text characters beside a final thin/wide pair. It is
a public synthetic engraving control, not a copied private page. The older
`repeat_dots.pdf` uses appended vector rectangles and remains a synthetic
control; no measured private source in this task establishes vector repeat
dots as its representation.
