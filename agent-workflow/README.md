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
