# PDF inspection resource budget (PERF-01)

The PDF-only converter refuses before retaining an inspection page that takes
the document above 2,000,000 expanded page-value nodes. Its code is
`pdf_resource_inspection_page_nodes_exceeded`; the JSON report and warning
include the 1-based page index, `inspection_page_nodes`, and `limit`.
This is a resource refusal, not a recognition decision. No geometry threshold,
grouping rule, duration rule, or GPIF writer changes.

## Reproduction and measurement

Product base: `7ff8c66cebf9fd147de5b64a59a4a4f867729b64`.
Assignment authority: AgentOps `d596e492e9362a3d961dbf77e01809868c4b81af`,
revision 135. The baseline source snapshot was compared byte for byte against
all 73 tracked `src/` files at that product revision: zero differences.

The workspace Windows host used its product `.venv/Scripts/python.exe`
(Python 3.12.13, PyMuPDF 1.28.2), with no sidecar, reference GP, template,
or remediation flag:

```text
python -m score2gp.cli convert --pdf <approved-private-PDF>
  --pdf-only-tab --time-signature 4/4 --out <ignored-work>/result.gp
  --work-dir <ignored-work>/conversion --json-report <ignored-work>/report.json
```

An in-process thread sampled `GetProcessMemoryInfo` every 50 ms. Wall time used
`time.perf_counter`; final process peaks use Windows `PeakWorkingSetSize`.
Stage samples used `WorkingSetSize` while the profiled functions were active.
Nested stage times are inclusive and must not be added to their parent times.
The notation/IR interval extends from extraction return to IR-builder return;
its memory figure is the maximum observed in its instrumented page operations,
not a separately reset Windows high-water counter. Final packaging/reporting is
the remaining terminal interval. All measurements include probe overhead.

Each conversion had a 600-second profile guard and a Windows Job Object hard
process-commit limit of 3.5 GiB (3,758,096,384 bytes). One conversion ran at a time.
The long Melodic Expressions baseline ran once. It did not finish: the profile
guard stopped it at 600.02 s, during the second notation traversal. Its process
peak was 2,757,787,648 bytes. This is a baseline timeout, not a product refusal.
No baseline GPIF or final refusal exists for that source.

The mounted set contained 42 PDFs, 11 `.gp` files and one `.gpx` file, rather
than the survey's older file count. All five prerequisite PDFs were present.
The PDF-only comparison covers every mounted PDF; GP packages are not PDF-only
conversion inputs. All 54 flattened private inputs match files byte for byte
in the clean sibling private checkout at
`0f9e11bfcdc5c37dc542191f450213f7fdb84200`
(`data/manifest-new-fixtures-2026-10-15`). No fixture was moved or modified.

## Where the work grows

Counts below come from the original sources and the base implementation.
Drawing items include curves; extracted strokes are the line/rectangle-edge
list produced by `pdf_geometry._drawing_segments`. Text tokens are PDF words.
Notation-route counts come from `extract_page_symbols` and `find_staves`.

| Source | Pages | Drawing items | Extracted strokes | PDF tokens | Inspection notation staves / TAB systems | Notation-route staves / TAB staves | Notation glyphs / segments / text tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Melodic Expressions | 34 | 272,854 | 64,238 | 5,417 | 178 / 173 | 178 / 178 | 17,739 / 18,527 / 4,918 |
| Chapter 19 | 2 | 14,719 | 3,693 | 471 | 9 / 9 | 9 / 9 | 1,043 / 1,415 / 429 |
| Lesson 6 | 6 | 12,839 | 6,400 | 1,289 | 34 / 34 | 34 / 34 | 1,147 / 3,645 / 1,143 |

| Stage / function | Melodic Expressions seconds / observed MB | Chapter 19 seconds / observed MB | Lesson 6 seconds / observed MB |
| --- | ---: | ---: | ---: |
| First `inspect_pdf` | 65.15 / 2,296.1 | 3.09 / 224.6 | 4.24 / 240.8 |
| `extract_tab` (includes repeated inspection and rows below) | 204.73 / 2,757.8 | 12.71 / 275.5 | 15.69 / 426.0 |
| Repeated `inspect_pdf` | 66.74 / 2,757.8 | 3.12 / 275.2 | 4.29 / 272.0 |
| `_extract_pdf_text_candidates` | 45.75 / 1,563.8 | 2.18 / 239.4 | 3.33 / 260.1 |
| `_write_grouping_artifacts` | 86.50 / 2,018.8 | 6.91 / 241.3 | 7.00 / 345.7 |
| Notation/IR interval | at least 329.47 / 1,782.1 | 23.49 / 281.3 | 10.93 / 395.3 |
| Final packaging/reporting | not reached | 1.53 / 416.9 | 2.54 / 655.8 |
| Whole conversion | timed out 600.02 / 2,757.8 | converted 41.49 / 416.9 | converted 34.08 / 655.8 |

