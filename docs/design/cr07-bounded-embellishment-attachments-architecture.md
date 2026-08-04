# CR-07 Bounded Embellishment Attachments Architecture

## 1. Executive Summary

This document establishes a generic, testable, and decoupled technical architecture for score2gp PDF conversion to independently classify and attach bounded embellishments (such as vibrato, slides, bends, hammer-ons, pull-offs, and palm muting).

### Key Architectural Invariants
- **Source-Target Proximity & String Identity:** Slide and slur/legato embellishments must only link notes sharing the same string identity (or adjacent coordinates for position shifts) and sequential temporal order.
- **Single-Note vs. Chordal Selection:** Chordal vibrato (applied to a vertical chord stack) must be represented structurally at the event/track level or propagated uniformly across all chord notes, whereas single-note vibrato applies only to the individual note on a single string.
- **Span-Based Boundaries:** Embellishments spanning multiple beats or measures (like palm muting and let-ring) must be bound using explicit onset-to-end-event ID ranges rather than arbitrary global text scopes.
- **Decoupled Evidence Models:** Visual indicators (curves, wavy paths, diagonal lines) and text indicators (e.g. "P.M.", "sl.") must have separate, decoupled evidence classes before being unified at the alignment stage.

- **Selected Outcome**: **`CONTINUE`** (evidence supports one bounded Developer implementation slice `CR-07A` on the PDF-tab seam for visual vibrato and slide indicators).

---

## 2. Baseline Revisions & Maintainer Authorization

- **Governance Repository Baseline**: `5477038e44bd6ba8e362781eb22fdf6039802533` (`tticom/score2gp-agentops`)
- **Product Repository Baseline**: `f3cf042c96defdaf09c3353f16f9dbcb38e542d3` (`tticom/score2gp`, `origin/main`)
- **Maintainer Authorization**: Present maintainer authorization explicitly accepts current product `origin/main` as the baseline for CR-07 research without requiring historical reconstruction of earlier task records.

---

## 3. Verified Repository Facts & Trace Analysis

Source-code tracing across [gpif.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/gpif.py), [ir.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/ir.py), [pdf.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/pdf.py), [tabraw.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/tabraw.py), and [build_ir.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/build_ir.py) establishes the following empirical facts:

### 3.1 ScoreIR and GPIF Representation
- **Exact File & Models**: [ir.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/ir.py) lines 320–480.
  - `VibratoTechnique`: Represents vibrato with optional fields `width: Literal["narrow", "wide", "unknown"]`, `speed: Literal["slow", "medium", "fast", "unknown"]`, and `curve: VibratoCurve | None`.
  - `SlideTechnique`: Represents slide with `style` and optional `target_event_id`.
  - `HammerOnTechnique` / `PullOffTechnique`: Represent slur-based legato techniques with `target_event_id: str | None` and `legato: bool`.
  - `PalmMuteTechnique` / `LetRingTechnique`: Span-based embellishments carrying `end_event_id: str | None`.
- **GPIF Serialization**: [gpif.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/gpif.py) lines 50–100 and 2030–2040.
  - `_collect_duration_techniques()` parses let-ring and palm-mute techniques, mapping them to absolute timelines to label every affected note in the chord/span.
  - `Vibrato` properties map note-level vibrato to XML nodes `<Vibrato WaveSize="Wide"| "Slight">` and `<VibratoCurve>`.

### 3.2 Detection on the PDF-Tab Seam
- **Exact File**: [pdf.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/pdf.py).
  - **Fact**: No visual curves, wavy paths, or diagonal lines are currently extracted or classified by the PDF parsing engine.
  - Text-based techniques are extracted via regex from PyMuPDF `words` lists (e.g. matching "P.M.", "sl.") and classified as `technique_text` category candidates in [tabraw.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/tabraw.py).
- **Proximity Attachment**: [build_ir.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/build_ir.py) lines 4080–4210.
  - Technique text candidates are aligned to the nearest notehead/event within a bar using horizontal `x` proximity. If multiple notes exist at the same distance, it triggers `ambiguous_technique_attachment` warnings.

---

## 4. Hypotheses and Unknowns Ledger

| ID | Subject / Claim | Status | Controlling Facts & Seams | Unknown / Deferred Boundary |
|---|-----------------|--------|---------------------------|-----------------------------|
| **H-01** | Wavy line paths can be distinguished from horizontal staff lines | Provisional | `pdf.py:_detect_tab_systems()` line detection | Distinguishing short vibrato wavy shapes from broken/fragmented staff lines requires aspect ratio and oscillation limits. |
| **H-02** | Diagonal lines representing slides can be isolated from stems/beams | Provisional | `pdf_geometry.py:_drawing_segments()` | Slanted lines must have a slope $|m| \in [0.1, 2.0]$ to be separated from vertical stems ($|m| > 10.0$) and horizontal lines ($|m| < 0.05$). |
| **H-03** | Slurs can be mapped using control points of bezier curves | Provisional | `fitz` page drawings `"c"` items | PyMuPDF curve `"c"` items represent bezier arcs; parsing control points to calculate start/end endpoints requires geometric projection to staves. |

