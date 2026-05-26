# Handoff

## Metadata

- **Current Branch**: `feature/gpif-system-breaks-and-staff-scaling-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft PR created on origin
- **Latest Local Commit**: `26b8048f760df768f7422961d28389c9223f6687` ("feat: implement system breaks, staff scaling, and hidden/dashed barlines")
- **Latest Pushed Commit**: `26b8048f760df768f7422961d28389c9223f6687` ("feat: implement system breaks, staff scaling, and hidden/dashed barlines")

- **Working Tree Status**: Clean.

- **GitHub Check Status**: Pending.
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. No root generated artifacts tracked.

## Tests And Checks Run

- `python -m pytest` -> 382 passed (100% success, including the new unit test file `tests/test_system_breaks.py` asserting visual breaks, staff-system layout distancing, and custom hidden/dashed barlines).
- `python -m score2gp.cli export-schema --out schemas` -> passed cleanly and updated intermediate schemas.
- `python -m score2gp.cli validate-ir fixtures/public/test_system_breaks.ir.json` -> valid and fully compliant.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed cleanly.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `python scripts/private_e2e_smoke.py` -> passed cleanly against all private PDF inputs (including derek trucks, hal leonard, jazz classics, CAGEDShapes, etc., and `fixtures/private/Lesson-7.pdf`) with zero regressions.

## What Changed In This Task

- **Model & Schema Validation Support (`src/score2gp/ir.py`)**:
  - Defined Pydantic models `SystemLayout` (with `system_size_percent`, `staff_distancing_cushion`, `barline_style`) and `StaffLayout` (with `staff_spacing_cushion`, `staff_size`).
  - Added `system_layout` and `staff_layout` optional fields to `ScoreLayout`.
  - Expanded `Bar`'s `barline` literal choices to include `"hidden"` and `"dashed"`.
  - Re-exported the schema via the CLI schema exporter: `schemas/scoreir.v0.1.schema.json`.
- **GPIF Formatting Mappings (`src/score2gp/gpif.py`)**:
  - Implemented `<SystemLayout>` and `<StaffLayout>` elements serialization under `<Layout>` under `<Score>` inside `build_gpif()`.
  - Added serialization of `<LayoutBreak><Type>System</Type></LayoutBreak>` or `<Type>Page</Type>` under `<Bar>` elements inside `_bars()`.
  - Expanded `barline_map` in `_master_bars()` to serialize `"hidden": "Hidden"` and `"dashed": "Dashed"`.
- **Reverse Extraction (`src/score2gp/gp_package.py`)**:
  - Added extraction of `<SystemLayout>` and `<StaffLayout>` properties under `<Layout>` back into the `layout` model object.
  - Added reverse-extraction of `<LayoutBreak>` element type back to `layout_break` inside `<Bar>`.
  - Expanded `barline_inv_map` in `MasterBar` parsing to support `"Hidden": "hidden"` and `"Dashed": "dashed"`.
- **Public Fixtures & Tests**:
  - Created `fixtures/public/test_system_breaks.ir.json` representing forced page/system breaks, custom hidden/dashed barlines, and custom staff/system layout scaling.
  - Created `tests/test_system_breaks.py` verifying accurate structural GP7-compatible XML tag output and bidirectional extraction round-tripping.

## Known Limitations

- Scanning is limited to digital PDF vector layouts; no scanned-PDF, image-based OCR, or layout ML is supported.

## Remaining Risks

- None known after private smoke refresh.

## Next Recommended Task

- Merge the current PR #123 into `main` after checks pass.
- Explicit non-goals for next tasks: Do not reopen tempo-variations, repeats/voltas, or system-breaks branches unless investigating a regression.

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.