# Architecture: PDF-Tab Duration Candidate Extraction & Association

**Task:** PDFTAB-DUR-03 (PDF-Tab Duration Candidate Extraction Architecture)
**Date:** 2026-07-28
**Status:** PROPOSED ARCHITECTURE

---

## 1. Pinned Provenance and Revisions

- **Product Repository**: `tticom/score2gp`
  - Target Branch: `agy/pdftab-duration-extraction-architecture`
  - Base Commit: `1a013cef0f242f1a75428c1ddfa77c251a2b22f0`
  - Python Executable: `/home/tticom-automation/work/score2gp-workspace/score2gp/.venv/bin/python`
- **AgentOps Repository**: `tticom/score2gp-agentops`
  - Base Commit: `b8b5a2ed4ddd55586f46667cc149d6fe2019c185`
- **Workflow Skills Lock**: `0d6d84879eff0d352b444fdeceb3bb7a098e0c47`
- **Public Synthetic Fixture Baseline**:
  - Generator: `tests/fixtures/pdf/make_generated_pdf_tab_duration_pdf.py` (SHA-256: `60a1d532ec79783490bd9005329c8593c8bdfb39973d864acf2facec8fa8b1f7`)
  - Fixture PDF: `tests/fixtures/pdf/generated_pdf_tab_duration.pdf` (SHA-256: `e18d4aaedb51eed6135c75ee7aa280f604ac19753d49e98f14bfa152633e57fd`)
  - Unit Test: `tests/test_pdf_tab_duration_fixture.py` (SHA-256: `5e8e104c689781b233ef497c70a5545222044ba14dc50fdaeaadd9399f6bc202`)

---

## 2. Context & Problem Statement

Currently, PDF-only tablature bar assembly (`pdf_tab_bar_assembler.py` and `pdf_tab_measure_timing.py`) computes measure timing via `select_pdf_tab_grid_spacing_and_duration_name`. This existing heuristic calculates a single uniform grid tick spacing and nominal duration based strictly on event subgroup count $N$ per measure:
- $N \le 8 \implies$ 480 ticks (`eighth` note)
- $N \le 16 \implies$ 240 ticks (`16th` note)
- $N \le 32 \implies$ 120 ticks (`32nd` note)

While this equal-spacing fallback functions for unstemmed ASCII/PDF tabs (e.g. `generated_tiny_tab.pdf`), it fails to utilize explicit visual rhythm notation (drawn vertical stems, horizontal beams, and diagonal flags) present in standard PDF tablature scores.

The audit in AgentOps PR #386 and synthetic fixture PR #391 established that `NotationStaffDiagnostics` extracts stem, beam, and flag candidates from PDF page drawings. However, no architectural bridge exists to pass these duration morphology candidates into `TabRaw` or `assemble_pdf_tab_bar`.

This document specifies:
1. Dataflow seam and schema extensions for duration candidate evidence.
2. Spatial association tolerances connecting fret events to stems, beams, and flags.
3. Fallback boundary for unstemmed tab staves.
4. Tier B testable developer implementation roadmap.

---

## 3. Inspected Evidence & Baseline Audit

### Source Code Modules Inspected
- `src/score2gp/pdf_staff_notation_diagnostics.py`: Extracts morphology primitives (`vertical_stroke_candidate`, `non_staff_horizontal`, `curve`, `rect`, `flag_candidates`, `beam_candidates`) per staff.
- `src/score2gp/pdf_staff_geometry.py`: Defines diagnostic dataclasses including `NotationStaffDiagnostics`, `StaffFlagBeamCandidateDiagnostics`, `XAlignedPrimitiveClusterEvidence`.
- `src/score2gp/tabraw.py`: Defines `TabCandidate` and `TabRaw` container models.
- `src/score2gp/pdf_tab_bar_assembler.py`: Manages per-bar event subgrouping, duration assignment, measure capacity, and remainder rest decomposition.
- `src/score2gp/pdf_tab_measure_timing.py`: Computes grid spacing and nominal durations.
- `src/score2gp/pdf_only_chord_event_grouper.py`: Groups fret candidates into simultaneous chord subgroups by horizontal $x$-tolerance ($3.0\text{ pt}$).

### Diagnostic Findings from `generated_pdf_tab_duration.pdf`
- **Bar 1**: 4 quarter notes on open string 1 with vertical stems extending below the bottom staff line ($y=220 \to 238$). 0 beams, 0 flags.
- **Bar 2**:
  - 2 eighth notes with vertical stems + diagonal flag strokes.
  - 2 eighth notes with vertical stems + 1 horizontal beam stroke ($y=238$, `width=3.0`).
  - 4 sixteenth notes with vertical stems + 2 horizontal beam strokes ($y=238, 234$).
