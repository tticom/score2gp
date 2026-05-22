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

`HANDOFF.md` must include:
- current branch
- base branch
- current PR number and URL if one exists
- latest commit hash and subject
- working tree status
- tests/checks run and results
- GitHub check status if applicable
- private-safety status
- what changed in the task
- known limitations
- remaining risks
- next recommended task
- explicit scope boundaries, including what must not be started in the current branch

If the task stops early because of a failure, conflict, pending GitHub check, or missing information, update `HANDOFF.md` with:
- where it stopped
- exact failing/pending command or condition
- files involved
- safest next action

Do not put private musical content, private PDF text, private fret sequences, private titles, private URLs, private diagnostic output, or `work/` artifact contents into `HANDOFF.md`.

Keep `HANDOFF.md` private-safe and useful enough that a new agent can continue without reading previous chat history.
