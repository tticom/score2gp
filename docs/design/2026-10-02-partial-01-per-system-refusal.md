# PARTIAL-01: refuse the one unboxed TAB system, not the whole file

## Problem

`build_ir_from_tabraw_only` refused a whole file with `pdf_only_tab_grouping_unsafe` as soon as any
layout warning was present, although the PDF-only route never reads TAB bar boxes: bars come from the
notation staff and each TAB digit is paired with a notation event by page, height and x
(`pdf_tab_bar_assembler.py`). The warnings only vouch for the TAB layout the digits were grouped in.
One system whose barlines fail the string-gap or strict-height tests blocked every other system.

## Rule (`src/score2gp/pdf_tab_system_partition.py`)

A TAB system is **readable** only if

- every one of its playable digits has a system, string, bar and x;
- neither its digits nor its system geometry carries an unsafe layout code (the same codes the whole-file
  gate uses);
- its barlines make at least two boxes (no `pdf_bar_box_too_narrow`, `..._outside_system_bounds`,
  `..._overlaps_neighbor`).

Any other system is **refused**, with the first matching code: `tab_system_unboxed`,
`tab_system_bar_boxes_invalid`, `tab_system_digit_unassigned_to_bar`,
`tab_system_digit_unassigned_to_string`, `tab_system_layout_warning`.

The file is written partially only if **all** of these hold; otherwise the whole file is refused as before
(same code, same `refusal_warning_code`):

1. exactly one system is refused and at least one is readable;
2. every unsafe warning of the file is located in the refused system (page and system), or is a code only
   candidate evidence can raise (the readable systems carry none); page-level codes such as
   `pdf_system_order_ambiguous` refuse the whole file;
3. each TAB system's digits sit under exactly one notation system, no two TAB systems share one, and the
   refused system's page has as many notation systems as TAB systems;
4. every notation bar of the refused system is read in full and adds up to its time signature. The bar
   count of the refused system numbers every later bar, and the notation is its only evidence.

## Effect

The refused system's digits are never read. Its notation bars are refused with the located code and
written empty (existing refused-bar mechanism), so numbering is the notation's own and the gap is explicit.
Nothing is written to another bar. Gates are unchanged: only what a refusal covers changed.

## Reporting (existing fields only)

- `note-type-route.json`: bars with `status: refused`, `reason` = system code, `location` (page, system,
  bar); `refused_tab_systems` and `summary.refused_tab_systems`.
- `score.warnings`: `pdf_partial_tab_system_refused` (page, system, digits).
- convert JSON report: `pdf_only_diagnostics.pdf_grouping_status = "partial"`,
  `conversion_complete = false`, `refused_tab_systems`. A complete conversion keeps `"safe"`.
