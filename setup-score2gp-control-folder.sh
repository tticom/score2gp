#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${1:-$HOME/work/score2gp-workspace}"
TASK_SLUG="${2:-pdf-to-gp-smoke-v1}"

CONTROL_DIR="${WORKSPACE_ROOT}/score2gp-control"
AGENT_WORKTREES="${WORKSPACE_ROOT}/agent-worktrees/${TASK_SLUG}"

mkdir -p "${CONTROL_DIR}"/{prompts,tasks,scripts,evidence,logs}
mkdir -p "${CONTROL_DIR}/tasks/${TASK_SLUG}/logs"

cat > "${CONTROL_DIR}/README.md" <<'EOF'
# score2gp-control

This folder is the shared controller space for the score2gp agent workflow.

It is not the implementation repo.

Use this folder for:

- Agent role prompts
- Master task files
- Architecture plans
- Acceptance criteria
- Test output summaries
- Sanitized evidence logs
- Review reports
- Integration handoffs
- Cross-agent coordination

Do not put private copyrighted PDFs, Guitar Pro files, MXL/MusicXML files, screenshots, overlays, generated conversion output, or large work artifacts here.

The implementation repo work happens in the role worktrees:

- score2gp-architect
- score2gp-tpo
- score2gp-developer
- score2gp-reviewer

The controller folder is the shared desk.
The worktrees are the working copies.
EOF

cat > "${CONTROL_DIR}/AGENT-RULES.md" <<'EOF'
# Agent Rules

## Global rules

1. Keep private copyrighted or licence-unclear fixtures local and untracked.
2. Do not place private PDFs, GP files, MXL/MusicXML files, screenshots, overlays, logs, or generated conversion artifacts in Git.
3. Use sanitized evidence only: counts, statuses, warning categories, command names, and artifact paths.
4. Do not claim full PDF-to-GP conversion works unless proven by reproducible tests.
5. Prefer public fixtures for automated tests.
6. Do not let multiple agents edit the same source worktree.
7. Do not allow documentation-only churn to masquerade as implementation progress.
8. Every proposed implementation slice must have a test or a clear explanation of why no test is possible.

## Role ownership

Architect:
- Researches, diagnoses failures, designs next changes.
- Writes architecture plans into score2gp-control.
- Does not edit implementation code.

TPO / Sceptic:
- Challenges the plan.
- Defines acceptance criteria and fake-progress blockers.
- Writes acceptance criteria into score2gp-control.
- Does not edit implementation code.

Developer:
- Reads controller docs.
- Implements only in the developer worktree.
- Updates implementation log in score2gp-control.
- Runs tests.

Reviewer:
- Reviews developer diff and test evidence.
- Writes review report into score2gp-control.
- Does not implement unless explicitly asked.

Human / Conductor:
- Decides whether to merge, revise, split, or stop.
EOF

cat > "${CONTROL_DIR}/prompts/01-architect.md" <<EOF
# Research Architect Prompt

You are the Research Architect for the score2gp project.

Your assigned source worktree is:

