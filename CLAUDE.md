# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Governance gate (read first)

This repo is the **product** repo only. Agent governance lives in the sibling repo `../score2gp-agentops` (workspace layout: `score2gp/`, `score2gp-agentops/`, `score2gp-private-fixtures/`). Full rules are in `AGENTS.md`; the load-bearing ones:

- Before any work, read `../score2gp-agentops/projects/score2gp/{AGENT_CONTROL,ACTIVE_TASK,TASK_RECORDING_CONVENTION}.md`. If `ACTIVE_TASK.md` says `NO_ACTIVE_TASK_APPROVED`, stop and report.
- Work on a task branch, never `main`. Never merge, force-push, delete branches, push to `main`, or run `gh pr merge`; the human merges.
- Don't put long-form agent state in this repo (`HANDOFF.md` is only a pointer). Results/prompt chains are recorded in `score2gp-agentops`.
- "continue / go / next" requests are routed by `../score2gp-agentops/CLAUDE.md` (`scripts/score2gp_dispatch.py`), not by this repo.

## Commands

Python ≥3.11, package in `src/` layout. Development is OS-agnostic: every command below runs unchanged in PowerShell on Windows and in a POSIX shell on Linux. Use `python`, never `python3`. The virtualenv interpreter is `.venv/Scripts/python.exe` on Windows and `.venv/bin/python` on Linux; activate it, or call it directly.

```bash
python -m venv .venv                        # then activate: .venv\Scripts\Activate.ps1 (Windows) or . .venv/bin/activate (Linux)
python -m pip install -e ".[dev]"          # dev deps: pytest, pillow, ruff==0.6.2, pylint==4.0.7
python -m pytest                            # full suite (tests/, pythonpath=src)
python -m pytest tests/test_build_ir.py::test_name -x   # single test
python scripts/agent_verify.py              # pytest + export-schema + validate-ir + artifact_audit + git checks; writes work/agent_verify.{json,md}
python scripts/artifact_audit.py            # artifact audit
python scripts/pr_body.py --title ... --summary ... --limitations ... --review-focus ...   # PR evidence body
python -m score2gp.cli --help               # CLI (also the `score2gp` entrypoint)
```

`make` is optional. Where it's installed, `make verify`, `make audit`, `make pr-body` and `make quick TEST=...` (default `TEST=tests/test_notation_bridge.py`) run the same commands using the virtualenv interpreter.

Pre-conclusion checklist required by `AGENTS.md` (report all of it):

```bash
python -m pytest
python -m score2gp.cli export-schema --out schemas
python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json
python scripts/artifact_audit.py            # must exit 0
git diff --check
git diff -- schemas                         # export-schema must leave no diff
git ls-files fixtures/private work          # must print exactly: fixtures/private/.gitkeep
git status --short
git status --branch
```

CI (`.github/workflows/pylint.yml`, named "CI") runs `pytest` + `artifact_audit.py` on Python 3.11 after mounting the private corpus. A separate advisory workflow runs `scripts/raster_diagnostics_gate_report.py`.

### Private fixtures and test failures

Some tests are **mandatory real-source tests** that need `score2gp-private-fixtures` mounted into `fixtures/private/` (e.g. `Lesson-5.pdf`, `Lesson-6.pdf`, `Derek Trucks BB King.gp`). `tests/test_private_fixture.py` *fails* (not skips) when the corpus is absent; a few others (`test_pdf.py`, `test_npg_05_*`, `test_scoreir_gpif_compiler_refactor.py`) skip on a missing Lesson PDF. So failures in a clone without the private corpus are expected, not regressions. `fixtures/private/` and `work/` are gitignored — never commit private PDFs/GP/MusicXML or derived outputs (`artifact_audit.py` enforces this and also restricts where generated `.json/.png/.html` may be tracked).

## Architecture

`score2gp` is a staged PDF → Guitar Pro 7 pipeline where every stage emits an inspectable artefact and **unsafe/uncertain input is refused rather than guessed**. `docs/architecture.md` is the detailed reference; the shape:

