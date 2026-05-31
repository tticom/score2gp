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
