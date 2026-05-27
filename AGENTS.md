# AGENTS.md

This repository is an open-source-style experiment for converting owned PDF guitar scores into inspectable intermediate data and then into Guitar Pro 7 packages.

---

If the external score2gp-agentops repository is unavailable, stop and ask for guidance rather than proceeding without the review-governance rules.

- Be honest about recognition quality. Never claim perfect PDF-to-GP conversion.
- Do not bypass DRM or process scores the user does not own or have permission to process.
- Keep private fixtures under `fixtures/private/`; they are ignored by Git.
- Prefer staged outputs: rendered pages, overlays, raw extraction JSON, strict ScoreIR JSON, warnings, and reports.
- Unsupported notation must be surfaced in warnings or reports, not silently dropped.
- Keep modules small, typed, and tested.
- Code and tests must be written before any PR is raised. Do not create tasks or PRs solely to run tests or update markdown files. Validation and markdown updates must be performed as a result of actual code changes within the same task.
## 1. Ground Rules

- **Be Honest**: Never claim perfect PDF-to-GP conversion. Be honest about recognition and alignment quality.
- **Respect DRM**: Do not bypass DRM or process scores the user does not own or have permission to process.
- **Staged Outputs**: Prefer staged, human-inspectable intermediate artifacts: rendered pages, overlays, raw extraction JSON, strict ScoreIR JSON, warnings, and reports.
- **Notation Integrity**: Unsupported notation must be surfaced in warnings or reports, not silently dropped.
- **Engineering Quality**: Keep modules small, typed, and fully tested. Code and tests must be written before any pull request is raised.

---

## 2. Local Repository Safety Rules

- **No Direct Main Push**: Never push directly to `main`. On feature branches, push commits after all tests and checks pass.
- **Private File Protection**: Keep all private PDFs, companion MusicXML files, and derived conversion artifacts strictly inside gitignored folders (`fixtures/private/` and `work/`).
- **Prohibited Product Changes**: Do not implement OCR, scanned-PDF support, ML-based layout recognition, MusicXML timing repair, or automatic GPIF expansion unless explicitly requested.
- **Handoff Update Requirement**: Every completed task must leave `HANDOFF.md` updated with exact commit details, PR state, and checks run before reporting completion.

---

## 3. Standard Verification & Private-Safety Audit

Implementation agents must run and report the full verification matrix before concluding:

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

### Private-Safety Invariant
The command:
```bash
git ls-files fixtures/private work
```
must output **exactly and only**:
```text
fixtures/private/.gitkeep
```

---

## 4. Governance & Review Policy Routing

This repository does not host prompt templates, rejected claim logs, or review rubrics. All control-plane agentops policies are maintained in the external governance repository:

- **Canonical Review Rules**: See [REVIEW_RULES.md](https://github.com/tticom/score2gp-agentops/blob/main/projects/score2gp/REVIEW_RULES.md)
- **Active Benchmark Ladder**: See [BENCHMARK_LADDER.md](https://github.com/tticom/score2gp-agentops/blob/main/projects/score2gp/BENCHMARK_LADDER.md)
- **Acceptance Targets**: See [ACCEPTANCE_TARGETS.md](https://github.com/tticom/score2gp-agentops/blob/main/projects/score2gp/ACCEPTANCE_TARGETS.md)
- **Rejected Claims Register**: See [REJECTED_CLAIMS.md](https://github.com/tticom/score2gp-agentops/blob/main/projects/score2gp/REJECTED_CLAIMS.md)
- **Prompt and PR Templates**: See [projects/score2gp/](https://github.com/tticom/score2gp-agentops/tree/main/projects/score2gp)
