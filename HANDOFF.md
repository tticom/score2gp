# HANDOFF

## Metadata
- **Current Branch**: `benchmark/major-triads-lessons-3-7-v0.1`
- **Base Branch**: `main`
- **Current PR**: [Draft PR #4 in score2gp-agentops](https://github.com/tticom/score2gp-agentops/pull/4) (for reporting)
- **Latest Local Commit**: `7c13ff20074b472f06c762b1374170b1db8ad133` ("docs: sync HANDOFF.md SHA to final commit") on product main
- **Working Tree Status**: Clean
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Benchmark Results (Lessons 3-7)

Durable, detailed agent-ops reviews live under:
`projects/score2gp/reviews/major-triads-lessons-3-7-benchmark-v0.1.md` in `score2gp-agentops`.

### Results Matrix

| Lesson | PDF Input | Gate A: Extraction | Gate B: Build-IR | Gate C: GP | Gate D: Round-Trip | Blocker Code / Category |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Lesson 3** | Available | `partial` | `refused` | `refused` | `refused` | `pdf_bar_box_edge_boundary_fallback_rejected`, `musicxml_timing_risk` |
| **Lesson 4** | Available | `partial` | `blocked` | `blocked` | `blocked` | `pdf_bar_box_edge_boundary_fallback_rejected` |
| **Lesson 5** | Available | `partial` | `blocked` | `blocked` | `blocked` | `pdf_bar_box_edge_boundary_fallback_rejected` |
| **Lesson 6** | Available | `partial` | `blocked` | `blocked` | `blocked` | `pdf_tab_staff_lines_fragmented` |
| **Lesson 7** | Available | `partial` | `blocked` | `blocked` | `blocked` | `pdf_bar_box_edge_boundary_fallback_rejected` |

### Lesson 3 Findings
- **Gate A Extraction**: Partially detected 49 systems and 61 bar boxes, but blocked on Page 1, System 7 due to fallback boundary rejection (`pdf_bar_box_edge_boundary_fallback_rejected`).
- **Gate B Build-IR**: Blocked by both the `partial` layout status and OMR MusicXML timing risks (`musicxml_timing_risk` with 74 underfull measures).
- **Strict ScoreIR Written**: No.
- **Semantic Round-Trip Passed**: No.

## next recommended task
- **Branch**: `feature/major-triads-layout-refinement-v0.1`
- **Goal**: Refine the system segmentation, barlines relative crossing logic, and outer edge boundaries to safely pass Gate A on Major Triads Lesson 3 without using pitch-based DP shortcuts.
- **Verification Requirement**: A properly aligned and checked clean MusicXML companion file is required to bypass OMR timing limits.

## Private-Safety Audit Result
- `git ls-files fixtures/private work` outputs exactly and only `fixtures/private/.gitkeep`.
- No private PDFs, GP files, or MXL files have been added to the tracking index.
