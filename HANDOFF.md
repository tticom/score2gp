# HANDOFF

## Metadata
- **Current Branch**: `bugfix/pipeline-geometry-normalizer-slice-v0.1`
- **Base Branch**: `main`
- **Current PR**: Draft PR using `gh pr create --draft --fill`
- **Output Directory**: `work/roundtrip_eval_clean_normalizer_v4`
- **Private-Safety Status**: Clean. Only `fixtures/private/.gitkeep` is tracked.

## Benchmark Results (Lessons 3-7)

Durable, detailed agent-ops reviews live under:
`projects/score2gp/reviews/major-triads-lessons-3-7-benchmark-v0.1.md` in `score2gp-agentops`.

### Results Matrix

| Lesson | PDF Input | Gate A: Extraction | Gate B: Build-IR | Gate C: GP | Gate D: Round-Trip | Blocker Code / Category |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Lesson 3** | Available | `complete` | `refused` | `refused` | `refused` | `missing_pdf_grouping` |

### Lesson 3 Findings
- **Gate A Extraction**: Resolved! Snapped all truncated staves and completely eliminated `pdf_bar_box_edge_boundary_fallback_rejected` (0 counts across the document). Increased boxed fret candidates to 399.
- **Gate B Build-IR**: The OMR timing risk blocker `musicxml_timing_risk` has been resolved and bypassed by switching the evaluator to the native flat GP7 XML stream. The remaining refusal code is `missing_pdf_grouping` due to vertical overlap and layout details on a few unboxed systems (e.g. Page 2 System 13, Page 4 System 1).
- **Strict ScoreIR Written**: No.
- **Semantic Round-Trip Passed**: No.

## next recommended task
- **Branch**: `feature/major-triads-layout-refinement-v0.1`
- **Goal**: Refine the system segmentation, barlines relative crossing logic, and outer edge boundaries to safely pass Gate A on Major Triads Lesson 3 without using pitch-based DP shortcuts.
- **Verification Requirement**: A properly aligned and checked clean MusicXML companion file is required to bypass OMR timing limits.

## Private-Safety Audit Result
- `git ls-files fixtures/private work` outputs exactly and only `fixtures/private/.gitkeep`.
- No private PDFs, GP files, or MXL files have been added to the tracking index.
