# Agent-Ops Governance Integration

This repository is the product repository for the **ScoreToGP** compiler. Project-wide developer agent governance, critical review postures, prompt templates, and benchmark ladders are maintained externally.

## Separation of Repositories

- **Product Repository (`score2gp`)**:
  - Owns all functional product code (`src/`), unit and integration tests (`tests/`), validation schemas (`schemas/`), public synthetic fixtures, local repository safety invariants, and verification CLI tools.
- **Governance Repository (`score2gp-agentops`)**:
  - Owns the canonical review rules, benchmark ladder policies, acceptance targets, permanent architecture decision records, rejected claims logs, and reusable prompt templates.

---

## Developer and Reviewer Guidelines

1. **Implementation Developer Agents**:
   - Must read and strictly follow [AGENTS.md](../AGENTS.md) for local repository safety invariants, branch commit guidelines, and private-safety audits.
2. **Reviewer / Architect Agents**:
   - Must consult the canonical [REVIEW_RULES.md](https://github.com/tticom/score2gp-agentops/blob/main/projects/score2gp/REVIEW_RULES.md) inside the `score2gp-agentops` governance repository before evaluating pull requests.
3. **Task Tracking & Branch State**:
   - [HANDOFF.md](../HANDOFF.md) is a branch-local state tracking file, not a repository of long-term architectural truth.
   - [TASKS.md](../TASKS.md) maintains active todo checklists during execution and must not duplicate the comprehensive benchmark ladder defined in `score2gp-agentops`.