MB is decimal. Sampling can miss short allocation spikes. The Windows process
high-water counter, which includes earlier stages, supplies these exact
additional bounds:

| Checkpoint | Melodic Expressions cumulative peak MB | Chapter 19 cumulative peak MB | Lesson 6 cumulative peak MB |
| --- | ---: | ---: | ---: |
| First inspection return | 2,296.1 | 248.3 | 240.8 |
| Extraction return | 2,757.8 | 297.4 | 469.9 |
| IR-builder return | not reached | 304.8 | 469.9 |
| Process end / profile guard | 2,757.8 | 416.9 | 655.8 |

Inspection builds `summary['pages']`, containing notation diagnostics, geometry
candidate dictionaries and semantic diagnostics. Each page's diagnostic copies
expand into JSON values even when they originated from the same geometry.
Expanded page nodes are 9,963,522 for Melodic Expressions, 581,458 for Chapter 19,
and 676,202 for Lesson 6. The first inspection string allocation alone takes
Melodic Expressions to 2.30 GB. Inspection is repeated inside extraction, with
both summaries live. Extracted candidate counts are respectively 5,864, 506 and
1,062. Inspection, repeated inspection and text extraction revisit the same
page/stroke/token populations listed above; they do not create additional input
pages. The candidate dictionaries retain further grouping evidence.

Time has several contributors. Samples repeatedly locate PDF text extraction
in `page.get_text('words')`. Grouping overlays repeatedly call MuPDF's
`pdf_count_q_balance` while appending drawing/text operations to page content.
Notation samples locate `_fill_ratio` / `_inside_fill`, traversing
`Glyph.shape.fill_edges`; the existing compatibility route repeats notation
reading. A staff-count-only explanation is insufficient: Melodic Expressions
has about 5.2 notation staves/page versus Lesson 6's 5.7, but far more drawing
items and expanded diagnostic values. The measured memory spike follows the
retained diagnostic expansion and whole-document serialization; overlay and
notation time also depend on page content and glyph contour work.

Large baseline artifacts, left unchanged by this task's implementation:

| Artifact | Bytes |
| --- | ---: |
| First inspection JSON | 378,901,499 |
| Repeated inspection JSON | 378,901,669 |
| TabRaw JSON | 217,104,536 |
| Grouping diagnostics HTML | 14,935,681 |
| Baseline conversion work directory at timeout | 1,006,557,590 |

MEM-02 report payloads and MEM-03 work-directory policy remain separate work.
The baseline never reached its final conversion report.

## Gate and its limits

`inspection_page_nodes` in `pdf_resource_budget.py` counts each JSON-compatible
container and scalar value occurrence, excluding dictionary keys. Shared
references are charged repeatedly because JSON expands them repeatedly. It
visits each page once in O(N) time, without creating a JSON string. The running
total resets for each inspection invocation; the second inspection is not
incorrectly charged against the first.

`inspect_pdf` checks the cumulative count before appending each completed page
to `summary['pages']`. `convert` catches the dedicated exception and writes a
located refusal before extraction, IR generation or GP writing. Accepted
documents retain the original objects and output paths unchanged. The old path
retained O(N) expanded data and allocated its document-sized JSON string with
no resource boundary. The new path stops document retention at L = 2,000,000
nodes, plus the current page's transient data; it never serializes an
over-budget document. This is a measured corpus boundary, not a universal bound
on an arbitrarily complex single page or all later recognition algorithms.

The largest other mounted document has 717,711 total inspection nodes (Lesson
7), including eight document-envelope nodes. All 20 converting documents and
all 21 existing refusals are below the limit. The 2,000,000-page-node limit is
2.79 times the largest accepted page-node population and below the target's
9,963,522 page nodes. Page count and PDF file size are not limits: both large
books keep their existing processing and refusal paths.

