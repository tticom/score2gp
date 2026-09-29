# MEM-01: IR provenance footprint

ScoreIR 0.1.1 stores a reference to a TabRaw candidate in event, note, and
candidate-warning provenance. The reference retains source stage, candidate id,
page, system, staff, bar, bbox, and confidence. The complete candidate is stored
once in `tab/tab_raw.json` and can be located by `candidates[].id`. MusicXML
provenance is unchanged. The old 0.1.0 IR shape, including populated `raw`
objects, still loads. The 0.1 schema family includes both contract versions.

## Consumer audit

Search scope: `git grep` over `src/`, `scripts/`, and `tests/` for
`provenance`, `raw`, `bbox`, `raw_token_id`, and the candidate grouping keys.

| Consumer | Fields used | Resolution |
| --- | --- | --- |
| `pdf_tab_event_factory.py` | candidate id and location on events and notes | Emits compact reference; grouping and duration evidence stays in TabRaw. |
| `build_ir.py` placement, symbol and technique attachment | id, page, system, staff, bar, x, y | Id and location retained; bbox centre supplies x/y, with a local id lookup into TabRaw when bbox is absent. The measured extracted fret candidates have centre coordinates equal to their bboxes. Direct `TabCandidate.raw` reads before IR creation remain unchanged. |
| `build_ir.py` MusicXML alignment | alignment strategy and pitch comparison | Small derived alignment fields remain in MusicXML-aligned note provenance; full TabRaw candidate is absent. |
| `build_ir.py` warnings and diagnostics | candidate id and bar | Retained. Direct `TabCandidate.raw` reads are unaffected. |
| `report.py` attachment map and diagnostics | provenance candidate id | Retained. Grouping diagnostics read `tab_raw.json` directly. |
| `gpif.py`, `gpif_builder.py`, `scoreir_compiler.py` | no candidate `raw` or grouping fields | Writer output is independent of the removed payload. |
| `scripts/` audits | TabRaw candidate data, not event/note provenance `raw` | Unchanged. |
| `tests/` | source location, candidate id, MusicXML derived fields | Retained. Event factory equality tests now compare compact references. |

Raw grouping fields (`bar_boxes`, `barline_candidates_details`, `fret_gaps`,
`duration_evidence`, assignment and grouping warnings, and related keys) are
read on `TabCandidate.raw` during extraction and IR assembly. No consumer reads
them from an event or note provenance after assembly. The report's own raw
candidate view comes from TabRaw. There is no implicit missing-value fallback
for a removed grouping field.

## Budget and measurement

The public `uneven_engraved_rows.pdf` baseline conversion wrote 355,429 IR
bytes for 3 bars (118,476 bytes/bar). The compact conversion wrote 27,042 bytes
for 3 bars (9,014 bytes/bar). The regression bound is 20,000 bytes/bar; the
new test was run against the exact base source and failed at 355,429 / 3.

For private measurements, the CLI ran with `--pdf-only-tab
--time-signature 4/4`, without a reference GP, using the product venv. An
in-process thread sampled `GetProcessMemoryInfo` / `PeakWorkingSetSize` every
50 ms. Wall time uses `time.perf_counter`. Each run has its own output directory
under `work/mem01/`. Counts and sizes only are recorded here; private artifacts
remain ignored under `work/`.

| Source | IR before | IR after | Reduction | Peak working set before | Peak after | Time before | Time after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Lesson 3 | 53,789,145 B | 1,285,220 B | 97.61% | 415,875,072 B | TBD | 17.72 s | TBD |
| Lesson 6 | 27,839,741 B | 715,982 B | 97.43% | 399,294,464 B | 390,852,608 B | 22.35 s | 24.02 s |

The GPIF oracle compares `Content/score.gpif` byte for byte on Lessons 3–7
and Can't Find My Way Home. GPIF equality also guards DUR-02 durations, rests,
strings, frets and techniques; OMIT-01 Key, OMIT-02 DoubleBar, OMIT-05
metadata/templates; and LAYOUT-01 SystemsLayout. Focused tests cover the
individual contracts.
