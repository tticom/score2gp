# Slide marks (SLIDE-01)

A slide on a TAB staff is read from the **drawn mark**, never from a default. The reader lives in
`src/score2gp/pdf_slide_marks.py`; `pdf.py: _slide_mark_candidates` turns each reading into a
`visual-slide` TabRaw candidate; `build_ir.py` writes the slide, or a located diagnostic.

## Reading rules

A diagonal stroke is a slide mark only if one of its ends touches a TAB fret digit (the same binding
tolerance the leading-slide reader always used: within half a digit width, at the digit's height).

| Drawn mark | Written as | GPIF `Slide` flags |
| --- | --- | --- |
| stroke ends at a digit, no digit before it in the system | slide-in (`up`/`down`) | 16 / 32 |
| stroke joins two digits on one string, a slur arc spans both | legato | 2 |
| stroke joins two digits on one string, no arc spans both | shift | 1 |

Anything else is **refused**: no slide technique is written and a diagnostic is reported.

## Diagnostic

`slide_mark_not_extracted` (warning, in the conversion report `warnings.json` and `ScoreIR.warnings`).
It is located by page, system and bar (the provenance) and the message states the reason code and the
run status `slide_not_written`.

| Reason code | Meaning |
| --- | --- |
| `slide_endpoint_not_bound_to_digit` | one end of the stroke touches no digit, or the end touches two |
| `slide_endpoints_on_different_strings` | the two bound digits are on different strings |
| `slide_endpoints_in_different_bars` | the two bound digits are in different bars (cross-bar slide) |
| `slide_slur_evidence_ambiguous` | more than one slur arc spans the pair, so legato/shift is undecidable |
| `slide_endpoint_note_not_found` | a bound digit has no note in the bar (or the pair is not in time order) |
| `slide_type_not_read` | a bare diagonal (slope/direction only) names no type |
| `slide_label_without_drawn_mark` | a printed `sl.` label has no drawn stroke under it |

A printed `sl.` label alone never writes a slide: it does not say which slide it is.

## Known limits

* Slide-out and cross-bar slides are refused (reported), not written.
* MusicXML-sourced slides carry no drawn evidence; that path is unchanged.