Melodic Expressions first exceeds the bound at page 10, with 2,060,433 nodes.
An independent recursive walk of the base inspection JSON confirms that exact
prefix count. The changed CLI refuses in 10.68 s with peak working set
220,205,056 bytes, exit 1, stage `pdf-inspection`, and the code above. No GPIF,
TabRaw, or document inspection JSON is generated. Its partial conversion work
directory is 1,638,202 bytes. The first ten source pages contain 50 candidate
notation staves, 15,185 extracted strokes and 2,132 PDF words. These partial
artifacts remain ignored; their reduction follows early refusal, not a work
directory cleanup change.

## Regression evidence

`test_perf_01_private.py` reaches the real page-10 inspection seam and asserts
the exact source-derived count, page, code, warning, report and absence of
later-stage outputs. A mutant making the budget check a no-op is rejected on
the same source at the first over-budget checkpoint. The test monitor stops
that mutant before it can allocate the multi-GB baseline string; it does not
rerun the long baseline conversion.

Lesson 6 and Chapter 19 assert their unchanged inspection counts and native
CLI GPIF SHA-256 against fresh base conversions. These controls use CLI
subprocesses because the pre-existing `gpif.build_gpif` pytest branch emits a
different format when pytest is loaded. That writer behavior is unchanged.
Private tests use `TemporaryDirectory` under repository `work/`.

The public container-growth test is non-domain infrastructure only: n and 2n
repeated containers charge 5,001 and 10,001 nodes, ratio below 2. It is the only
way to exercise growth in public CI without private input; it makes no
recognition, grouping, geometry, timing or fidelity claim and carries no domain
acceptance weight. GPIF equality proves preservation, not that pre-existing
recognition is musically correct.

<!-- corpus-results -->

## Whole mounted PDF set

The 20 base successes retain byte-identical `Content/score.gpif`; all 21
existing refusals retain their codes. The only changed status is Melodic
Expressions: profile timeout to the located inspection resource refusal.

Timing tolerance is max(2 seconds, 15% of base), conservatively allowing
process startup and shared-host variation. Repeated frozen-base runs of
Am-blues-lick took 2.264, 2.167 and 2.162 s (0.102 s / 4.5% spread);
Lesson 6 took 34.078 and 34.486 s (0.408 s / 1.2% spread). This operational
tolerance is wider than those observed control spreads; it is not a
statistical confidence interval. No measured file exceeds it. Measurements
are single paired runs per file except those calibration controls.

Times are seconds; peaks are decimal MB. `same` means byte-identical GPIF.
A single refusal code in a row applies at both base and head.