- **Diagnostics Output**: `build_notation_diagnostics` successfully extracts 6 horizontal staff lines, 15 vertical stroke candidates (3 barlines + 12 stems), 3 non-staff horizontal beam strokes, and 12 fret text spans.

---

## 4. Interface & Dataflow Definition

### Architectural Seam

```
┌─────────────────────────────────────────────────────────────┐
│ PyMuPDF Page Drawings / Text Spans                          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ pdf_staff_notation_diagnostics.py                           │
│ - Extracts Staff Notation & Morphology Candidates           │
│ - Emits NotationStaffDiagnostics (Stems, Beams, Flags)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ pdf_tab_duration_candidate_associator.py (NEW)              │
│ - Maps stem/beam/flag primitives to TabCandidate / Subgroup │
│ - Emits TabDurationEvidence per event subgroup              │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ TabRaw / TabCandidate Extension                             │
│ - Preserves duration_candidate in candidate/bar metadata    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ assemble_pdf_tab_bar (pdf_tab_bar_assembler.py)             │
│ - Uses explicit TabDurationEvidence when present            │
│ - Falls back to select_pdf_tab_grid_spacing_and_duration_name│
│   when staves are unstemmed                                 │
└─────────────────────────────────────────────────────────────┘
```

### Proposed Schema Extensions

#### 1. `TabDurationCandidate` (in `src/score2gp/pdf_tab_duration_types.py`)

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class TabDurationEvidence:
    duration_name: Literal["whole", "half", "quarter", "eighth", "16th", "32nd", "64th"]
    duration_ticks: int
    stem_present: bool = False
    beam_count: int = 0
    flag_count: int = 0
    confidence: float = 1.0
    source: Literal["visual_morphology", "equal_spacing_fallback"] = "visual_morphology"
