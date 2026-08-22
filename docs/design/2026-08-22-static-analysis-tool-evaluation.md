# Static Analysis Tool Evaluation

**Date:** 2026-08-22
**Evaluated Branch:** `d237df5929968a42e61e17db114785c60e378e8b`
**Code Smell Contract:** `tticom/agy-skills@4162b613e423801b82e4136ac8338b5c365798dc` (file: `skills/engineering/code-review/references/code-smell-contract.md`)

## Context and Motivation
During the implementation of NPG-04D (Vector-Based Structural Signaling), the Codex Reviewer returned strict feedback regarding the introduction of code smells. Rather than relying purely on LLM self-evaluation to catch and resolve these code smells prior to handback, we evaluated automated 3rd-party static analysis tools.

This document presents a reproducible evaluation of Ruff vs. Pylint, mapping capabilities directly to the project's **No-Code-Smells Contract** to delineate what can be automated versus what still requires adversarial human review.

## Tool Evaluated: Ruff

### Reproducible Performance & Findings Evidence
- **Version Pin:** `ruff 0.16.4` (Python 3.12.3)
- **Command executed:** `time ruff check src/ tests/ --statistics`

**Timing:**
```
real    0m0.076s
user    0m0.339s
sys     0m0.197s
```

**Results:**
The unconfigured run found 1,106 errors across the repository, of which 702 were marked as safely auto-fixable `[*]`.

**Top Findings (Sample):**
- `338 I001 unsorted-imports`
- `203 F401 unused-import`
- `64 SIM102 collapsible-if`
- `54 B008 function-call-in-default-argument`
- `35 F841 unused-variable`

### Contract Coverage Matrix

The following table explicitly defines which clauses of the No-Code-Smells contract Ruff can autonomously enforce, and which it cannot.

| Contract Clause | Enforceable by Ruff? | Relevant Ruff Rules | Notes & Limitations |
| :--- | :--- | :--- | :--- |
| **Import & Dependency Clutter** | **YES** | `F401` (Unused), `F402` (Shadowed), `I` (isort) | Safely auto-fixable, though `__init__.py` facades require exclusion (`F401` ignore). |
| **Duplicated / Unused Code (Local)** | **YES** | `F841` (Unused variable) | Catches unused local assignments immediately. |
| **Feature Envy / Middle Man / Complexity** | **PARTIAL** | `SIM` (Simplify), `C90` (McCabe) | `SIM` auto-fixes verbose/nested logic. `C901` flags overly complex functions for manual refactor, but does not auto-fix. |
| **Dead Code (Global)** | **NO** | None | Ruff cannot detect unused *public* functions or disconnected production paths. Requires manual tracing. |
| **Test Theatre** | **NO** | None | Ruff cannot verify if a test properly crosses a production handoff or uses an independent oracle. |
| **Exception-as-Fallback** | **NO** | None | Ruff flags bare excepts (`BLE001`), but cannot enforce that a fallback explicitly returns/emits typed data. |
| **Magic Thresholds / Substring Traps** | **NO** | None | Requires manual boundary probes and adversarial test cases. |
| **Circular Evidence** | **NO** | None | Requires semantic validation of the oracle's provenance. |

## Rejected Alternatives

### Pylint
- **Version Pin:** `pylint 4.0.7`
- **Command executed:** `time pylint src/ tests/`

**Timing:**
Execution consistently took over `45.0` seconds on `score2gp`.

**Findings:**
Pylint's strictness and deep AST checks generated thousands of false positives (e.g. `R0902: Too many instance attributes (17/7)`) requiring extensive configuration tuning.

**Rejection Rationale:**
Pylint's execution time is orders of magnitude slower than Ruff (`45s` vs `0.076s`), slowing down local feedback loops and CI runs significantly. Ruff provides the most valuable rules from Pylint without the performance penalty.

### Flake8 + Black + isort
**Rejection Rationale:**
Managing three separate tools introduces Python environment dependency conflicts. Ruff executes in 76ms and natively covers the rules of all three tools in a single Rust binary.

## Recommendation

**We recommend integrating Ruff into the CI and developer workflow to enforce the automated subset of the code-smell contract.**

1. **Configuration:** Define `tool.ruff` in `pyproject.toml` to enable `E, F, W, B, C90, SIM, I`.
2. **Exemptions:** Explicitly ignore `F401` in `src/score2gp/**/__init__.py` and known facade modules to prevent auto-fixers from destroying re-exports.
3. **Review Protocol:** The Reviewer must continue to manually audit PRs for *Test Theatre, Circular Evidence, Dead Code, and Domain Smells*, as static analysis cannot enforce these semantic requirements.
