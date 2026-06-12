## Task 87 — Integrate whole-note candidate diagnostics into normal diagnostics flow

### Description
This PR integrates the whole-note candidate diagnostics into the existing standard geometric diagnostics structure (`PdfStaffNotationGeometryDiagnostics` via `extract_notation_diagnostics_dict`) and exposes it through `scripts/raster_diagnostics_gate_report.py`. 

### Changes
*   Added `WholeNoteCandidateDiagnostics` to `src/score2gp/pdf_staff_geometry.py`.
*   Extracted the standalone stem-exclusion and bounding box logic into `_extract_whole_note_candidates` within `src/score2gp/pdf_staff_notation_diagnostics.py`.
*   Integrated `whole_note_candidates` into `PdfStaffNotationGeometryDiagnostics`.
*   Refactored `scripts/whole_note_diagnostics_report.py` to use the shared geometry diagnostics pipeline instead of duplicate ad-hoc paths.
*   Updated `scripts/raster_diagnostics_gate_report.py` to also output `whole_note_candidate` counts directly in its JSON output and human-readable output to satisfy normal diagnostic run visibility.
*   Fixed a mock test environment issue where `rect.width` caused failures by making `rect` width calculations robust to both `tuple` and `fitz.Rect` properties.
*   Regenerated the JSON schema snapshot tests with the newly added model fields.

### Verification
*   Passed `pytest tests/test_whole_note_diagnostics_report.py` ensuring positive coverage, negative noise coverage, and half-note negative coverage operate correctly.
*   Passed `pytest tests/test_raster_diagnostics_gate_report.py` and `pytest tests/test_pdf_standard_staff_diagnostics_fixtures.py`.
*   Maintained the half-note exclusion boundary constraint as mandated by Task 86.
*   Ensured NO ScoreIR output, NO semantic promotion, and NO OCR. All candidate extractions are pure geometric representations without side-effects on existing pipelines.

### Codex Comment Disposition Requirement
(For the reviewer) Please ensure that the review formally includes a **Codex comment disposition** section listing any automated feedback, categorising it (Accepted/Rejected/Fixed), and providing reasoning per governance rules.
