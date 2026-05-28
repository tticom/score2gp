# AGENTS.md

This is the ScoreToGP product repository. It owns product truth: source code, tests, schemas, public fixtures, CLI behavior, and product documentation.

Agent governance truth lives in the external governance repository:

https://github.com/tticom/score2gp-agentops

Before doing agentic implementation or review work, agents must read:

https://github.com/tticom/score2gp-agentops/blob/main/projects/score2gp/README.md

## Governance Record Keeping

- **Mandatory Reporting**: Every agent task must write durable result records to `score2gp-agentops`.
- **Prompt Chain Recording**: For multi-prompt sessions, every explicit prompt must be stored as a numbered prompt-chain record in `score2gp-agentops`.
- **No Local Long-Form State**: The product repository must not carry long-form agent-control state.
- **Lightweight Pointer**: The product repository `HANDOFF.md`, if present, is strictly a short pointer to the governance repository and must not become the canonical evidence store again.
- **Fail-Safe**: If `score2gp-agentops` is unavailable, stop and ask the human maintainer for guidance rather than recreating or duplicating governance rules locally.

## Local Private-Safety Rules

- Do not add private PDFs, private GP/MusicXML files, rendered private pages, private exports, or derived private benchmark artifacts to Git.
- Keep private inputs and generated private outputs under gitignored locations such as `fixtures/private/` and `work/`.
- The only tracked file allowed under `fixtures/private` or `work` is `fixtures/private/.gitkeep`.
- Do not move fixtures unless the human maintainer explicitly requests it.
- Do not claim conversion progress without the evidence required by `score2gp-agentops`.

## Local Verification Commands

Run and report these commands before concluding product work:

```bash
python -m pytest
python -m score2gp.cli export-schema --out schemas
python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json
git diff --check
git diff -- schemas
git ls-files fixtures/private work
git status --short
git status --branch
```

The private-safety invariant is:

```bash
git ls-files fixtures/private work
```

It must output exactly:

```text
fixtures/private/.gitkeep
```

## Branch Safety

Never push directly to `main`. Use a branch and open a pull request.
