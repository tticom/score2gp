# AGENTS.md

This repository is an open-source-style experiment for converting owned PDF guitar scores into inspectable intermediate data and then into Guitar Pro 7 packages.

Ground rules:

- Be honest about recognition quality. Never claim perfect PDF-to-GP conversion.
- Do not bypass DRM or process scores the user does not own or have permission to process.
- Keep private fixtures under `fixtures/private/`; they are ignored by Git.
- Prefer staged outputs: rendered pages, overlays, raw extraction JSON, strict ScoreIR JSON, warnings, and reports.
- Unsupported notation must be surfaced in warnings or reports, not silently dropped.
- Keep modules small, typed, and tested.
- Code and tests must be written before any PR is raised. Do not create tasks or PRs solely to run tests or update markdown files. Validation and markdown updates must be performed as a result of actual code changes within the same task.

## Critical Review Invariant

When evaluating agent output, PRs, handoffs, or diagnostic reports, act first as a sceptical reviewer, not as a progress narrator.

Do not describe work as a breakthrough, success, fix, or improvement unless the claim is supported by:
1. a coherent single-run artifact set,
2. a clearly stated baseline,
3. private-safe before/after metric deltas,
4. public regression coverage where code changed,
5. strict separation between diagnostic/remediation output and strict conversion success.

Use the terms:
- claimed
- verified
- unverified
- contradicted
- blocked

Avoid celebratory or promotional language in reviews.

A PR is not mergeable merely because tests pass, files are generated, or diagnostics are richer. A PR is mergeable only if it satisfies the stated acceptance criteria without weakening project invariants.

If artifacts disagree, stop evaluation and require artifact reconciliation before interpreting metrics.

If a branch changes the benchmark or oracle, treat that as a hypothesis to verify, not a success.

## Evidence Hierarchy

When reviewing conversion progress, trust evidence in this order:

1. A clean strict-mode run from a fresh output directory.
2. A clean private-safe round-trip evaluation from a fresh output directory.
3. Public synthetic tests reproducing the same mechanical defect.
4. Handoff summaries.
5. Agent claims.

Never treat HANDOFF.md claims as sufficient evidence by themselves.

Every review must explicitly separate:
- strict conversion status,
- remediation/diagnostic status,
- semantic round-trip status,
- generated-file existence.

Generated ScoreIR or GP output is not conversion success unless the semantic quality gate passes.

## Automatic Review Blockers

Request changes or keep the PR in draft if any of these are true:

- Artifacts are from mixed or stale runs.
- summary.json, diagnostics.json, warnings.json, edge-boundary reports, and roundtrip_report.json disagree on whether build-ir ran or whether ScoreIR/GP was written.
- The PR suppresses unsafe grouping, string, fret, bar, or timing warnings without proving the suppression is isolated to diagnostic/remediation mode.
- MusicXML pitch, tuning, or oracle data is used to bypass PDF geometry gates.
- A private benchmark is reinterpreted without proving source-pair equivalence.
- Tests mostly assert implementation copies rather than exercising the production path.
- The PR improves one metric while worsening or invalidating the acceptance benchmark.
- The PR claims progress without a public fixture reproducing the mechanical defect.
## Review Verdict

Status: Fix / Research-Isolation / Infrastructure / Blocked / Rejected

Merge recommendation:
- Approve
- Keep Draft
- Request Changes
- Close/Supersede

One-sentence reason:

## Claims vs Evidence

Claim:
Evidence:
Verified? yes/no
Contradictions:

## Artifact Coherence

Fresh output directory used: yes/no
Exact command:
Artifacts regenerated in same run:
- summary.json: yes/no
- diagnostics.json: yes/no
- warnings.json: yes/no
- edge-boundary report: yes/no
- roundtrip_report.json: yes/no

Do all artifacts agree on build-ir status? yes/no
Do all artifacts agree on ScoreIR/GP written status? yes/no
Do all artifacts agree on semantic comparison status? yes/no

If no, stop and do not interpret metrics.

## Strict Mode Result

Grouping status:
ScoreIR written:
GP written:
Primary blocker:
Changed from previous baseline? yes/no

## Remediation / Diagnostic Result

