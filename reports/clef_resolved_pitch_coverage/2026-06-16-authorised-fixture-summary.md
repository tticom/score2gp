# Clef-Resolved Pitch Coverage Analysis (2026-06-16)

## Corpus
- **Files processed:** 132 public fixtures from `tests/fixtures/pdf/`
- **Safety:** All files are anonymised generated public fixtures. No private PDFs, no copyrighted source names, no raw OCR dumps or sensitive data included.

## Aggregate Findings

| Metric | Count |
|--------|-------|
| Total Note Candidates | 14 |
| With Staff Position Index | 14 |
| On Staves with Valid Clef | 0 |
| Mapped to Pitch | 0 |
| In-Staff Mapped | 0 |
| Out-of-Staff Mapped | 0 |

### Skip Reasons
| Reason | Count |
|--------|-------|
| Missing Clef Evidence | 14 |
| Missing Required Ledger Support | 0 |
| Ambiguous Clef Evidence | 0 |
| Malformed Staff Association | 0 |
| Malformed Staff Position | 0 |

## Interpretation
The coverage analysis identifies **missing clef evidence** as the dominant blocker preventing note candidates from receiving a `clef_resolved_staff_pitch`.

## Recommendation
Based on empirical evidence, the next smallest safe product task is:
**Product Task 171 should bridge logical clef candidate evidence to fill in missing clefs.**
