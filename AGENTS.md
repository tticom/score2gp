# AGENTS.md

## Product Agent Execution Gate

This product repository must not be used as a standalone execution source.

Agent governance truth lives in the external governance repository:

`/home/tticom/work/score2gp-workspace/score2gp-agentops`

Before doing any work, agents must read the governance control files:

1. `projects/score2gp/AGENT_CONTROL.md`
2. `projects/score2gp/ACTIVE_TASK.md`
3. `projects/score2gp/TASKS.md`

If `ACTIVE_TASK.md` says `NO_ACTIVE_TASK_APPROVED`, agents must stop after preflight and report.

Agents must not:

- merge PRs
- push directly to main
- delete branches
- force-push
- run `gh pr merge`
- run commands containing `--delete-branch`
- run `hgh`
- approve own PR
- bypass failing checks
- mark unmerged work as merged
- start unrelated backlog tasks

Agents may push task branches and open PRs for human review if operating under Tier 2. Human performs merge and branch deletion.

---


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
- Private fixtures reside in the sibling repository `score2gp-private-fixtures`.
- Keep local mounts, symlinks, or copies of private inputs and generated private outputs under gitignored locations such as `fixtures/private/` and `work/`.
- The only tracked file allowed under `fixtures/private` or `work` is `fixtures/private/.gitkeep`.
- Do not move fixtures unless the human maintainer explicitly requests it.
- Do not claim conversion progress without the evidence required by `score2gp-agentops`.

## Local Verification Commands

Run and report these commands before concluding product work:

```bash
python -m pytest
python -m score2gp.cli export-schema --out schemas
python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json
python scripts/artifact_audit.py
git diff --check
git diff -- schemas
git ls-files fixtures/private work
git status --short
git status --branch
```

The private-safety invariant check:

```bash
python scripts/artifact_audit.py
```

It must exit with code 0 (PASS). Also:

```bash
git ls-files fixtures/private work
```

must output exactly:

```text
fixtures/private/.gitkeep
```

## Branch Safety

Never work directly on `main` for implementation changes.

Agents must not merge pull requests, push directly to `main`, or delete branches.

When agent work is approved under Tier 2, agents may create a task branch, commit work, push the task branch, and open a pull request. Reviewer agents may review PRs, make comments on PRs, and review Architect and Developer outputs. The human maintainer retains exclusive authority for merging and branch deletion.

Agents may report the branch name, changed files, validation evidence, and PR link. Merging and branch deletion remain strictly human-only GitHub actions.
