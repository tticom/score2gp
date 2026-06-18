# Task 175: Logical Clef Extraction Gap Diagnostic Report

## Command Run
`python scripts/diagnose_task175_extraction_gap.py`

## Extraction Gap Diagnostic Summary
```
=== Extraction Gap Diagnostic ===
staves_total: 17
no_left_margin: 2
staff_association_missing_or_malformed: 0
primitives_found_but_wrong_type: 6
primitives_found_but_malformed: 0
primitives_found_but_too_fragmented: 0
primitives_found_but_outside_staff_region: 5
primitives_found_but_ambiguous: 0
primitives_found_but_failing_classifier_thresholds: 4
treble_clef_candidate: 0
total_curves: 23
total_text_spans: 10
total_rectangles: 2
total_vertical_strokes: 17
total_horizontal_strokes: 1
```

## Conclusion
The logical clef evidence is lost across several distinct categories:
1. Primitives exist but have the wrong type (6 instances).
2. Primitives exist but are outside the strict staff region (5 instances).
3. Primitives fail the strict classifier thresholds (4 instances).
4. Complete absence of left margin candidates (2 instances).

No unbounded generic "treble clef candidate" is emitted, adhering to strict logical clef boundaries.
