# PDFG-01: ledger topology repair and located unsupported TAB groups

Counts and labels only. Base: `9f539a03a6994984941e174fc2c19545364a6b60`.

## Measurement before repair

| Source | Pages | Physical systems / TAB groups | Notation bars | First refusal |
|---|---:|---:|---:|---|
| Mixing Lead & Rhythm pt1 | 4 | 23 / 23 (5, 6, 6, 6 per page) | 46 | `ambiguous_bar_assignment` |
| PARANOID - BLACK SABBATH | 3 | 15 / 15 (5, 6, 4 per page) | 0 | `pdf_no_systems_detected` |

Mixing's legacy detector produces 28 topologies, including five false groups on
page 4; only 23 groups carry playable digits. Five genuine systems on that page
(legacy system labels 2, 4, 6, 8, 11) fail assignment, affecting ten notation bars.
One has no accepted barline; four have only two instead of three. Of their 128
digits, 91 lack a bar assignment. The other 447 digits have complete assignment.
With those five systems' digits withheld, the unchanged bar assembler writes 35
of the other 36 bars; one has an unread duration. This diagnostic counterfactual
does not authorize writing any unsafe group's digits.

PARANOID's long-primitive route finds only seven six-line hypotheses (2, 5, 0 per
page). Their measured step is 8.42 pt, excluded by the accepted TAB spacing bands.
All are classified `ambiguous` and none becomes an accepted TAB system. Recovering
short drawn pieces for inspection locates 15 physical groups, covering 54 engraved
bars (14, 24, 16 per page, including two tie-only bars). Page rendering and the
full-height barline intervals agree. There are no five-line notation systems and
no notation-duration bars. Narrowing the grouping refusal alone can therefore
write zero bars with this route.

## Cause and repair

`_tab_line_groups` greedily searches for six equally spaced rows before five-line
staves. On Mixing page 4, short ledger-line runs satisfy that search together
with actual notation rows. `classify_staff_line_group` labels four such groups
`rejected` and one `tab`. `_detect_tab_systems` nevertheless gives the rejected
groups topologies too. Its primitive ownership lock sees competing topologies
and withholds real full-height barlines from the genuine TAB groups. These
produce the unsafe warning found by `build_ir_from_tabraw_only`; the existing
`partition_tab_systems` cannot isolate five failures as its one-system case.

`notation_anchored_line_groups` uses the existing independent `find_staves`
geometry: five drawn rows, uniform spacing, common ends, and minimum painted
coverage. When a legacy six-row hypothesis consumes these notation rows, the
notation rows are reserved before the TAB search. The anchors retain actual
horizontal primitives. No row, barline, fret, duration, or bracket is invented.
The repair restores six genuine page-4 TAB groups, each with three accepted
barlines. All 23 systems then have complete grouping. No PDF-GROUP-02 merge
constant, grouping warning gate, barline acceptance gate, or PARTIAL-01 condition
changes.

PARANOID has two independent limitations. `_LineSegment.is_horizontal` requires
a 75 pt primitive, dropping digit-interrupted pieces; the classifier also
excludes the measured staff step. More importantly, `read_note_durations` reads
notation above TAB, whereas this source prints rhythm directly on TAB. Accepting
its grouping alone would still provide no supported timing. This task keeps the
existing refusal. `locate_unclassified_tab_groups` joins pieces longer than the
page's measured staff step **only to locate refusals**. A location requires six
uniform drawn rows, numeric text, a full-height vertical, and the unchanged
classifier's ambiguous verdict. It never authorizes assignments or output.

Each of the 15 groups is reported with page/system indices, bounding box,
`tab_group_staff_spacing_unclassified`, and
`tab_group_without_notation_timing`. These records reach both `diagnostics.json`
and the convert JSON report's `pdf_only_diagnostics.located_grouping_refusals`.
There is no inferred source-to-output bar ordinal for this unsupported timing
layout.

## Observable outcome and limits

Mixing writes 45 of 46 bars, with zero unplaced digits; bar 4 remains empty with
`note_duration_event_unread` (page index 0, notation system index 1, event index 1).
The 575 playable digit candidates retain complete string/bar assignment. This
is partial conversion, not a musical-fidelity claim.

The matching reference GP is a readable ZIP container, but its
`Content/score.gpif` entry is 90,576 bytes and is not XML: the stdlib XML parser
raises `ParseError: not well-formed (invalid token): line 1, column 0`. No notes,
counts, thresholds or timing were taken from that payload. Reference fidelity
is unproven. PARANOID has no matching reference GP in the mounted corpus.

`tests/test_pdfg_01_private.py` invokes the normal convert entrypoint in a
`TemporaryDirectory` under repository `work`. Mixing asserts the group counts,
all assignments, three barlines per group, bar counts, and the retained refusal.
PARANOID asserts no output, the original refusal, 15 separate group locations,
both located codes, and publication through the final JSON report.

The wrong implementations rejected are:

* restore the old ledger topology and consequent blanket refusal: Mixing fails
  its output assertion;
* accept the unsupported six-line spacing band: PARANOID fails its unchanged
  layout-refusal assertion (the unsupported timing route is reached instead);
* merge the first two physical refusal groups into one: PARANOID fails its exact
  page/system location assertion.

The existing PDF-GROUP-02 and PARTIAL-01 tests remain unchanged. No synthetic
fixture provides acceptance evidence for this change.

Common-ended six-row groups return unchanged before text/font extraction. This
preserves the existing geometry-only page interface. Comparing this fast path
with the initial repair on every page of all 42 approved PDFs (395 pages) gives
identical grouping primitives and order.

## Corpus preservation

Base/head conversion measurements cover all 42 mounted PDFs, with declared
4/4 and no reference or MusicXML sidecar. All 20 previously generated
`Content/score.gpif` payloads are byte-identical, preserving 641 indexed bars,
including 586 written bars. Mixing is the only exit-status/output change; all
other 41 sources retain their previous conversion status. A7-Blues-Lick is the
third-source control: its GPIF remains byte-identical.

The tracked runner makes the comparison reproducible. `<base-src>` is the
directory containing the `score2gp` package at the recorded base SHA:

```text
python tests/pdfg_01_corpus_probe.py --module-root <base-src> --out work/pdfg01-base.json
python tests/pdfg_01_corpus_probe.py --baseline work/pdfg01-base.json --out work/pdfg01-head.json
```

Every conversion uses `TemporaryDirectory` under repository `work`; only
counts, labels, codes, timings and GPIF hashes are retained. The comparator
rejects any changed previously written GPIF. An in-memory changed-hash negative
control is rejected; this checks comparison infrastructure, not musical
recognition, whose acceptance evidence remains the real-source tests above.