\`${AGENT_WORKTREES}/score2gp-architect\`

Your shared controller folder is:

\`${CONTROL_DIR}\`

Use the source worktree for reading code, docs, tests, and running safe diagnostics.
Use the controller folder for writing plans, evidence summaries, and task documents.

Before running terminal commands, run:

\`\`\`bash
cd "${AGENT_WORKTREES}/score2gp-architect"
pwd
git branch --show-current
git status --short
\`\`\`

Your role is researcher, system designer, failure analyst, and algorithmic diagnostician.

You are not the implementation developer. Do not make source-code changes unless explicitly asked later.

Primary goal:

Determine what about the current architecture, algorithm, assumptions, or pipeline design is preventing a score PDF from being converted safely into a useful Guitar Pro output, and produce a concrete design plan for what needs to change next.

Read at minimum:

- README.md
- docs/setup.md
- docs/workflow.md
- docs/scoreir.md
- docs/musicxml-tabraw-build-ir.md
- docs/private-diagnostics.md
- tests/
- src/score2gp/
- ${CONTROL_DIR}/tasks/${TASK_SLUG}/00-master-task.md
- any evidence under ${CONTROL_DIR}/evidence/ or ${CONTROL_DIR}/tasks/${TASK_SLUG}/logs/

Write your output to:

\`${CONTROL_DIR}/tasks/${TASK_SLUG}/01-architecture-plan.md\`

The architecture plan must include:

1. Current pipeline summary.
2. Current test status.
3. Current conversion status.
4. Observed failure or limitation.
5. Likely root cause category:
   - architecture
   - algorithm
   - recognition theory
   - data/fixture quality
   - implementation bug
   - missing dependency
   - unsupported feature
6. What assumptions appear wrong or risky.
7. What evidence supports that conclusion.
8. What should change next.
9. The smallest useful implementation slice.
10. Files/modules likely to change.
11. Tests that should prove the change.
12. Risks and backout plan.
13. Clear recommendation: proceed, split, block, or abandon this route.

Hard limits:

- Do not write implementation code.
- Do not edit developer, TPO, or reviewer worktrees.
- Do not claim full PDF-to-GP conversion works unless proven.
- Do not write private fixture content into controller docs.
EOF

cat > "${CONTROL_DIR}/prompts/02-tpo-sceptic.md" <<EOF
# TPO / Sceptic Prompt

You are the Technical Product Owner and Sceptic for the score2gp project.

Your assigned source worktree is:

\`${AGENT_WORKTREES}/score2gp-tpo\`

Your shared controller folder is:

\`${CONTROL_DIR}\`

Use the source worktree for reading the repo and running safe checks.
Use the controller folder for writing acceptance criteria and sceptical review.

Before running terminal commands, run:

\`\`\`bash
cd "${AGENT_WORKTREES}/score2gp-tpo"
pwd
git branch --show-current
git status --short
\`\`\`

Your job is to protect the project from fake progress.

You are not here to be agreeable. You are here to spot when we are polishing a turd, over-documenting, overfitting to synthetic fixtures, hiding behind handoffs, or pretending that partial diagnostics equal real conversion capability.

Read:

- ${CONTROL_DIR}/tasks/${TASK_SLUG}/00-master-task.md
- ${CONTROL_DIR}/tasks/${TASK_SLUG}/01-architecture-plan.md
- README.md
- docs/workflow.md
- docs/private-diagnostics.md
- relevant tests and test outputs

Write your output to:

\`${CONTROL_DIR}/tasks/${TASK_SLUG}/02-acceptance-criteria.md\`

You must answer:

1. What is the real product outcome being attempted?
2. What would prove that the system has moved closer to PDF-to-GP conversion?
3. What would be fake progress?
4. Are we only improving docs, handoffs, or diagnostics without improving conversion capability?
5. Are we overfitting to synthetic fixtures?
6. Are private fixture results being reported safely and honestly?
7. What is the smallest acceptance test that proves real progress?
8. What should be explicitly out of scope?
9. What would cause you to block the task?
10. What should the Developer implement next, if anything?

If the Architect plan is too broad, narrow it.
If the plan does not produce testable converter progress, reject it.
If the current approach is fundamentally weak, say so directly.
If the right next move is not coding, say what evidence is missing.

Do not write source code.
EOF

cat > "${CONTROL_DIR}/prompts/03-developer.md" <<EOF
# Developer Prompt

You are the Developer agent for score2gp.

Your assigned source worktree is:

\`${AGENT_WORKTREES}/score2gp-developer\`

Your shared controller folder is:

\`${CONTROL_DIR}\`

Before running terminal commands, run:

\`\`\`bash
cd "${AGENT_WORKTREES}/score2gp-developer"
pwd
git branch --show-current
git status --short
\`\`\`

Read:

- ${CONTROL_DIR}/tasks/${TASK_SLUG}/00-master-task.md
- ${CONTROL_DIR}/tasks/${TASK_SLUG}/01-architecture-plan.md
- ${CONTROL_DIR}/tasks/${TASK_SLUG}/02-acceptance-criteria.md

Implement only the smallest safe slice approved by the Architect and TPO.

Rules:

1. Work only in the developer worktree.
2. Keep changes minimal.
3. Do not rewrite unrelated modules.
4. Do not commit private copyrighted or licence-unclear files.
5. Do not commit generated work artifacts.
6. Prefer deterministic public fixtures and tests.
7. If private fixtures are used, report only sanitized counts, statuses, warning categories, and artifact paths.
8. Run relevant tests before final response.
9. If tests fail, stop and explain the failure.

Write your implementation log to:

\`${CONTROL_DIR}/tasks/${TASK_SLUG}/03-dev-implementation-log.md\`

The log must include:

1. Files changed.
2. Behaviour changed.
3. Tests run.
4. Test result.
5. Known limitations.
6. Follow-up tasks.
EOF

cat > "${CONTROL_DIR}/prompts/04-reviewer.md" <<EOF
# Reviewer Prompt

You are the Reviewer agent for score2gp.

Your assigned source worktree is:

\`${AGENT_WORKTREES}/score2gp-reviewer\`

Your shared controller folder is:

\`${CONTROL_DIR}\`

Before running terminal commands, run:

\`\`\`bash
cd "${AGENT_WORKTREES}/score2gp-reviewer"
pwd
git branch --show-current
git status --short
\`\`\`

Your job is to review the developer's implementation against the task, architecture plan, and acceptance criteria.

Read:

- ${CONTROL_DIR}/tasks/${TASK_SLUG}/00-master-task.md
- ${CONTROL_DIR}/tasks/${TASK_SLUG}/01-architecture-plan.md
- ${CONTROL_DIR}/tasks/${TASK_SLUG}/02-acceptance-criteria.md
- ${CONTROL_DIR}/tasks/${TASK_SLUG}/03-dev-implementation-log.md
- the developer branch/diff

Write your review to:

\`${CONTROL_DIR}/tasks/${TASK_SLUG}/04-review-report.md\`

Your review must include:

1. Pass/fail per acceptance criterion.
2. Bugs or regressions.
3. Missing tests.
4. Private-safety audit.
5. Generated-artifact audit.
6. Recommendation: approve, request changes, split task, or block.

Do not make implementation changes unless explicitly asked.
EOF

cat > "${CONTROL_DIR}/tasks/${TASK_SLUG}/00-master-task.md" <<'EOF'
# pdf-to-gp-smoke-v1

## Goal

Determine whether the current score2gp pipeline can take one owned/private lesson PDF through the safest currently supported conversion path toward a target Guitar Pro-style output, without overstating unsupported recognition.

The expected result is not necessarily perfect PDF-to-GP conversion.

The expected result is a clear, tested statement of:

1. What works now.
2. What fails.
3. What artifacts are produced.
4. What the next implementation blocker is.
5. What needs to change architecturally or algorithmically.

## Context

score2gp is a staged command-line toolkit for converting owned PDF guitar scores into inspectable intermediate data and eventually Guitar Pro 7 `.gp` files.

The project should not pretend that printed music recognition is solved. Every stage should leave inspectable artifacts that a musician or developer can validate.

## Constraints

- Keep private copyrighted or licence-unclear files local and untracked.
- Keep generated artifacts under ignored paths such as `work/`.
- Use sanitized private evidence only.
- Prefer public deterministic fixtures for automated tests.
- Do not claim full PDF-to-GP conversion works unless proven.
- Do not allow documentation-only churn to count as implementation progress.

## Required outputs

- Architecture plan
- Acceptance criteria
- Implementation log
- Review report
- Integration handoff

## Initial suggested slice

Prove the safest current smoke path using the existing CLI and diagnostics. If the smoke path fails, classify the failure honestly and identify the smallest implementation change that would improve real conversion capability.
EOF

touch "${CONTROL_DIR}/tasks/${TASK_SLUG}/01-architecture-plan.md"
touch "${CONTROL_DIR}/tasks/${TASK_SLUG}/02-acceptance-criteria.md"
touch "${CONTROL_DIR}/tasks/${TASK_SLUG}/03-dev-implementation-log.md"
touch "${CONTROL_DIR}/tasks/${TASK_SLUG}/04-review-report.md"
touch "${CONTROL_DIR}/tasks/${TASK_SLUG}/05-integration-handoff.md"

cat > "${CONTROL_DIR}/scripts/status.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail

TASK_SLUG="\${1:-${TASK_SLUG}}"
WORKSPACE_ROOT="\${2:-${WORKSPACE_ROOT}}"
CONTROL_DIR="\${WORKSPACE_ROOT}/score2gp-control"
AGENT_ROOT="\${WORKSPACE_ROOT}/agent-worktrees/\${TASK_SLUG}"

echo "Controller:"
echo "  \${CONTROL_DIR}"
echo

echo "Task files:"
ls -la "\${CONTROL_DIR}/tasks/\${TASK_SLUG}"
echo

for role in architect tpo developer reviewer; do
  WT="\${AGENT_ROOT}/score2gp-\${role}"
  echo "=== \${role}: \${WT} ==="
  if [[ -d "\${WT}" ]]; then
    (
      cd "\${WT}"
      echo -n "branch: "
      git branch --show-current
      echo "status:"
      git status --short
      if [[ -d .venv ]]; then
        echo "venv: present"
      else
        echo "venv: missing"
      fi
    )
  else
    echo "missing"
  fi
  echo
done
EOF
chmod +x "${CONTROL_DIR}/scripts/status.sh"

cat > "${CONTROL_DIR}/scripts/capture-pytest.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail

ROLE="\${1:-architect}"
TASK_SLUG="\${2:-${TASK_SLUG}}"
WORKSPACE_ROOT="\${3:-${WORKSPACE_ROOT}}"

WT="\${WORKSPACE_ROOT}/agent-worktrees/\${TASK_SLUG}/score2gp-\${ROLE}"
CONTROL_DIR="\${WORKSPACE_ROOT}/score2gp-control"
OUT="\${CONTROL_DIR}/tasks/\${TASK_SLUG}/logs/pytest-\${ROLE}-latest.txt"

cd "\${WT}"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
mkdir -p "\$(dirname "\${OUT}")"
python -m pytest 2>&1 | tee "\${OUT}"

echo
echo "Saved pytest output to:"
echo "\${OUT}"
EOF
chmod +x "${CONTROL_DIR}/scripts/capture-pytest.sh"

cat > "${CONTROL_DIR}/scripts/capture-developer-diff.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail

TASK_SLUG="\${1:-${TASK_SLUG}}"
WORKSPACE_ROOT="\${2:-${WORKSPACE_ROOT}}"

DEV="\${WORKSPACE_ROOT}/agent-worktrees/\${TASK_SLUG}/score2gp-developer"
OUT="\${WORKSPACE_ROOT}/score2gp-control/tasks/\${TASK_SLUG}/logs/developer-diff.patch"

cd "\${DEV}"
mkdir -p "\$(dirname "\${OUT}")"
git diff --stat > "\${OUT}.stat"
git diff > "\${OUT}"

echo "Saved developer diff:"
echo "\${OUT}.stat"
echo "\${OUT}"
EOF
chmod +x "${CONTROL_DIR}/scripts/capture-developer-diff.sh"

cat > "${CONTROL_DIR}/.gitignore" <<'EOF'
*.pdf
*.gp
*.gpif
*.mxl
*.musicxml
*.xml
*.png
*.jpg
*.jpeg
*.webp
*.omr
*.zip
work/
private/
raw/
generated/
logs/private*
evidence/private*
EOF

echo
echo "Controller folder created:"
echo "${CONTROL_DIR}"
echo
echo "Add this folder to the Antigravity project using:"
if command -v wslpath >/dev/null 2>&1; then
  wslpath -w "${CONTROL_DIR}"
else
  echo "${CONTROL_DIR}"
fi
echo
echo "Check status with:"
echo "${CONTROL_DIR}/scripts/status.sh ${TASK_SLUG} ${WORKSPACE_ROOT}"
echo
