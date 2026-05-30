#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${REPO_ROOT}" ]]; then
  echo "ERROR: Run this from inside the score2gp git repository."
  exit 1
fi

cd "${REPO_ROOT}"

if [[ ! -f pyproject.toml ]] || ! grep -q 'name = "score2gp"' pyproject.toml; then
  echo "ERROR: This does not look like the score2gp repository root."
  echo "Current directory: ${REPO_ROOT}"
  exit 1
fi

mkdir -p agent-workflow/prompts agent-workflow/scripts agent-workflow/tasks

cat > agent-workflow/README.md <<'EOF'
# score2gp Agent Workflow

This folder contains a local multi-agent workflow for Antigravity-style development.

The intended agent sequence is:

```text
Conductor / Human
  ↓
Architect agent
  ↓
Technical Product Owner agent
  ↓
Developer agent
  ↓
Reviewer agent
  ↓
Integration decision
```

Use separate Git worktrees for implementation and review work. Do not let multiple agents edit the same working tree.

## Roles

- **Architect**: analyse the repo and produce a plan. No source-code edits.
- **Technical Product Owner**: turn the requirement into acceptance criteria and test cases. No source-code edits.
- **Developer**: implement the smallest safe slice in a dedicated worktree.
- **Reviewer**: inspect the diff, run tests, and decide whether the work satisfies the criteria. Avoid source-code edits unless explicitly asked.

## Start a task

```bash
./agent-workflow/scripts/new-agent-task.sh pdf-to-gp-smoke-v1 "Prove one owned lesson PDF can move through the safest currently supported conversion path"
```

## Create worktrees

```bash
./agent-workflow/scripts/create-agent-worktrees.sh pdf-to-gp-smoke-v1 main
```

The worktrees will be created outside the repository under:

```text
../agent-worktrees/
```

Open each worktree folder separately in Antigravity.
EOF

cat > agent-workflow/prompts/00-conductor.md <<'EOF'
# Conductor Prompt

You are the conductor for the score2gp multi-agent workflow.

Your job is to coordinate the agents without doing unnecessary reasoning inside every agent.

Rules:

1. Keep the task narrow.
2. Prefer one implementation slice over broad rewrites.
3. Keep private copyrighted fixtures local and untracked.
4. Do not ask agents to commit private PDFs, GP files, MXL/MusicXML files, overlays, logs, or generated work artifacts.
5. Require tests or an explicit explanation of why a test was not possible.
6. Stop agents that only update docs without moving the implementation forward, unless the task is explicitly documentation-only.
7. Do not let multiple agents edit the same working tree.

Expected flow:

1. Give the Architect the master task.
2. Give the TPO the master task and architecture plan.
3. Give the Developer the master task, architecture plan, and acceptance criteria.
4. Give the Reviewer the master task, architecture plan, acceptance criteria, and implementation diff.
5. Decide whether to merge, revise, or split the task.
EOF

cat > agent-workflow/prompts/01-architect.md <<'EOF'
# Architect Agent Prompt

You are the system architect for `score2gp`.

Your job is to analyse and plan. Do not implement source-code changes unless explicitly instructed later.

Read:

1. `README.md`
2. `docs/setup.md`
3. `docs/workflow.md`
4. `docs/scoreir.md`
5. `docs/musicxml-tabraw-build-ir.md`
6. `docs/private-diagnostics.md`
7. The relevant task folder under `agent-workflow/tasks/`

Produce or update:

```text
agent-workflow/tasks/<task-slug>/01-architecture-plan.md
```

Your output must include:

1. Current architecture summary.
2. Current implementation status.
3. Requirement interpretation.
4. Smallest safe implementation slice.
5. Files likely to change.
6. Data flow and artifact flow.
7. Risk areas.
8. Backout plan.
9. Test strategy.
10. Clear recommendation: proceed / split / blocked.

Hard limits:

- Do not rewrite unrelated code.
- Do not make speculative architecture changes.
- Do not claim full PDF-to-GP conversion works unless proven by tests.
- Keep private fixture content out of tracked files.
EOF

cat > agent-workflow/prompts/02-technical-product-owner.md <<'EOF'
# Technical Product Owner Agent Prompt