---

## 5. Claim-by-Claim Evidence Ledger

| Claim ID | Claim Description | Repository Source / Evidence | Classification | Failure Mode Ruled Out |
|----------|-------------------|------------------------------|----------------|------------------------|
| **C-01** | Visual vibrato curves are not extracted from PDFs | [pdf.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/pdf.py) search for `vibrato` | Verified Fact | Ruled out the claim that visual vibrato is currently processed in PDF OMR. |
| **C-02** | Slides are only parsed via text "sl." candidates | [build_ir.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/build_ir.py) lines 4130-4180 | Verified Fact | Ruled out visual diagonal slide parsing in the current version. |
| **C-03** | Palm mute applies to all notes in span | [gpif.py](file:///home/tticom/work/score2gp-workspace/score2gp/src/score2gp/gpif.py) lines 50-90 | Verified Fact | Confirmed span-based replication matches GP7 specifications. |

---

## 6. Proposed Embellishment Integration Architecture

To support visual OMR extraction of embellishments, we define three decoupled evidence layers:

```
    [PDF Page Vector Drawings]
                │
                ├──> [wavy_line paths]   ──> VisualVibratoEvidence (staff, bbox)
                ├──> [diagonal_line]     ──> VisualSlideEvidence (staff, x0, y0, x1, y1)
                └──> [arc curves ("c")]  ──> VisualSlurEvidence (staff, x_start, x_end)
```

### 6.1 Visual Vibrato Detection Rule
- A vector path containing multiple vertical oscillations (alternating $y$ directions within a small $x$ range) is classified as a **Visual Vibrato**.
- **Attachment Proximity:** Target is the note/event at staff $s$ whose horizontal center $x_{note} \in [x_0 - 10.0, x_1 + 10.0]$ and is positioned immediately above the staff line.
- **Chordal Control:** If multiple notes exist at the same $x$, assign the vibrato technique to all notes in that chord (chordal vibrato).

### 6.2 Visual Slide Detection Rule
- A slanted line segment with slope $|m| \in [0.1, 2.0]$ that starts near $x_{start}$ and ends near $x_{end}$ is classified as a **Visual Slide**.
- **Attachment Proximity:** Connects note $A$ (closest to $x_{start}, y_{start}$) and note $B$ (closest to $x_{end}, y_{end}$). String identity of Note $A$ and Note $B$ must match.

### 6.3 Visual Palm Mute Span Detection Rule
- A dashed horizontal line or bracket with text `"P.M."` defines a horizontal span `[x_PM_start, x_PM_end]`.
- All notes on the staff within this span receive the `PalmMuteTechnique` property.

---

## 7. Decoupled Pydantic Evidence Models

```python
from typing import Literal
from pydantic import BaseModel, Field

class VisualVibratoEvidence(BaseModel):
    """Visual wavy-line vibrato candidate."""
    id: str
    bbox: list[float]
    page_index: int
    system_index: int
    staff_index: int
    oscillation_count: int = Field(ge=2)
    style: Literal["slight", "wide", "unknown"] = "unknown"

class VisualSlideEvidence(BaseModel):
    """Visual diagonal-line slide candidate."""
    id: str
    x0: float
    y0: float
    x1: float
    y1: float
    page_index: int
    system_index: int
    staff_index: int
    string_index: int | None = None
    direction: Literal["up", "down", "unknown"] = "unknown"
```

---

## 8. Outcome & Recommended Developer Implementation Slice

- **Selected Outcome**: **`CONTINUE`** (evidence supports one bounded Developer implementation slice `CR-07A` on the PDF-tab seam).

### 8.1 Bounded Developer Implementation Slice: `CR-07A`
- **Slice Name**: `CR-07A: Bounded Visual Vibrato and Slide Glyphs Evidence Seam`
- **Authorized Product Files**:
  - `src/score2gp/pdf_geometry.py`
  - `src/score2gp/pdf.py`
  - `tests/test_cr07_embellishment_attachments.py` (new test file)
- **Scope**:
  - Implement visual detection of wavy-line paths (vibrato) and diagonal-line paths (slides) inside PyMuPDF drawings.
  - Map these visual candidates to `read_only_recognition_outcomes` using the proposed schemas.
- **Negative Controls**:
  - Regular straight staff lines must not trigger wavy-line (vibrato) detection.
  - Vertical stems and horizontal barlines must not trigger diagonal-line (slide) detection.
- **Validation Command**:
  - `.venv/bin/python -m pytest tests/test_cr07_embellishment_attachments.py`
  - `.venv/bin/python scripts/agent_verify.py`

---

## 9. Stop Conditions

- **Stop Condition**: Publish updated product architecture on branch `agy/cr07-bounded-embellishment-attachments-architecture` in `tticom/score2gp` for independent Codex re-review. Stop without modifying product source code in `score2gp`.
