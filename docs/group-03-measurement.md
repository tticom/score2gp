# GROUP-03 measurement: the sources still refused at TAB grouping

Normal CLI (`convert --pdf-only-tab`) over every approved PDF (43 `*.pdf` in `fixtures/private/`), `main` at a2fc60c vs this branch. Counts, codes and labels only; no private content.

## Before (re-measured)

Bars written 1416 over 38 converting sources. Refused before any bar exists: five sources. Four end in `pdf_only_tab_grouping_unsafe` (the task's four); the fifth (`5_Grateful_Dead_Intros`, `pdf_only_tab_no_notation_bars`) is another code and out of scope.

| source | pages | refusal check (`build_ir.py`, `build_ir_from_tabraw_only`) | blocking geometry | class |
|---|---|---|---|---|
| Rock Ballads (scanned book) | 177 | `if not tabraw.candidates ...` "no candidates found in TabRaw" (`pdf_input_class_scanned_pdf_unsupported`) | 0 drawings, 1 image/page, 0 words: no vector barline, line or digit exists | reader gap (raster reader; RASTER-00, DEC-01) |
| Jazz Classics (scanned book) | 105 | same | same | reader gap |
| LegatoLicks (hand-drawn page) | 1 | `unsafe_warning_codes` hit `pdf_no_systems_detected` | 0 drawings, 1 image; the 80-word text layer is scan noise: 13 candidates, 0 fret, 0 string | reader gap (raster reader) |
| CAGED (web-rendered ASCII TAB) | 1 | same, `pdf_no_systems_detected` | 3 six-row monospace blocks, 54 fret candidates grouped to strings, **0 bar separators, no rhythm mark** (`ascii_timing_status: timing_unavailable`) | representation/reader gap: bar boundaries and durations are not on the page; writing them is a guess |

Causes ranked by affected sources: raster, no vector evidence (3); ASCII rows with no bar boundary or rhythm (1). Per-bar located reasons do not exist for these (no bar is formed), so the located reason is per source.

## Finding

No grouping rule can resolve any of the four: for three there is no vector geometry to group and for the fourth the rows are grouped by string already but carry no barline or rhythm. Loosening the safety check, or inventing bars (e.g. cutting the ASCII rows into measures by width) and durations, is exactly the symptom-masking the recovery design rejects. Nothing is written; no bar is newly written; this is **unfinished work**, not a correct refusal.

## Change (`build_ir.py`)

`_ungrouped_source_details` adds a located cause to the refusal of the two sources that had only the warning code: `ascii_tab_rows_without_barlines_or_rhythm` (block, candidate and separator counts) for CAGED, `text_without_tab_rows` for LegatoLicks. Diagnostics only; no gate, tolerance or output changed.

## After

Exit codes identical for all 43 sources; bars written 1416 -> 1416; bars refused by code unchanged (132 `note_duration_event_unread`, 54 `notation_note_without_tab_digit`, 20 `bar_without_notation_event`, 10 `bar_total_mismatch`, 10 `notehead_digit_count_mismatch`, 2 `tie_head_ownership_unconfirmed`, 2 `tab_system_digit_unassigned_to_bar`, 2 `tab_digit_without_notation_event`, 1 each `duration_off_tick_grid`, `notation_tab_column_ambiguous`, `tab_chord_arrow_unread`). Inner `Content/score.gpif`: 38 of 38 converting sources byte-identical. No bar newly written, so none to verify against a reference or the page; no holdout read applies (no reader was added).

Verification: located counts for CAGED were checked against the printed page text (three six-row blocks, no `|` separator). None of the four sources has a reference: not independently verified.