```

#### 2. Candidate Metadata Injection
In `TabCandidate.raw`, attach optional `duration_evidence`:
```json
{
  "duration_evidence": {
    "duration_name": "eighth",
    "duration_ticks": 480,
    "stem_present": true,
    "beam_count": 1,
    "flag_count": 0,
    "source": "visual_morphology"
  }
}
```

---

## 5. Stem, Beam, and Flag Spatial-Association Rules

### Rule 1: Vertical Stem to Fret Event Association
A vertical stroke primitive $S = [x_{s0}, y_{s0}, x_{s1}, y_{s1}]$ attaches to an event subgroup $E$ centered at $x_E$ on staff system $\text{Staff}_i$ if:
1. **Horizontal Proximity**:
   $$|x_S - x_E| \le \Delta x_{\text{stem\_tol}} \quad \text{where } \Delta x_{\text{stem\_tol}} = \max(6.0\text{ pt}, 0.6 \times \text{staff\_space})$$
2. **Vertical Attachment**:
   The top endpoint $y_{s0}$ (for downward stems) or bottom endpoint $y_{s1}$ (for upward stems) touches or lies within $\Delta y_{\text{attach}} = 1.5 \times \text{staff\_space}$ of the top or bottom staff line.

### Rule 2: Beam Stroke to Vertical Stem Association
A horizontal non-staff stroke $B = [x_{b0}, y_{b0}, x_{b1}, y_{b1}]$ with width $w_B = x_{b1} - x_{b0} \ge 0.5 \times \text{staff\_space}$ attaches to vertical stem $S$ at position $x_S$ if:
1. **Horizontal Overlap**:
   $$x_{b0} - \epsilon \le x_S \le x_{b1} + \epsilon \quad \text{where } \epsilon = 4.0\text{ pt}$$
2. **Vertical Stem Extension**:
   $$|y_{b0} - y_{\text{stem\_free\_end}}| \le \Delta y_{\text{beam\_tol}} \quad \text{where } \Delta y_{\text{beam\_tol}} = 6.0\text{ pt}$$

Multiple stacked beams at the same stem endpoint increment the `beam_count` $k$.

### Rule 3: Flag Stroke to Vertical Stem Association
A diagonal or curved primitive $F = [x_{f0}, y_{f0}, x_{f1}, y_{f1}]$ attaches to vertical stem $S$ if:
1. **Endpoint Contact**:
   $$\sqrt{(x_{f0} - x_S)^2 + (y_{f0} - y_{\text{stem\_free\_end}})^2} \le 8.0\text{ pt}$$

### Duration Resolution Table

| Stem Present | Beam Count $k$ | Flag Count $m$ | Resolved Nominal Duration | Ticks |
| :---: | :---: | :---: | :--- | :---: |
| `False` | 0 | 0 | *Fallback to equal spacing* | *Variable* |
| `True` | 0 | 0 | `quarter` | 960 |
| `True` | 1 | 0 | `eighth` | 480 |
| `True` | 0 | 1 | `eighth` | 480 |
| `True` | 2 | 0 | `16th` | 240 |
| `True` | 0 | 2 | `16th` | 240 |
| `True` | 3 | 0 | `32nd` | 120 |

---

## 6. Fallback Boundary & Fail-Closed Safety

1. **Unstemmed Staff Fallback**:
   If a PDF tab staff contains no vertical stem candidates attached to fret event subgroups, the associator emits `source = "equal_spacing_fallback"`, triggering `select_pdf_tab_grid_spacing_and_duration_name(N)` to preserve 100% backward compatibility for unstemmed/ASCII tabs.

2. **Partial Stemming Safety**:
   If some events in a measure have stem/beam evidence while others do not, explicit evidence takes precedence for stemmed events, and unstemmed events default to quarter notes unless bounded by measure capacity.

3. **Measure Capacity Enforcement**:
   Total measure tick capacity ($\sum \text{duration\_ticks} \le 3840$) is strictly enforced by `is_within_pdf_tab_measure_capacity`. If visual duration candidates cause a measure to exceed 3840 ticks, assembly fails closed with `PdfTabBarAssemblerError("pdf_only_tab_measure_overcapacity")`.

---

## 7. Implementation Slicing Plan

To implement this architecture safely without breaking existing tests, the work is divided into four small, testable developer implementation slices.

```
┌────────────────────────────────────────────────────────────────────────┐
│ Slice 1: Duration Types & Spatial Associator Primitive                 │
│ - Create pdf_tab_duration_types.py & associator module                 │
│ - Unit test against extracted morphology primitives                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Slice 2: Integration into TabRaw / TabCandidate Pipeline               │
│ - Attach duration evidence to TabCandidate metadata in TabRaw          │
│ - Unit test schema validation and serialization                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Slice 3: Assembler Integration & Oracle Verification                   │
│ - Wire explicit duration evidence into assemble_pdf_tab_bar            │
│ - Verify generated_pdf_tab_duration.pdf oracle passes 100%             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Slice 4: Regression Audit & Hardening                                  │
│ - Run full test suite & agent_verify.py across all public fixtures     │
│ - Verify unstemmed fallback behaviour remains unchanged                │
└────────────────────────────────────────────────────────────────────────┘
```

### Developer Prompt Slices

#### Slice 1 Prompt (Types & Associator Primitive)
```markdown
Title: Implement pdf_tab_duration_associator.py

Goal: Create `src/score2gp/pdf_tab_duration_associator.py` and dataclasses in `src/score2gp/pdf_tab_duration_types.py`.
Implement spatial association functions matching `docs/design/pdf-tab-duration-candidate-extraction.md`.
Add unit tests in `tests/test_pdf_tab_duration_associator.py` verifying stem, beam, and flag candidate matching against `generated_pdf_tab_duration.pdf` primitives.
```

#### Slice 2 Prompt (TabRaw Pipeline Integration)
```markdown
Title: Integrate duration evidence into TabRaw candidates

Goal: Extend `TabCandidate` raw metadata to store optional `TabDurationEvidence`.
Update TabRaw factory to preserve duration evidence during PDF-tab extraction.
Add unit tests verifying schema validation and serialization in `tests/test_tabraw_duration_metadata.py`.
```

#### Slice 3 Prompt (Assembler & Oracle Verification)
```markdown
Title: Wire duration evidence into assemble_pdf_tab_bar

Goal: Update `assemble_pdf_tab_bar` in `src/score2gp/pdf_tab_bar_assembler.py` to inspect `TabDurationEvidence` per event subgroup.
Assign explicit durations when visual evidence is present; fall back to equal spacing when unstemmed.
Verify that `generated_pdf_tab_duration.pdf` extracts quarter, eighth, and sixteenth notes per the expected oracle.
```

---

## 8. Disconfirmation Record & Non-Goals Confirmed

- **No Product Source Edits in Architecture Phase**: `src/score2gp/` remained strictly read-only during Task PDFTAB-DUR-03.
- **No Private Inputs or GP Leakage**: All design decisions were verified against public synthetic fixtures (`generated_pdf_tab_duration.pdf`, `generated_tiny_tab.pdf`).
- **No Premature Implementation**: Code changes will take place under separately promoted developer implementation tasks.
