# AGENTIC_ARCHITECTURE.md

This project separates software construction from agent review.

The implementation agent may write code, tests, diagnostics, and handoff updates. The reviewer or architect agent must not act as the implementation agent's cheerleader. Its job is to decide whether the result is trustworthy.

## Operating model

Use three roles:

1. **Implementation Agent**: makes scoped code changes on a feature branch.
2. **Reviewer Agent**: evaluates claims against evidence using `REVIEW_RULES.md`.
3. **Human Maintainer**: decides whether to approve, reject, merge, close, or redirect the work.

The implementation agent reports what it did. The reviewer agent decides whether that report should be trusted.

## Artifact separation

Agent-control artifacts should be kept separate from product artifacts.

Product artifacts live in the normal codebase:

- `src/`
- `tests/`
- `fixtures/public/`
- `schemas/`
- product documentation

Agent-control artifacts live in review/planning documents:

- `AGENTS.md`
- `REVIEW_RULES.md`
- `HANDOFF.md`
- `TASKS.md`
- architecture/review notes

Do not let agent-control artifacts become a substitute for product correctness. A better handoff is not a better converter.

## Review gates

Before a PR can be called a fix, the reviewer must verify:

- the original failure is clearly stated,
- the baseline is clear,
- the artifact set is coherent,
- the private-safe before/after metrics moved in the claimed direction,
- strict mode and remediation mode are separated,
- no private files or `work/` outputs are tracked,
- no project invariant was weakened,
- public tests reproduce the mechanical defect when code changes were made.

If any of these are missing, keep the PR draft or request changes.

## Benchmark policy

A private benchmark may guide local diagnosis, but it is not a regression fixture.

For GP-originated PDF work, prefer a staged benchmark ladder:

1. tiny public synthetic fixture,
2. simple private GP-originated PDF/GP/MusicXML pair,
3. longer private GP-originated score with straight notes,
4. intermediate expressive score,
5. stress score with dense techniques and engraving.

Do not use a stress score as the first acceptance target.

## Source truth policy

Generated diagnostics are evidence, not truth.

If a diagnostic table says a score omits bars, but visual inspection shows those bars, the diagnostic table is wrong until proven otherwise.

The software must conform to the music. The music is not required to conform to the software's inferred structure.

## Review-first workflow

For every significant agent result:

1. Review the claims.
2. Check for contradictions.
3. Identify architectural risks.
4. Decide approve / keep draft / request changes / close.
5. Only then write the next implementation prompt.

Do not write the next prompt before giving a review verdict.
