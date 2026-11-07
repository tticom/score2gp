# RASTER-00: scoping the scanned and hand-drawn sources

Status: measurement only. No source's output changes; nothing here is wired into `convert`. Counts and located
reasons only, no private content. Every figure below was re-measured on the current runtime (PyMuPDF 1.28.2,
Pillow 13.0.0) with `src/score2gp/raster_scoping.py`; the NOROUTE-01 leads (177 and 105 pages, 0 drawings,
1 image per page) were confirmed.

**Not independently verified.** None of the three sources has a reference file (`.gp`, MusicXML or hand count).
The only check on any located count is one viewer's count of one printed sample page per source. Everything
reference-less below is labelled as such, and the synthetic-free test file carries the real sources only.

## 1. The three sources

| Source (corpus name) | Pages | Vector drawings | Images/page | Embedded image resolution | Text words |
|---|---|---|---|---|---|
| Hand-drawn one-pager (`LegatoLicks`) | 1 | 0 | 1 | 300 dpi (2480 x 3507 px) | 80 (a text layer exists; not read here) |
| Scanned book A (`Hal Leonard ... Rock Ballads`) | 177 | 0 | 1 on all 177 | 344 dpi on 174 pages, 332 on 1, 182 on 1, 174 on 1 | 0 |
| Scanned book B (`Jazz Classics for Solo Guitar ...`) | 105 | 0 | 1 on all 105 | 600 dpi on 103 pages, 200 on 2 | 0 |

All three are image-only for the purpose of the vector pipeline: `pdf.py` classes them `scanned-or-raster` and
refuses with `pdf_input_class_scanned_pdf_unsupported` (pinned by `tests/test_noroute_01_private.py`).

## 2. What raster code exists today, and what each piece does

| Piece | Where | What it does today | Used on these sources |
|---|---|---|---|
| `build_raster_notation_diagnostics` | `pdf_raster_staff_diagnostics.py` | Renders at 2x, thresholds at 128, takes unbroken dark runs wider than 35% of the page, groups 5 evenly spaced lines into a notation staff and **deliberately drops any 5-line group that sits inside a longer run (6-line TAB)**; crops the left margin for a treble-clef-shaped blob. Diagnostics only. | Yes, via the smoke script; finds almost nothing (below). |
| `classify_raster_opening_symbol_candidate` / `summarize_raster_treble_clef_diagnostics` | same | Proportion heuristics for a treble clef candidate. | Only on staves that were found. |
| `scripts/private_raster_diagnostic_smoke.py`, `scripts/raster_diagnostics_gate_report.py` | `scripts/` | Run the above over a PDF (advisory CI workflow). | Not run in CI on these sources. |
| `recognition/raster.py` (REC) | `recognition/` | Deterministic page render with provenance (dpi, affine, sample SHA-256), line, glyph (8-connected components) and region observations, cross-modal vector/raster comparison. Typed, non-semantic. | Glyph extractor reused by this task's digit-band probe. |
| `recognition/scale.py`, `observations.py`, `schemas.py` | `recognition/` | Scale and observation schemas. | No. |
| `notation_omr/` | `notation_omr/` | Clef, notehead, duration, tuplet, staff geometry, timeline and position optimiser; consume vector evidence (and the raster clef bridge). | No: needs vector or already-located staves. |
| Audiveris wrapper | `cli.py omr` | Shells out to a user-supplied Audiveris executable and imports the MusicXML it writes. Audiveris is **not installed on this host**, so no Audiveris result was measured; nothing below claims one. | No. |
| OCR / digit reader | none | There is no raster digit recogniser and no OCR dependency (no numpy, OpenCV or Tesseract in the dev environment). | n/a |

Result of the existing locator over every page of each source (`build_raster_notation_diagnostics`, scale 2.0):

| Source | Pages with at least one staff found | Staves found | Treble-clef candidates |
|---|---|---|---|
| Hand-drawn one-pager | 0 of 1 | 0 | 0 |
| Scanned book A | 15 of 177 | 36 | not summarised |
| Scanned book B | 14 of 105 | 39 | not summarised |

Located reasons, from re-running the locator's own steps on sample pages: on the one-pager the ruled lines are
long (26 rows with an unbroken run over 35% of the width) but the notation staves are interrupted by hand-drawn
text and clefs and the TAB staves are 6-line, which the locator rejects by design; on book B at 600 dpi source
(144 dpi render) the lines are thinner than one rendered pixel, so **no row reaches the 128 threshold over 35% of
the width** (0 rows on the sample page); on book A the 5-line staves are found on only some pages (36 staves
in 15 pages).

## 3. Staff location, measured with a tolerant row-profile locator

`raster_scoping.measure_staff_location` renders at 150 dpi, takes mean ink per pixel row (anti-aliasing
tolerant), merges inked rows into lines and finds evenly spaced chains (spacing 2 to 12 pt, 20% tolerance).
A 5-chain is a notation-staff candidate, a 6-chain a TAB candidate. It is a measurement hook, not a recogniser.

