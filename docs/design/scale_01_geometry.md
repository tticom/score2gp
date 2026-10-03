# SCALE-01 source geometry measurements

Measured from the 30 mounted PDFs at product base `df7decb14676bfdeff1aaec356e33cc77da6e136`. Each row is one PDF in a stable local sorted order; names and musical content are omitted. `P25` is the enlarged target. `P01`, `P02`, and `P11` are the three named TAB-only refusal controls. Dimensions, staff spaces, and rectangle widths are PDF points. The size column lists every distinct page size in that PDF. Staff counts cover all pages (notation/TAB); the staff-space column is the median detected spacing, or the repeated long-horizontal step when the base detector found no staff. `none` means no reliable vector step was measured. The rectangle column lists the three most frequent widths of filled vertical rectangles (width, count); it does not label them as notes or bars.

| ID | Pages | Page sizes (pt) | Space (pt) | Base staffs N/T | Head staffs N/T | Vertical rectangle widths (pt, count) |
|---|---:|---|---:|---:|---:|---|
| P01 | 3 | 901.2×1274.5 | 9.66 | 0/20 | 0/20 | 1.03 (75), 3.22 (3) |
| P02 | 1 | 901.2×1274.5 | 9.66 | 0/6 | 0/6 | 1.03 (24), 3.22 (1) |
| P03 | 1 | 612.0×792.0 | 5.0 | 4/4 | 4/4 | none |
| P04 | 2 | 612.0×792.0 | 5.0 | 5/5 | 5/5 | none |
| P05 | 1 | 612.0×792.0 | 5.0 | 4/4 | 4/4 | none |
| P06 | 2 | 595.3×841.9 | 5.31 | 10/10 | 10/10 | 0.68 (42), 2.3 (10), 2.13 (2) |
| P07 | 2 | 612.0×792.0 | 5.0 | 6/6 | 6/6 | none |
| P08 | 3 | 612.0×792.0 | 5.0 | 14/14 | 14/14 | none |
| P09 | 2 | 595.0×842.0 | 5.31 | 9/9 | 9/9 | 0.68 (32), 2.13 (2) |
| P10 | 1 | 595.0×842.0 | 4.69 | 3/3 | 3/3 | 0.6 (24), 1.88 (10) |
| P11 | 1 | 901.2×1274.5 | 9.66 | 0/5 | 0/5 | 1.03 (20), 3.22 (1) |
| P12 | 1 | 595.0×842.0 | 5.31 | 4/4 | 4/4 | 0.68 (20), 0.34 (18), 2.13 (8) |
| P13 | 177 | 524.4×680.3 | none | 0/0 | 0/0 | none |
| P14 | 1 | 612.0×792.0 | 5.0 | 3/3 | 3/3 | none |
| P15 | 2 | 612.0×792.0 | 5.0 | 6/6 | 6/6 | none |
| P16 | 105 | 608.6×842.4, 609.1×842.4 | none | 0/0 | 0/0 | none |
| P17 | 2 | 595.0×842.0 | 5.31 | 8/8 | 8/8 | 0.68 (84), 0.34 (6), 2.13 (2) |
| P18 | 1 | 595.2×841.7 | none | 0/0 | 0/0 | none |
| P19 | 4 | 612.0×792.0 | 5.31 | 23/23 | 23/23 | 0.68 (154), 2.13 (2) |
| P20 | 5 | 612.0×792.0 | 5.31 | 29/29 | 29/29 | 0.68 (192), 2.13 (2) |
| P21 | 3 | 612.0×792.0 | 5.31 | 14/14 | 14/14 | 0.68 (98), 2.13 (2) |
| P22 | 6 | 612.0×792.0 | 5.31 | 34/34 | 34/34 | 0.68 (190), 2.13 (2) |
| P23 | 5 | 612.0×792.0 | 5.31 | 25/25 | 25/25 | 0.68 (142), 2.13 (2) |
| P24 | 1 | 595.0×841.9 | none | 0/0 | 0/0 | none |
| P25 | 1 | 2480.3×3507.9 | 17.72 | 0/0 | 3/0 | 2.83 (16), 2.84 (2), 8.86 (2) |
| P26 | 34 | 595.3×841.9 | 5.32 | 178/178 | 178/178 | 0.68 (1312), 0.34 (24), 2.13 (6) |
| P27 | 2 | 595.3×841.9 | 5.31 | 9/9 | 9/9 | 0.68 (68), 2.13 (2) |
| P28 | 2 | 612.0×792.0 | 5.0 | 6/6 | 6/6 | none |
| P29 | 4 | 595.0×842.0 | 6.38 | 17/19 | 17/19 | 0.68 (196), 0.34 (102), 2.13 (2) |
| P30 | 2 | 595.0×842.0 | 5.31 | 10/10 | 10/10 | 0.68 (104), 2.13 (2) |

## Binding limits and rule

The staff and symbol detector and the `pdf_*.py` modules were searched for point thresholds. The limits that block this source at this stage are the first staff-line step (`15.0` pt) and filled vertical rectangle thickness (`1.5` pt). The paired horizontal rectangle limit (`1.0` pt) is also converted, although this source has no horizontal filled rectangles. On P25, the repeated notation step is `17.72` pt, and 18 narrow vertical rectangles are `2.83–2.84` pt wide; the old limits reject them. Two wider `8.86` pt rectangles remain glyphs. A source-measured long-horizontal step is available before rectangle classification; it is used for both stages. The new limits are `2.35`, `0.24`, and `0.16` times that step. At the largest working ordinary step (`6.38` pt), these give `14.99`, `1.53`, and `1.02` pt. At P25 they give `41.64`, `4.25`, and `2.84` pt. The 0.24 factor remains above the measured narrow barlines and below the wider filled bars at both scales. A page without a repeated source step cannot supply a scale and does not promote filled rectangles or a staff from this rule.

Other point bounds in `notation_omr/note_duration.py` are staff-line minimum length (`50` pt), merge gap (`20` pt), end tolerance (`3` pt), and line coincidence (`0.05` pt). The enlarged notation lines are over `2,200` pt long and share ends, so these bounds do not prevent its three notation staves. The `pdf_*.py` scan also found point bounds in geometry, diagnostics, arpeggio, text-label, and TAB alignment code. These do not gate this page's initial notation-staff or filled-barline classification. No such bound was broadened: after the three changes the target has 8 located bars, with remaining refusal at a located tuplet association rather than a scale threshold. Baseline and head staff counts in the table show the detector's non-regression across the other 29 PDFs; full GPIF comparison is reported separately in the PR evidence.

The public `tests/fixtures/pdf/scale_01` PDFs use the same generated five-line notation staff, six-line TAB staff, and two filled-rectangle barlines at `5.31` and `17.72` pt spaces. The large fixture fails to find a staff at the base; both scale variants pass the production extractor and barline reader with the new limits. They contain no private musical material.
