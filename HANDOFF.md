# Handoff

## Metadata

- **Current Branch**: `feature/build-ir-fret-snapping-optimization-v0.1`
- **Base Branch**: `main`
- **Current PR**: [PR #114](https://github.com/tticom/score2gp/pull/114) (Draft)
- **Latest Local Commit**: `cc51d8099daec191f3619977eaeb2b123cf2dc37` ("docs: update HANDOFF.md and TASKS.md with fret snapping cost optimization details")
- **Latest Pushed Commit**: `cc51d8099daec191f3619977eaeb2b123cf2dc37` ("docs: update HANDOFF.md and TASKS.md with fret snapping cost optimization details")

- **Working Tree Status**: Clean.

- **GitHub Check Status**: N/A
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked under `fixtures/private/`. No private PDFs, GP files, MXL/MusicXML files, summaries, overlays, logs, or `work/` contents are tracked.
- **Root Generated-Artifact Audit**: Clean. No root generated artifacts tracked.

## Tests And Checks Run

- `python -m pytest` -> 374 passed (100% success, including the new fret snapping cost optimization unit tests and E2E compiler integration tests).
- `python -m score2gp.cli export-schema --out schemas` -> passed cleanly.
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json` -> valid.
- `git diff --check` -> passed cleanly (zero trailing whitespace or EOF blank line violations).
- `git diff -- schemas` -> passed cleanly.
- `git ls-files fixtures/private work` -> only `fixtures/private/.gitkeep`.
- `python scripts/private_e2e_smoke.py` -> passed cleanly against all private PDF inputs with zero regressions.

## What Changed In This Task

- **Fret-Snapping Cost Optimization & Shift Penalization Solver**:
  - Implemented `optimize_fret_snapping(score: ScoreIR)` in `src/score2gp/build_ir.py` using a localized Viterbi-like dynamic programming costing solver.
  - Enforced ergonomic centroid boundaries, penalizing notes $> 4$ frets away from the active hand position centroid.
  - Clamped all valid pitch selections within localised structural safety cushions (frets `0` to `24`).
  - Penalized radical horizontal jumps $> 4$ frets between adjacent events.
  - Implemented biomechanical stretch limits, filtering out unplayable finger spans exceeding `5` frets.
  - Applied a minor mismatch cost to prefer original `TabCandidate` suggestions when they are ergonomic and biomechanically safe.
- **Opt-in Compiler & CLI Integration**:
  - Exposed keyword-only parameter `optimize_fret_snapping: bool = False` to `build_ir_from_files`, `build_ir_with_diagnostics_from_files`, `build_ir_from_imports`, and `build_ir_with_diagnostics_from_imports`.
  - Resolved Python variable shadowing issues cleanly by referencing the global optimizer namespace.
  - Added the `--optimize-fret-snapping` / `--no-optimize-fret-snapping` command-line option to both `build-ir` and `convert` command entry points inside `src/score2gp/cli.py` (defaulting to `False` to maintain full visual coordinate fidelity for legacy tests).
- **Public Fixtures & Verification Tests**:
  - Created `fixtures/public/test_fret_snapping_optimization.ir.json` modeling wide intervals and shifting melodic passages.
  - Created `tests/test_fret_snapping_optimization.py` containing 3 thorough unit/integration tests confirming dynamic programming costing accuracy, unplayable span exclusions, and clean pipeline invocation.

## Known Limitations

- Scanning is limited to digital PDF vector layouts; no scanned-PDF, image-based OCR, or layout ML is supported.

## Remaining Risks

- None.

## Next Recommended Task

- Next branch: `feature/build-ir-advanced-ornaments-v0.1`
- Goal: Implement advanced ornamentation parsing and visual formatting.

## Explicit Scope Boundaries

- **No OCR, scanned-PDF, or ML layout recognition** used.
- **No private files or work/ outputs committed**.
- **No MusicXML timing repair or alterations**.
- **No loosening of grouping/string/fret/timing/build-ir gates**.
