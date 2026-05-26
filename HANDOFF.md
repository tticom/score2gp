# Handoff

## Metadata

- **Current Branch**: `feature/gpif-target-version-adapters-v0.1`
- **Base Branch**: `main`
- **Current PR**: PR #109 (https://github.com/tticom/score2gp/pull/109)
- **Latest Local Commit**: `5ec3129a7bfd737219c35090813597b4c7af4969` ("feat: implement target version-gate adapters for legacy and modern formats")
- **Latest Pushed Commit**: `5ec3129a7bfd737219c35090813597b4c7af4969` ("feat: implement target version-gate adapters for legacy and modern formats")

- **Working Tree Status**: Clean (except doc/tasks updates).

- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. No root generated artifacts tracked.

## Tests And Checks Run

- `python -m pytest` -> 365 passed (100% success, including the new version-gated adapters down-conversion/up-conversion unit tests).
- `python -m score2gp.cli export-schema --out schemas` -> passed cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed cleanly (zero trailing whitespace or EOF blank line violations).
- `git diff -- schemas` -> passed cleanly.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `python scripts/private_e2e_smoke.py` -> passed cleanly against all private PDF inputs with zero regressions.

## What Changed In This Task

- **Version-Gated XML Generation & Transform Adapters**:
  - Created `src/score2gp/version_adapter.py` providing structural XML translations, attribute strips, and tag overrides to down-convert/up-convert GPIF files based on requested version specifications (GP6, GP7, GP8).
- **Transformation Rules per Profile**:
  - For **GP6**: Strips style collections (`StyleCollections`), master output mix balances (`MasterMixer`), and pipeline configuration presets (`PipelinePresetCascade`), injecting a `LegacyLayout` indicator tag inside `PageSetup`.
  - For **GP8**: Injects `TargetCompliancy` and `VersionLayout` tags under `Metadata` and enables modern style collections with the attribute `gp8Compatible="true"`.
  - Automatically overrides package `VERSION` text file output contents (e.g. `6.0\n`, `7.0\n`, `8.0\n`) to preserve zip compliance.
- **Orchestrator and CLI Support**:
  - Integrated target specification into `src/score2gp/batch.py` so individual payloads can specify a `target_version` key (defaulting to `"GP7"`).
  - Updated `src/score2gp/cli.py` `write-gp` command to expose a `--target` (GP6, GP7, GP8) option directly to developers.
- **Synthetic Manifest Fixtures & Unit Tests**:
  - Created `fixtures/public/test_version_adapters_manifest.json` modeling concurrent target profiles.
  - Authored unit tests in `tests/test_target_version_adapters.py` verifying correct structural transforms, VERSION overrides, and batch execution compatibility.

## Known Limitations

- Scanning is limited to digital PDF vector layouts; no scanned-PDF, image-based OCR, or layout ML is supported.

## Remaining Risks

- None.

## Next Recommended Task

- Proceed with final packaging enhancements or visual booklets.

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
