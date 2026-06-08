# Standard-Staff Fixture Expansion Plan

## 1. Context and Objective
Following the implementation of standard-staff diagnostics (PR #192 primitive clustering, PR #193 left-margin density), the project has gained robust standard-staff geometric extraction capabilities. However, our current public fixture test suite (`tests/fixtures/pdf/`) leans heavily toward tablature (`generated_pdf_*.pdf`) or paired notation-tab systems. 
To validate our standard-staff pipelines against complex edge cases (large overlapping clusters, dense accidentals, multiple voices, clef changes) without violating privacy boundaries by using real-world copyrighted PDFs, we must expand our synthetic, generative fixtures.

## 2. Identified Coverage Gaps
The current generative scripts (e.g. `make_paired_notation_tab_system_pdfs.py`) only render simple notation geometries (stems and 5-lines). They do not adequately model:
1. **Left-Margin Density Variants**: Extreme variations in left-margin symbols (e.g., dense key signatures with multiple accidentals, complex time signatures).
2. **Dense Primitive Clusters**: Multi-voice clusters with noteheads, accidentals, and ledger lines densely packed together sharing X-coordinates.
3. **Wide Curves (Ties/Slurs)**: Broad bezier curves or lines spanning across multiple stems, testing the `wide_curve` primitive behavior.
4. **Articulations/Text**: Extensive geometry above/below the 5-line staff that could interfere with staff bounding boxes or primitive clustering.

## 3. Proposed Generative Approach
We will continue the established pattern: a JSON specification file parsed by a Python script (`fitz`-based) to draw synthetic geometries.

### Proposed Script: `make_standard_staff_diagnostics_pdfs.py`
This script will consume JSON definitions specific to standard-staff edge cases.

### Proposed JSON Schema Additions
To support the missing features, the JSON specification for our new fixtures should be expanded to include:
* `margin_text_clusters`: Array of `{"text": "b", "x": 50, "y": 100, "fontsize": 18, "fontname": "helv"}` to simulate dense key signatures without semantic rules.
* `note_clusters`: Grouped primitives representing complex chords.
  * `stems`: Array of `{"x": ..., "y_min": ..., "y_max": ...}`
  * `noteheads`: Simulated as text or small filled circles/rectangles.
  * `accidentals`: Simulated as text or path primitives.
* `wide_curves`: Array of `{"p0": [x,y], "p1": [x,y], "p2": [x,y], "p3": [x,y], "width": 0.5}` to draw bezier curves simulating slurs/ties.

## 4. Planned Fixtures
We propose creating the following specific JSON fixtures in `tests/fixtures/public/` and compiling them to PDFs:
1. `generated_standard_staff_dense_margin.json`: Tests the left-margin density threshold logic against an oversized, dense left margin.
2. `generated_standard_staff_complex_cluster.json`: Tests primitive clustering when multiple voices and accidentals share an X-coordinate.
3. `generated_standard_staff_wide_curves.json`: Evaluates whether ties/slurs correctly fall outside the staff's standard primitive grouping without breaking the system alignment.
4. `generated_standard_staff_sparse.json`: A minimalist staff with almost no primitives, to test fallback thresholds.

## 5. Implementation Steps
1. Create the proposed `.json` files in `tests/fixtures/public/`.
2. Author `tests/fixtures/pdf/make_standard_staff_diagnostics_pdfs.py` to parse these new JSON schemas and use `fitz` to render them into PDFs.
3. Add corresponding unit tests in `tests/` that load these new PDFs and assert the `NotationStaffDiagnostics` outputs (e.g., verifying `left_margin.curve_candidate_count` correctly counts the dense margin).
4. Do not include any pitch/clef semantic logic; all assertions must remain strictly geometric, preserving the semantic firewall.

## 6. Privacy & Architecture Adherence
* **Privacy**: 100% compliant. All fixtures will be algorithmically generated, containing no copyrighted musical content.
* **Architecture**: Compliant. The fixtures will only be used to validate the output of the geometry-focused `NotationStaffDiagnostics` module, asserting primitive counts, cluster bounds, and margin thresholds.
