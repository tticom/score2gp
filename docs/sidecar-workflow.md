# Sidecar Acquisition Workflow

This document details how to prepare, name, and pair input files and sidecars for conversion in the `score2gp` pipeline.

## Sidecar Pairing and Naming Convention

To convert a vector guitar PDF score, you must acquire or author a matching MusicXML sidecar that contains the notation and timing details.

### Local Discovery Pairing
For private local testing and diagnostic script runs, files should be placed in `fixtures/private/` with matching base names:
* **PDF File**: `fixtures/private/<Song Name>.pdf`
* **MusicXML File**: `fixtures/private/<Song Name>.<extension>` (where `<extension>` is `.mxl`, `.musicxml`, or `.xml`)

The diagnostic smoke runner (`scripts/private_e2e_smoke.py`) automatically scans `fixtures/private/` and pairs matching filenames.

### CLI Workflows
For direct CLI conversions, paths are explicitly mapped using the `--musicxml` argument:
```bash
python -m score2gp.cli build-ir \
  --pdf-tabraw "work/song/tab_raw.json" \
  --musicxml "fixtures/private/song.xml" \
  --out "work/song/score.ir.json"
```

---

## Validation Before Build-IR

Before any alignment or ScoreIR building is performed, the pipeline validates the inputs.

1. **Geometry Grouping Preflight**: The tab extractor verifies that fret numbers can be assigned to a six-line staff and associated with detected barlines.
2. **MusicXML Timing Preflight**: The XML parser simulates a voice cursor timeline for every voice and measure in the file. If timing risks (overlaps, overflows, cursor drift) are found, the run is refused.

---

## Refusal Wording and Troubleshooting Guidance

When a file pair fails validation, the error codes guide the user on the next corrective action:

* **If the MusicXML is missing**: The system exits with `missing_musicxml`.
  * *Guidance/Corrective Action*: Provide a matching MusicXML sidecar before attempting `build-ir`.
* **If the PDF has no selectable text/vector lines (scanned/raster)**: The system exits with `pdf_tab_staff_missing` or `pdf_no_systems_detected`.
  * *Guidance/Corrective Action*: Provide an extractable digital/vector PDF generated directly from a notation editor.
* **If the MusicXML has polyphony/timing risks**: The system exits with `invalid_timing_refused` or `unsupported_polyphony_refused`.
  * *Guidance/Corrective Action*: Simplify the notation voices in the source sheet (e.g. merge overlapping voices, fix measure duration errors) and export a clean MusicXML file.

---

## Future ASCII Alignment Sidecars

For ASCII text PDFs (where guitar tabs are represented by text character rows), the pipeline supports pairing the extracted text rows with a MusicXML sidecar using an intermediate alignment map (`ascii_musicxml_alignment.json`). 
* The alignment map maps character column spans to specific onset ticks in the MusicXML score.
* Currently, the ASCII alignment pathway is restricted to controlled monophonic test cases. Broad automated conversion of arbitrary ASCII tabs remains an area of future development and is not supported in this release.
