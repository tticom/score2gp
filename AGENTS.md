# AGENTS.md

This repository is an open-source-style experiment for converting owned PDF guitar scores into inspectable intermediate data and then into Guitar Pro 7 packages.

Ground rules:

- Be honest about recognition quality. Never claim perfect PDF-to-GP conversion.
- Do not bypass DRM or process scores the user does not own or have permission to process.
- Keep private fixtures under `fixtures/private/`; they are ignored by Git.
- Prefer staged outputs: rendered pages, overlays, raw extraction JSON, strict ScoreIR JSON, warnings, and reports.
- Unsupported notation must be surfaced in warnings or reports, not silently dropped.
- Keep modules small, typed, and tested.

# Persistent handoff rule

At the end of every task, update `HANDOFF.md` before reporting completion.

`HANDOFF.md` is the canonical project handoff file. Do not create or use `HANDOVER.md` unless explicitly instructed.

Because some agent CLIs may limit access to previous output, `HANDOFF.md` must be kept durable and pushed to the remote branch whenever it changes.

Every completed task must leave `HANDOFF.md` with:
- current branch
- base branch
- current PR number and URL if one exists
- latest local commit hash and subject
- latest pushed commit hash and subject
- working tree status
- tests/checks run and results
- GitHub check status if applicable
- private-safety status
- what changed in the task
- known limitations
- remaining risks
- next recommended task
- explicit scope boundaries, including what must not be started in the current branch

If the task stops early because of a failure, conflict, pending GitHub check, missing approval, missing information, or CLI/tool limitation, update `HANDOFF.md` with:
- where it stopped
- exact failing/pending command or condition
- files involved
- what was already committed
- what was already pushed
- safest next action

After updating `HANDOFF.md`:
1. Run the relevant verification checks for the task.
2. Confirm no private files or `work/` artifacts are tracked.
3. Commit `HANDOFF.md` together with the task changes, or as a small handoff-only commit if the task changes were already committed.
4. Push the current feature branch so the handoff is available remotely.
5. Re-check PR/GitHub status if a PR exists.
6. Only then report completion.

Never push directly to `main` unless explicitly instructed. On feature branches, push handoff updates to the feature branch after checks pass.

Do not put private musical content, private PDF text, private fret sequences, private titles, private URLs, private diagnostic output, or `work/` artifact contents into `HANDOFF.md`.

Keep `HANDOFF.md` private-safe and useful enough that a new agent can continue without reading previous chat history.

# Planning and execution rule

Unless the user explicitly asks for planning only, do not stop after creating an implementation plan. Create a short plan if useful, then continue into implementation.

The agent may proceed through normal repo-local implementation, tests, commits, pushes to feature branches, and draft PR creation without asking for another approval, provided:
- the task remains within the requested scope
- required checks pass
- no private files or work/ artifacts are tracked
- HANDOFF.md is updated, committed, and pushed
- the branch is not main
- the push is not a force push

The agent must still stop and ask before:
- merging PRs
- force-pushing
- deleting branches
- destructive file operations
- reading private fixtures unless explicitly instructed
- reading secrets or credential files
- broadening scope beyond the current branch

# Allowed routine commands

The user permits the agent to run routine Git, GitHub CLI, and pytest/project-validation commands without asking for additional confirmation.

Allowed without extra confirmation:
- git status
- git status --branch
- git branch
- git branch --show-current
- git switch
- git checkout
- git pull --ff-only
- git fetch
- git log
- git diff
- git diff --stat
- git diff --check
- git diff -- schemas
- git ls-files
- git add
- git commit
- git push origin <current-feature-branch>
- gh pr view
- gh pr checks
- gh pr status
- gh pr create
- gh pr edit
- gh pr ready
- python -m pytest
- python -m score2gp.cli export-schema --out schemas
- python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json
- git push --force*
- git reset --hard*
- git clean*
- git rm*
- gh pr merge*
- gh repo*
- gh secret*
- del*
- rmdir*
- rm*
- type fixtures/private/*
- cat fixtures/private/*

The agent may commit and push normal feature-branch work after required checks pass, provided:
- the branch is not `main`
- no private files or `work/` artifacts are tracked
- `HANDOFF.md` has been updated
- the push is a normal push to the current feature branch
- the working tree is clean after the push

Still require explicit user confirmation for:
- git push --force
- git push --force-with-lease
- git reset --hard
- git clean
- git rm
- deleting branches
- deleting files or directories
- merging PRs
- pushing directly to main
- reading fixtures/private/*
- reading secrets, .env files, credentials, keys, or tokens
- changing GitHub repo settings, secrets, or permissions
- running arbitrary network upload/download commands

Run:
python -m pytest
python -m score2gp.cli export-schema --out schemas
python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json
git diff --check
git diff -- schemas
git ls-files fixtures/private work

If checks pass, commit and push:
git add AGENTS.md HANDOFF.md
git commit -m "Document routine command permissions"
git push origin feature/ascii-scoreir-gate-refusal-diagnostics-v0.1