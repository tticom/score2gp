# Prove one owned lesson PDF can move through the safest currently supported conversion path

Task slug: `pdf-to-gp-smoke-v1`

## Goal

Goal: determine whether the current score2gp pipeline can take one owned/private lesson PDF through the safest currently supported conversion path toward a target Guitar Pro-style output, without overstating unsupported recognition.

The task should prefer existing implemented commands, public deterministic tests, and sanitized private diagnostics.

The expected result is not necessarily perfect PDF-to-GP conversion. The expected result is a clear, tested statement of what works now, what fails, what artifacts are produced, and what the next implementation blocker is.

## Context

Describe relevant repo status, recent PRs, known constraints, and why this task matters.

## Constraints

- Keep private copyrighted or licence-unclear files local and untracked.
- Keep generated artifacts under ignored paths such as `work/`.
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
