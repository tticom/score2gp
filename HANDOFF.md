# Handoff

## Metadata

- **Current Branch**: `feature/gpif-package-binary-hardening-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft PR (created via `gh pr create --draft --fill`)
- **Latest Local Commit**: `93e85e6e0246fc3742b890eab97c34f72bad2da1` ("docs: update HANDOFF.md and TASKS.md with element sequencing and dynamic companion files hardening achievements")
- **Latest Pushed Commit**: `93e85e6e0246fc3742b890eab97c34f72bad2da1` ("docs: update HANDOFF.md and TASKS.md with element sequencing and dynamic companion files hardening achievements")

- **Working Tree Status**: Clean.

- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. No root generated artifacts tracked.

## Tests And Checks Run

- `python -m pytest` -> 371 passed (100% success, including the new GPIF element sequencing and binary package companion files hardening unit tests).
- `python -m score2gp.cli export-schema --out schemas` -> passed cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed cleanly (zero trailing whitespace or EOF blank line violations).
- `git diff -- schemas` -> passed cleanly.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `python scripts/private_e2e_smoke.py` -> passed cleanly against all private PDF inputs with zero regressions.

## What Changed In This Task

- **Strict XML Element Sequencing Constraints under `<Score>`**:
  - Defined a strict sequence mapping for all `<Score>` children under a standardized schema sequencing array in `src/score2gp/gpif.py` and `src/score2gp/version_adapter.py`.
  - Applied a stable key sorting transformation at the end of both `build_gpif()` and `adapt_gpif()` to guarantee that the compiled GPIF document perfectly matches native Guitar Pro unmarshalling sequence constraints.
- **Dynamic Companion Files Generation**:
  - Implemented robust, dynamic generation of `Content/Preferences.json` in `src/score2gp/gp_package.py` mapping page size, scaling, orientation, view mode, and margins.
  - Implemented dynamic generation of `Content/LayoutConfiguration` in `src/score2gp/gp_package.py` containing XML metadata tags (`<ActiveLayout>`, `<SystemLayout>`, `<SystemPageMargins>`) matching active layout styles.
- **Public Fixtures & Verification Tests**:
  - Created `fixtures/public/test_gpif_binary_hardening.ir.json` modeling page layouts, custom fonts, style collections, and active expression controllers to act as our structural sequencing baseline.
  - Created `tests/test_gpif_binary_hardening.py` asserting strict element sequencing compliant with sequence rules, companion file content generation correctness, and E2E roundtrip packaging.

## Known Limitations

- Scanning is limited to digital PDF vector layouts; no scanned-PDF, image-based OCR, or layout ML is supported.

## Remaining Risks

- None.

## Next Recommended Task

- Proceed with advanced visual ornamentations or fret snapping refinements.

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