Diagnostic-only:
ScoreIR written:
GP written:
Warnings suppressed:
Why suppression cannot leak into strict mode:

## Semantic Round-Trip Result

Oracle source:
Source-pair equivalence verified? yes/no/unknown
Oracle note count:
Recovered note count:
String match rate:
Fret match rate:
Full match rate:
Poor bars:
Unknown bars:
Unmatched oracle notes:
Unmatched PDF candidates:

## Metric Delta Against Previous Baseline

Metric:
Previous:
Current:
Improved / worsened / unchanged / invalidated:
Explanation:

## Architectural Risk Review

Uses MusicXML pitch/tuning/oracle evidence? yes/no
If yes, for what purpose?
Does it affect layout grouping, bar assignment, string assignment, fret inference, or timing?
Allowed by project rules? yes/no/needs decision

Unsafe warning suppression added? yes/no
Strict-mode impact proven absent? yes/no

## Public Regression Coverage

Public fixture added:
Mechanical defect reproduced:
Guardrail test added:
Production path exercised:

## Done - Accepted Fixes

Only list work here if it passed acceptance criteria and is merged or approved.

## Done - Research Findings

Use this section for useful investigations that did not fix conversion.

Each entry must include:
- hypothesis tested
- result
- evidence location
- next decision

## Rejected / Superseded Work

Use this section for PRs or branches that produced useful information but should not be treated as accepted architecture.

## Current Acceptance Target

The active target is:

[plain English acceptance test]

Current blocker:
Current baseline:
Required next evidence:
Disallowed shortcuts:

## Review Rules
- Read REVIEW_RULES.md for review rules.

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

# Cross-agent final report rule

At the end of every task, the final response must include a complete, copy/pasteable final report for another assistant that cannot access GitHub.

The final report must be based on local Git, GitHub CLI output, HANDOFF.md, TASKS.md, and the actual verification commands run.

The report must include:

## Repository State
- current branch
- base branch
- whether local branch tracks origin
- latest local commit hash and subject
- latest pushed commit hash and subject
- working tree status
- whether local branch is clean and synchronized

## Pull Request State
- PR number
- PR URL
- PR title
- PR state: draft/open/ready/merged/closed
- whether PR is draft
- whether PR is mergeable if known
- GitHub check status
- names/statuses of relevant checks where available
- whether the PR was created, updated, marked ready, or left draft
- whether the PR was merged: yes/no
- merge commit hash if merged

## Verification Results
- exact test command and result
- schema export command and result
- validate-ir command and result
- git diff --check result
- git diff -- schemas result
- private/work audit command and result
- root generated-artifact audit result if relevant
- public E2E smoke result if relevant

## Private-Safety Result
- whether any private PDFs, GP files, MusicXML/MXL files, overlays, logs, summaries, diagnostics, or work/ outputs are tracked
- exact result of git ls-files fixtures/private work
- confirmation that only fixtures/private/.gitkeep is tracked under private/work paths
- any untracked private outputs must be named only by safe path category, not content

## What Changed
- concise bullet list of implementation changes
- public fixtures added or updated
- diagnostics/reporting added or updated
- docs/tasks/handoff files updated
- strict gates preserved

## Current Blocker Classification
- top blocker
- secondary blockers
- current private-safe summary using only anonymized counts/statuses/reason codes
- comparison with previous summary if known
- whether the blocker improved, stayed same, or moved to a new stage

## Scope Boundaries Preserved
Explicitly state whether these were preserved:
- no private files committed
- no work/ outputs committed
- no OCR
- no scanned-PDF support
- no ML layout recognition
- no MusicXML timing repair
- no GPIF expansion
- no tuning/pitch inference used to bypass geometry gates
- no loosening of grouping/string/fret/timing/build-ir gates

## Next Recommended Task
- exact next branch name
- goal of next branch
- why this is the next branch
- explicit non-goals for next branch
- whether next task should wait for current PR merge

The final response must not rely on “see PR” or “see GitHub” as the only source. Include the information directly.

If the task stops early, the final report must include:
- where it stopped
- exact pending/failing command or condition
- what was already committed
- what was already pushed
- PR status if any
- safest next action

HANDOFF.md must contain the same essential state before the final response is given.

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