You are the technical product owner for `score2gp`.

Your job is to turn the task into acceptance criteria. Do not implement source-code changes.

Read:

1. The task's `00-master-task.md`
2. The task's `01-architecture-plan.md`
3. Relevant project docs

Produce or update:

```text
agent-workflow/tasks/<task-slug>/02-acceptance-criteria.md
```

Your output must include:

1. Requirement summary.
2. In-scope behaviour.
3. Out-of-scope behaviour.
4. Functional acceptance criteria.
5. Non-functional acceptance criteria.
6. Edge cases.
7. Test scenarios.
8. Definition of done.
9. Explicit failure conditions.

Be strict. If a requirement is vague, constrain it to the smallest safe useful version.
EOF

cat > agent-workflow/prompts/03-developer.md <<'EOF'
# Developer Agent Prompt

You are the developer agent for `score2gp`.

Your job is to implement the smallest safe slice that satisfies the agreed acceptance criteria.

Read:

1. `agent-workflow/tasks/<task-slug>/00-master-task.md`
2. `agent-workflow/tasks/<task-slug>/01-architecture-plan.md`
3. `agent-workflow/tasks/<task-slug>/02-acceptance-criteria.md`

Then inspect the codebase and implement.

Rules:

1. Work only in your dedicated developer worktree.
2. Keep changes minimal.
3. Do not rewrite unrelated modules.
4. Do not commit private copyrighted or licence-unclear files.
5. Do not commit generated `work/` artifacts.
6. Prefer deterministic public fixtures and tests.
7. If private fixtures are used, report only sanitized counts/statuses/artifact paths.
8. Run relevant tests before final response.
9. If tests fail, stop and explain the failure.

Produce or update:

```text
agent-workflow/tasks/<task-slug>/03-dev-implementation-log.md
```

Final response must include:

1. Files changed.
2. Behaviour changed.
3. Tests run.
4. Test result.
5. Known limitations.
6. Follow-up tasks.
EOF

cat > agent-workflow/prompts/04-reviewer.md <<'EOF'
# Reviewer Agent Prompt

You are the reviewer/test agent for `score2gp`.

Your job is to review the developer's implementation against the task, architecture plan, and acceptance criteria.

Read:

1. `agent-workflow/tasks/<task-slug>/00-master-task.md`
2. `agent-workflow/tasks/<task-slug>/01-architecture-plan.md`
3. `agent-workflow/tasks/<task-slug>/02-acceptance-criteria.md`
4. `agent-workflow/tasks/<task-slug>/03-dev-implementation-log.md`
5. The implementation diff

Run safe tests where possible.

Produce or update:

```text
agent-workflow/tasks/<task-slug>/04-review-report.md
```

Your review must include:

1. Pass/fail per acceptance criterion.
2. Bugs or regressions.
3. Missing tests.
4. Private-safety audit.
5. Generated-artifact audit.
6. Recommendation: approve / request changes / split task / block.

Do not make implementation changes unless explicitly instructed.
EOF

cat > agent-workflow/prompts/05-integration-manager.md <<'EOF'
# Integration Manager Prompt

You are the integration manager for `score2gp`.

Your job is to prepare the final handoff after review.

Read all task artifacts and the final diff.

Produce or update:

```text
agent-workflow/tasks/<task-slug>/05-integration-handoff.md
```

Include:

1. What changed.
2. Why it changed.
3. Branch name.
4. Tests run.
5. Review decision.
6. Merge readiness.
7. Rollback/backout commands.
8. Next recommended task.

Do not hide uncertainty. If the implementation does not prove the requirement, say so.
EOF

cat > agent-workflow/scripts/new-agent-task.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

TASK_SLUG="${1:-}"
TASK_TITLE="${2:-}"

if [[ -z "${TASK_SLUG}" || -z "${TASK_TITLE}" ]]; then
  echo "Usage: $0 <task-slug> <task-title>"
  echo 'Example: ./agent-workflow/scripts/new-agent-task.sh pdf-to-gp-smoke-v1 "Prove one owned lesson PDF can move through the safest supported conversion path"'
  exit 1
fi

TASK_DIR="agent-workflow/tasks/${TASK_SLUG}"
mkdir -p "${TASK_DIR}"