| Source | Pages | Pages with a staff-like chain | 5-line chains | 6-line chains | Other line counts |
|---|---|---|---|---|---|
| Hand-drawn one-pager | 1 | 1 | 4 | 6 | 0 |
| Scanned book A | 177 | 170 (96%) | 621 | 700 | 64 |
| Scanned book B | 105 | 87 (83%) | 409 | 271 | 6 |

Pages with no chain (7 in A, 18 in B) were not classified; the located reason is "no evenly spaced line chain at
the measurement thresholds", which does not say whether the page carries music.

**Share of staves found** can only be stated against a denominator on the viewed sample pages (one viewer, not
independently verified):

| Sample page | Viewed (notation + TAB) | Located | Of which kind right | Existing locator |
|---|---|---|---|---|
| One-pager | 6 + 6 = 12 | 10 (83%): 4 notation, 6 TAB; all 6 TAB found, 2 notation missed (text drawn across the lines) | 10 | 0 |
| Book A, p.21 | 6 + 3 = 9 | 9 (100%) | 7 of 9: two notation staves took a spurious sixth line and read as 6-line (their spacing, 6.5 px, matches notation, not the 10.8 px TAB spacing) | 0 |
| Book B, p.11 | 4 + 4 = 8 | 8 (100%) | 8 | 0 |

Over the whole books the 5-line/6-line labels are line-count labels only. The 5-line vs 6-line split is
unreliable as a notation/TAB classifier (book A reports more 6-line chains than 5-line ones although each system
has one TAB staff per two notation staves); a located staff is therefore a **location**, not yet a kind.

## 4. First slice and which stage fails first

Measured on the three sample pages:

1. **Staff location** fails first for the existing code (0 of 29 viewed staves on the sample pages) and gets
   most of the way with a tolerant row profile (27 of 29 located, 25 of 29 with the right kind; unverified).
   The failures that remain are hand-drawn text across staff lines, and spurious extra lines (lyrics underlines,
   beams) on dense notation staves.
2. **TAB digit reading** is next. With staff-line rows blanked, the repo's own connected-component extractor
   finds digit-sized components (height 0.5 to 2.0 line spacings) in every located TAB band: one-pager
   17 to 57 per staff (6 staves), book A 20 to 30 per staff (3 TAB staves), book B 22 to 39 per staff
   (4 staves). **None is identified**: the repo has no digit classifier, a two-digit fret is not told from two
   frets, and the counts are not checked against a hand count (not independently verified).
3. **Rhythm** is unread. Stems, beams, flags, dots and rests are not located by any raster code. In these
   sources rhythm lives in the notation staff above each TAB, so it also needs staff-to-TAB alignment.

Smallest honest first slice: **TAB-staff location plus digit candidate location on the 600 and 344 dpi scanned
books, emitting located, unidentified observations only** (through the existing `recognition/` raster
observation schemas), with every unread band refused with a located reason. This is the stage the current code
fails first and the only one measurable here without a reference; it writes no GP output, so nothing that works
can change. The hand-drawn page is a separate, later slice: its digits and staff lines are drawn by hand and the
staves are interrupted by text, so it should not set the acceptance bar.

### Cost of owning each stage in Python vs replacing Audiveris (estimates, not measured)

| Stage | Own in Python | Audiveris |
|---|---|---|
| Staff location | Small: the probe above is about 150 lines with no new dependency; remaining work is deskew, text-over-line handling and notation-vs-TAB classification. Pure-Python pixel loops are slow at 600 dpi (a few seconds per page); numpy would be a new dependency. | Locates notation staves well but not TAB as TAB; its output is a MusicXML sidecar score2gp cannot see inside, which conflicts with the topology-first rule that score2gp owns system and barline topology. |
| TAB digit reading | Largest owned item: a classifier for the digits 0 to 24 on a possibly handwritten TAB, with no reference corpus and no OCR dependency. Needs labelled real crops, which the approved corpus does not yet hold. | Not provided: Audiveris does not read guitar TAB (`docs/setup.md`). Replacing it does not help this stage. |
| Rhythm | Medium to large: stems/beams/flags/dots/rests from raster, plus alignment to TAB. `notation_omr/duration.py` and `tuplet.py` consume vector evidence only. | Provides durations from notation staves, which is its strength; reliability on these scans is unmeasured here (not installed). |

## 5. Dependencies

- **DEC-01** (still undecided: own the recogniser vs depend on an external OMR) gates everything beyond the
  first slice. The first slice (staff and digit candidate location, no identification) is common to both
  branches of DEC-01 and can proceed before it is decided; digit identification and rhythm cannot.
- **REC items:** the first slice emits through the existing `recognition/raster.py` line/glyph/region
  observations and their provenance. Digit identification would need a typed observation for a classified digit,
  which the current schemas do not carry (they are explicitly non-semantic).
- A reference for acceptance does not exist for any of the three sources; either hand counts approved by the
  maintainer or a ground-truth `.gp` is needed before any located or read count can be called verified.

## 6. What changed in this task

`src/score2gp/raster_scoping.py` (measurement hook, not imported by the product), `tests/test_raster_00_scoping_private.py`
(real sources only; mutants named in its docstring) and this document. No source, fixture, schema or CLI output
changed. Synthetic tests carry no acceptance weight and none were added.
