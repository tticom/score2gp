# Conversion report

`convert` writes `conversion-report.html` in the requested work directory for
completed conversions and refusals that reach HTML reporting. Early inspection
budget refusals retain their JSON diagnostics without an HTML report. Warnings,
provenance, extraction data, build results, and write results remain available
in reports that are written.

By default, the repeated `barline_candidates_details` lists are replaced by
`barline_candidate_summary`. Each detected staff system is counted once,
using its page, system index, and staff bounding box. Rejected candidates are
counted by reason, with at most three examples per reason across the document.
Each example includes its page, system, staff bounds, and candidate geometry.
Accepted candidate details are retained once per staff system.

To include the original full candidate lists in the HTML summary, explicitly
add `--debug-barline-candidates` to `convert`. This can produce a very large
report. The option affects HTML rendering only; extraction artifacts, refusal
decisions, ScoreIR, and GP output are unaffected.

The private-source report regression checks the normal CLI for every mounted
PDF. Its size allowance is the report's unchanged content plus 512,000 bytes
for the deduplicated accepted geometry, rejection counts, and located examples.
Each report must also remain below 41,000,000 bytes for this corpus.
The test checks counts against the captured original renderer input, bounds the examples,
compares all other summary fields and HTML sections, and exercises the debug
flag on a real source.

## Work-directory footprint (MEM-03)

`convert` inspects the PDF once: `inspect/inspect_pdf.json` and
`inspect/pages/` are the only copy, and the extraction stage reuses that result
rather than inspecting and rendering the pages again under `tab/inspect/`.
(`extract-tab` run on its own still inspects into its own output directory.)

The grouping overlay PNGs, `grouping-diagnostics.html` and the
`pdf-edge-boundary-report.*` files under `tab/` are written only when
`--diagnostic-artifacts` is added to `convert`. TabRaw, the conversion report
and the GP output are identical with or without it. The `diagnostics.json`
sidecar names these files only when they exist.

`tests/test_mem_03_workdir_footprint.py` converts approved private sources and
bounds the bytes written per bar and the peak working set of the conversion.