cat > "${TASK_DIR}/00-master-task.md" <<EOF2
# ${TASK_TITLE}

Task slug: \`${TASK_SLUG}\`

## Goal

Describe the goal here.

## Context

Describe relevant repo status, recent PRs, known constraints, and why this task matters.

## Constraints

- Keep private copyrighted or licence-unclear files local and untracked.
- Keep generated artifacts under ignored paths such as \`work/\`.
- Prefer public fixtures and deterministic tests.
- Do not claim full PDF-to-GP conversion works unless the task proves it.
- Keep implementation changes minimal.

## Required outputs

- Architecture plan
- Acceptance criteria
- Implementation
- Tests
- Review report
- Integration handoff

## Initial suggested slice

Replace this with the smallest useful implementation slice.
EOF2

touch "${TASK_DIR}/01-architecture-plan.md"
touch "${TASK_DIR}/02-acceptance-criteria.md"
touch "${TASK_DIR}/03-dev-implementation-log.md"
touch "${TASK_DIR}/04-review-report.md"
touch "${TASK_DIR}/05-integration-handoff.md"

echo "Created task folder: ${TASK_DIR}"
EOF

cat > agent-workflow/scripts/create-agent-worktrees.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

TASK_SLUG="${1:-}"
BASE_BRANCH="${2:-main}"

if [[ -z "${TASK_SLUG}" ]]; then
  echo "Usage: $0 <task-slug> [base-branch]"
  echo "Example: ./agent-workflow/scripts/create-agent-worktrees.sh pdf-to-gp-smoke-v1 main"
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
REPO_NAME="$(basename "${REPO_ROOT}")"
WORKTREE_ROOT="$(dirname "${REPO_ROOT}")/agent-worktrees/${TASK_SLUG}"

cd "${REPO_ROOT}"

git fetch origin
git switch "${BASE_BRANCH}"
git pull --ff-only origin "${BASE_BRANCH}"

mkdir -p "${WORKTREE_ROOT}"

create_worktree () {
  local role="$1"
  local branch="agent/${TASK_SLUG}/${role}"
  local path="${WORKTREE_ROOT}/${REPO_NAME}-${role}"

  if git show-ref --verify --quiet "refs/heads/${branch}"; then
    echo "Branch exists: ${branch}"
  else
    git branch "${branch}" "${BASE_BRANCH}"
  fi

  if [[ -d "${path}/.git" || -f "${path}/.git" ]]; then
    echo "Worktree already exists: ${path}"
  else
    git worktree add "${path}" "${branch}"
  fi
}

create_worktree "architect"
create_worktree "tpo"
create_worktree "developer"
create_worktree "reviewer"

cat <<EOF2

Created/verified worktrees under:

${WORKTREE_ROOT}

Open these folders separately in Antigravity:

${WORKTREE_ROOT}/${REPO_NAME}-architect
${WORKTREE_ROOT}/${REPO_NAME}-tpo
${WORKTREE_ROOT}/${REPO_NAME}-developer
${WORKTREE_ROOT}/${REPO_NAME}-reviewer

Recommended prompts:

architect -> agent-workflow/prompts/01-architect.md
tpo       -> agent-workflow/prompts/02-technical-product-owner.md
developer -> agent-workflow/prompts/03-developer.md
reviewer  -> agent-workflow/prompts/04-reviewer.md
EOF2
EOF

chmod +x agent-workflow/scripts/new-agent-task.sh
chmod +x agent-workflow/scripts/create-agent-worktrees.sh

touch agent-workflow/tasks/.gitkeep

cat <<'EOF'
Agent workflow files created.

Next:

1. Create a task:
   ./agent-workflow/scripts/new-agent-task.sh pdf-to-gp-smoke-v1 "Prove one owned lesson PDF can move through the safest currently supported conversion path"

2. Edit the task:
   nano agent-workflow/tasks/pdf-to-gp-smoke-v1/00-master-task.md

3. Create worktrees:
   ./agent-workflow/scripts/create-agent-worktrees.sh pdf-to-gp-smoke-v1 main

4. Open each worktree separately in Antigravity and give each one the matching prompt.
EOF