| PDF | Base s | Head s | Base peak MB | Head peak MB | Result / GPIF |
| --- | ---: | ---: | ---: | ---: | --- |
| 12 Bar Blues Solo Guitar Jam.pdf | 8.74 | 8.76 | 296.4 | 291.3 | `pdf_only_tab_no_notation_bars` |
| 5 MUST KNOW Pentatonic Licks In Em.pdf | 3.10 | 3.06 | 125.4 | 126.0 | `pdf_only_tab_no_notation_bars` |
| 5_Grateful_Dead_Intros.pdf | 1.52 | 1.54 | 108.6 | 109.8 | `pdf_only_tab_grouping_unsafe` |
| 7_Grateful_Dead_Melodies.pdf | 4.45 | 4.53 | 131.7 | 130.8 | `pdf_only_tab_no_notation_bars` |
| A7-Blues-Lick.pdf | 2.83 | 2.75 | 130.3 | 131.2 | converted / same |
| A_blues_lick_5_positions.pdf | 10.42 | 10.47 | 138.1 | 137.6 | converted / same |
| Am-blues-lick.pdf | 2.26 | 2.20 | 110.3 | 110.5 | converted / same |
| Back In Black.pdf | 2.99 | 2.95 | 169.6 | 169.5 | `pdf_only_tab_grouping_unsafe` |
| Bebop Licks in Am.pdf | 13.65 | 13.31 | 221.3 | 225.1 | converted / same |
| Black Dog.pdf | 4.06 | 3.92 | 176.7 | 177.2 | `pdf_only_tab_grouping_unsafe` |
| Brown Sugar.pdf | 2.53 | 2.53 | 143.6 | 144.2 | `pdf_only_tab_grouping_unsafe` |
| Can't Find My Way Home (open chord shenanigans).pdf | 21.18 | 21.02 | 314.8 | 312.1 | converted / same |
| Castles Made of Sand.pdf | 3.95 | 3.97 | 209.4 | 209.0 | `pdf_only_tab_grouping_unsafe` |
| Combining_Maj_minor_pent_-_A.pdf | 5.87 | 5.78 | 129.0 | 129.1 | `pdf_only_tab_no_bar_written` |
| Crossroads.pdf | 8.41 | 8.40 | 312.4 | 311.7 | `pdf_only_tab_grouping_unsafe` |
| Derek Trucks BB King.pdf | 15.89 | 15.74 | 239.6 | 238.9 | `pdf_only_tab_no_bar_written` |
| E_Chord_Lick_Chord.pdf | 16.09 | 15.65 | 197.9 | 195.2 | converted / same |
| Ex 2 Hands Up.pdf | 5.12 | 4.92 | 160.6 | 159.6 | converted / same |
| Finger postition tips TAB.pdf | 3.55 | 3.54 | 132.7 | 132.4 | `pdf_only_tab_no_notation_bars` |
| G-Am-C-Lick.pdf | 7.30 | 7.17 | 209.4 | 209.3 | converted / same |
| Gloria.pdf | 5.21 | 5.17 | 147.8 | 148.5 | converted / same |
| Hal Leonard Corporation. Rock Ballads.pdf | 103.29 | 103.26 | 363.6 | 362.0 | `pdf_only_tab_grouping_unsafe` |
| Heartbreaker.pdf | 2.07 | 2.11 | 116.0 | 115.8 | `pdf_only_tab_grouping_unsafe` |
| Hey Joe.pdf | 3.72 | 3.68 | 174.5 | 174.4 | `pdf_only_tab_grouping_unsafe` |
| Jazz Classics for Solo Guitar- Chord Melody Arrangements.pdf | 207.17 | 206.32 | 386.3 | 386.7 | `pdf_only_tab_grouping_unsafe` |
| Just-Practice-Like-THIS-Every-Day.pdf | 6.65 | 6.58 | 145.6 | 144.3 | converted / same |
| LegatoLicks.pdf | 1.01 | 0.93 | 103.1 | 102.5 | `pdf_only_tab_grouping_unsafe` |
| Lesson-3.pdf | 25.81 | 25.63 | 397.2 | 397.4 | converted / same |
| Lesson-4.pdf | 31.28 | 32.06 | 445.9 | 450.7 | converted / same |
| Lesson-5.pdf | 19.94 | 20.44 | 580.9 | 581.1 | converted / same |
| Lesson-6.pdf | 34.08 | 34.29 | 655.8 | 654.8 | converted / same |
| Lesson-7.pdf | 28.59 | 29.01 | 512.8 | 514.2 | converted / same |
| Lick in All 5 CAGED Shapes start on the 5 _ guitar tab creator.pdf | 1.20 | 1.21 | 94.7 | 95.2 | `pdf_only_tab_grouping_unsafe` |
| Melodic Soloing Masterclass.pdf | 7.16 | 7.35 | 329.6 | 329.6 | converted / same |
| Melodic_Expressions.pdf | 600.02 | 10.68 | 2757.8 | 220.2 | timeout → `pdf_resource_inspection_page_nodes_exceeded` (page 10) |
| Melodic_Expressions_Chap_19_.pdf | 41.49 | 40.82 | 416.9 | 415.8 | converted / same |
| Mixing Lead & Rhythm pt1.pdf | 50.36 | 49.58 | 449.8 | 449.2 | `pdf_only_tab_grouping_unsafe` |
| PARANOID - BLACK SABBATH.pdf | 1.77 | 1.74 | 97.0 | 97.2 | `pdf_only_tab_grouping_unsafe` |
| Pride and Joy.pdf | 3.40 | 3.27 | 175.4 | 174.7 | `pdf_only_tab_grouping_unsafe` |
| Tasty_A_Major_Lick.pdf | 1.73 | 1.62 | 109.2 | 108.8 | converted / same |
| The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord.pdf | 20.08 | 20.04 | 266.9 | 268.0 | converted / same |
| This_039_Boring_039_Scale_Exercise_Will_Save_You_Years_But_Most_Skip_This_.pdf | 10.63 | 10.55 | 233.5 | 233.2 | converted / same |

<!-- validation-results -->