1. **PDF ingestion / extraction** (`pdf.py`, `pdf_*.py`, `cli.py: inspect-pdf`, `extract-tab`) — PyMuPDF geometry + text → `TabRaw` (`tabraw.py`, `tabraw.v0.1`): fret candidates with spatial evidence, confidence and provenance. System → bar → string grouping is deliberately conservative; ungrouped candidates never become notes.
2. **Symbolic sidecar** (`musicxml.py`, `notation_omr/`, Audiveris optional) — MusicXML/`.mxl` import with a timing/voice-cursor preflight. `notation_omr/` is the in-repo notation recognition (clef, notehead, duration, tuplet, staff geometry, timeline, biomechanical `position_optimizer`) that can generate sidecar MusicXML. `recognition/` holds the newer typed observation/raster/scale schemas (REC-* tasks).
3. **`build_ir`** (`build_ir.py`, `ascii_alignment.py`, `scoreir_compiler.py`) — fuses MusicXML timing with TabRaw string/fret evidence into `ScoreIR` (`ir.py`, strict pydantic, `extra="forbid"`; JSON schema in `schemas/`). Durations/rests come from MusicXML; strings/frets from TabRaw. Gates raise `BuildIrInputRiskError` and write `build-ir-failure-diagnostics` sidecars; success/failure diagnostics live in sidecars, never in ScoreIR.
4. **GP writer** (`gpif.py`, `gpif_builder.py`, `gp_package.py`) — ScoreIR → GPIF XML → GP7 zip, optionally over a template package (`fixtures/templates/`). `inspect-gp`, `validate`, `compare*` (`compare.py`, `oracle.py`) verify output semantically, not byte-for-byte.
5. **`report.py` / `diagnostics.py`** — the (very large) HTML/JSON diagnostic report generators. JSON is always the source of truth; HTML is developer-facing.

Big files to expect: `pdf.py`, `build_ir.py`, `report.py`, `musicxml.py`, `gpif.py`, `gp_package.py`, `cli.py` (all 1.5–5k lines). `cli.py`'s `convert` command orchestrates the whole pipeline; `batch.py`/`cache.py` add parallel/incremental runs.

### Conventions that span files

- **Fail-closed gates with warning-code taxonomies.** Layout, fret-refinement, MusicXML timing, ASCII-tab timing and symbol-attachment problems are reported as stable string codes (`pdf_*`, `ascii_*`, etc. — see `docs/architecture.md`, `docs/diagnostics_failure_taxonomy.md`). Any layout warning blocks `pdf_grouped` status and therefore `build_ir`. Don't loosen a gate to make a fixture pass; the 2026-08-09 recovery design (`docs/design/2026-08-09-conversion-recovery-architecture.md`) explicitly rejects "symptom-masking" hacks (widened geometry tolerances, duration scaling, proximity digit merging, open-string synthesis).
- **Versioned contracts** (`tabraw.v0.1`, `pdf-timing-mapping.v0.7`, `pdf-timing-refinement.v1.0`, `ascii-*.v0.1`, `build-ir-diagnostics.v0.1`) — bump the version string when changing a payload shape.
- **Real-source-only acceptance**: the target architecture is topology-first (score2gp owns system/barline topology; OMR sidecars only supply timing/pitch) and is judged against ground-truth `.gp` files via the oracle comparators, not synthetic unit tests alone.
- Public fixtures for CI live in `fixtures/public/` and `tests/fixtures/{pdf,musicxml,tabraw}`; new failure modes should get a synthetic public fixture so CI never depends on private material.
- `TESTING.md` describes the extra private smoke scripts (`scripts/private_e2e_smoke.py`, `private_gp_quality_audit.py`); its "467 tests" figure is stale. PRs need an evidence report (`make pr-body` / `scripts/pr_body.py`).

## Agent skills

### Issue tracker

GitHub Issues on `tticom/score2gp` via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default roles, except `needs-triage` and `needs-info`, which are namespaced as `triage:needs-triage` and `triage:needs-info`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` at the repo root. ADRs live in `doc/architecture/decisions/` (the established location; create new ADRs there). `docs/adr/` is only checked because skills may reference it, and is not a second ADR location. See `docs/agents/domain.md`.
