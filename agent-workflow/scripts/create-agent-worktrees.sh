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
