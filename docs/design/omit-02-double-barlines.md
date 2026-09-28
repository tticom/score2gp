# OMIT-02 double barlines

The reader classifies painted barline contours at bar ends already located by
the notation reader. The TAB topology supplies the fallback for inputs without
notation bars. A filled rectangle has two vertical edges with one PDF primitive
ID; it counts as one stroke. A double requires two distinct, full-staff strokes
of the same primitive kind, each 0.45–1.0 pt wide, with a width difference at
most 0.2 pt and a 1.5–3.2 pt gap. These inclusive bounds leave a gap around
the measured wider and more distant near misses. A single stroke does not
produce `DoubleBar`.

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

A thin pair writes `Bar.barline = "double"`; the GPIF writer already emits
`DoubleBar` on that master bar. A thin/wide pair with two small dots in the two
middle notation spaces is a repeat, with the wide-stroke side determining
start or end. A final-bar thin/wide pair without dots is an end barline.
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
