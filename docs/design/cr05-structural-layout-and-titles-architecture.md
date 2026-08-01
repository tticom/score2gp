# CR-05 Structural Layout and Titles Architecture

## 1. Executive Summary

This document establishes a generic, testable, and decoupled technical architecture for score2gp PDF conversion to independently classify:

1. **Ordinary, double, and final barlines**;
2. **System and page layout breaks**;
3. **Phrase or piece titles and their ownership by a system or measure**.

### Key Architectural Invariants
- A double or final barline must **never** imply a system break merely because of its barline type.
- A system break must **never** require a double or final barline.
- Title text above or near staves must be explicitly classified and bound to system or measure ownership rather than being treated as arbitrary or global text.
- Evidence structures for barlines, layout breaks, and titles are strictly separated.

- **Selected Outcome**: `CONTINUE` (evidence supports one bounded Developer implementation slice `CR-05A` on the PDF-tab seam).

---

## 2. Baseline Revisions & Maintainer Authorization

- **Governance Repository Baseline**: `5477038e44bd6ba8e362781eb22fdf6039802533` (`tticom/score2gp-agentops`)
- **Product Repository Baseline**: `f3cf042c96defdaf09c3353f16f9dbcb38e542d3` (`tticom/score2gp`, `origin/main`)
- **Reviewed PR Head**: `ba1944368f94c4d16bef5e647097c5db24b7b2a0` (PR #397)
- **Maintainer Authorization**: Present maintainer authorization explicitly accepts current product `origin/main`, including commit `f3cf042c96defdaf09c3353f16f9dbcb38e542d3`, as the baseline for CR-05 research without requiring historical reconstruction of earlier task records.

---

## 3. Verified Repository Facts & Corrected Seam Analysis

Source-code tracing across `src/score2gp/pdf.py`, `src/score2gp/pdf_staff_geometry.py`, `src/score2gp/report.py`, `src/score2gp/whole_note_recogniser.py`, `src/score2gp/cli.py`, and `src/score2gp/build_ir.py` establishes the following empirical facts:

### 3.1 PDF-Tab Barline Classification Seam
- **Exact File & Functions**: `src/score2gp/pdf.py:filter_tab_barline_candidates()` (lines 3730–3850) and `_detect_tab_systems()` (lines 3880–4112).
- **Producer / Consumer Path**:
  - `_detect_tab_systems()` extracts vertical `_LineSegment` candidates from page vector drawings.
  - `filter_tab_barline_candidates()` performs single-linkage clustering using `DOUBLE_BARLINE_CLUSTERING_TOLERANCE` (12.0 pt).
  - For a 2-stroke cluster, it picks a single representative x-coordinate for `valid_barlines` and marks secondary strokes as rejected under the code `pdf_barline_double_secondary`.
  - Details are stored in `barline_candidates_details` dicts attached to `_TabSystem` and reported in `report.py`.
- **Verified Defect & Seam Disconnect**:
  - `StructuralSkeletonBarlineCandidate` in `src/score2gp/pdf_staff_geometry.py` belongs *only* to `pdf_staff_notation_diagnostics.py` (standard notation path) and is **not** consumed or produced by the PDF-tab path (`filter_tab_barline_candidates()`).
  - To record barline style in the PDF-tab conversion path, typed fields (`barline_style: Literal["regular", "double", "ambiguous"]`) must be added to the tab-specific candidate details dictionary produced by `filter_tab_barline_candidates()` and carried on `_TabSystem.barline_candidates_details`.
- **Public Reproducer / Command**:
  - Command: `python -m pytest tests/test_pdf_only_tab.py`
  - Public Fixture: `fixtures/public/generated_paired_notation_tab_system_double_barline.json` (contains two vertical strokes at x=572.0 and x=575.0).

### 3.2 System and Page Layout Break Inference
- **Exact File & Functions**: `src/score2gp/pdf.py:_detect_tab_systems()` (lines 3880–4112).
- **Producer / Consumer Path**:
  - Systems are inferred by grouping 6 horizontal staff lines into `_TabSystem` instances per page.
  - Page breaks are implicitly defined by PyMuPDF page indices (`page_number`).
- **Verified Defect**: No explicit data structure represents system-break or page-break evidence independently from horizontal staff line bounding boxes.

### 3.3 Influence of Barline Type on Layout Breaks
- **Exact File & Functions**: `src/score2gp/pdf.py:_detect_tab_systems()` and `infer_edge_boundaries()`.
- **Producer / Consumer Path**:
  - Double barlines at system edges collapse into single float x-coordinates. Internal double barlines with >2 strokes trigger `pdf_barline_ambiguous`.
- **Verified Defect**: System boundary recovery falls back to `infer_edge_boundaries()` when barlines are rejected or missing, conflating barline stroke presence with system layout boundaries.

### 3.4 Text Extraction and Coarse Spatial Association (Corrected Fact)
- **Exact File & Functions**: `src/score2gp/pdf.py:_extract_pdf_text_candidates()` (lines 753–1700).
- **Producer / Consumer Path**:
  - PyMuPDF (`fitz`) extracts words (`page.get_text("words")`) and blocks.
  - Words are assigned a coarse system reference (`system = _nearest_system(systems, x, y)`) and bar index (`system.bar_for_x(cx)`).
  - Regex checks match tuning phrases (`standard tuning`, `drop d`), string pitch labels (`E`, `B`, `G`, `D`, `A`), and section keywords (`verse`, `intro`, `chorus`).
- **Verified Defect**:
  - While coarse spatial association exists for digits and tuning text, **durable title classification, title ranking, title exclusivity, and title-to-system/measure ownership contracts are absent**.
  - All non-tuning/non-digit text above or near staves falls through into `non_playable_words` and is emitted as unclassified `candidate-text`.

---

## 4. Hypotheses and Unknowns Ledger

| ID | Subject / Claim | Status | Controlling Facts & Seams | Unknown / Deferred Boundary |
|---|-----------------|--------|---------------------------|-----------------------------|
| **H-01** | Multi-stroke barline clusters (12pt) can be typed as `double` without discarding secondary strokes | Verified | `pdf.py:filter_tab_barline_candidates()` cluster logic | Final barline (thick-thin) cannot be distinguished without stroke-width evidence; `CR-05A` bounds typing to `regular` vs `double`. |
| **H-02** | System breaks can be represented independently of barline presence | Verified | `pdf.py:_detect_tab_systems()` staff line grouping | System break connectors (`bracket_curve`, `brace_curve`) in multi-staff scores require separate connector geometry checks. |
| **H-03** | Title text can be classified via font size ratio and relative page position | Verified | `pdf.py:page.get_text("words")` bbox + font metadata | Optimal font-size ratio threshold across diverse PDF publisher templates (A4 vs Letter vs custom booklet). |
| **H-04** | Title-to-system ownership can be made exclusive via minimum vertical distance ranking | Verified | Page-level text candidates vs system bounding box `y0` | Handling multi-line titles or title + subtitle blocks above System 1. |

---

## 5. Claim-by-Claim Evidence Ledger

| Claim ID | Claim Description | Repository Source / Evidence | Classification | Failure Mode Ruled Out |
|----------|-------------------|------------------------------|----------------|------------------------|
| **C-01** | PDF-tab barlines are flattened into `list[float]`, losing barline style | `pdf.py:filter_tab_barline_candidates()` (lines 3730-3850), `_TabSystem.barlines` | Verified Fact | Ruled out claim that barline style is preserved in IR. |
| **C-02** | `StructuralSkeletonBarlineCandidate` is not on the PDF-tab conversion path | `src/score2gp/pdf_staff_geometry.py` vs `pdf.py` search | Verified Fact | Ruled out editing `pdf_staff_geometry.py` alone as a valid fix for PDF-tab barlines. |
| **C-03** | Double barlines do not force system breaks in `_detect_tab_systems()` | `pdf.py:3880-4112` code inspection | Verified Fact | Ruled out existing code automatically splitting systems on double barlines. |
| **C-04** | Text candidates receive coarse `system_index` but lack title ownership contracts | `pdf.py:753-1700` (`_nearest_system` and `bar_for_x`) | Verified Fact | Ruled out claim of total text spatial decoupling; confirmed title ownership gap. |

---

## 6. Executable Classification Algorithms & Decision Rules

### 6.1 System and Page Layout Break Inference Algorithm

#### Inputs
- `staff_line_groups`: List of horizontal line groups extracted from vector drawings.
- `page_bounds`: Bounding box of PDF page `[0, 0, page_width, page_height]`.
- `vertical_connectors`: List of vertical stroke segments crossing multiple staves.

#### Deterministic Rules
1. **System Extraction**:
   - Group horizontal line segments into 6-line staff groups with equal vertical line spacing $S \in [5.5, 15.0]$ pt.
   - Calculate staff bounding box $B_k = [x_0^k, y_0^k, x_1^k, y_1^k]$ for staff group $k$.
   - A new **System Break** occurs at staff group $k$ if $k = 1$ (page top) or if $y_0^k - y_1^{k-1} > 2.0 \times S$ (vertical gap between staves).
2. **Page Break Extraction**:
   - A **Page Break** occurs at page index boundaries ($p_1 \to p_2$).
3. **Absence & Ambiguity Output**:
   - If two staff groups overlap vertically ($y_0^k < y_1^{k-1} - 4.0$), emit `pdf_multi_system_order_ambiguous` and fail closed (`status="ambiguous"`).

---

### 6.2 Barline Style Classification Algorithm (PDF-Tab Seam)

#### Inputs
- `system_candidates`: List of vertical line segments $s_i = (x_i, y_{min,i}, y_{max,i})$ crossing staff $k$.
- `y0, y1`: Top and bottom $y$-coordinates of staff $k$.
- `line_ys`: $y$-coordinates of the 6 staff lines.
- `DOUBLE_BARLINE_CLUSTERING_TOLERANCE`: 12.0 pt.

#### Deterministic Rules
1. **Single-Linkage Clustering**:
   - Filter candidates that cross at least 4 string gaps ($y_{min} \le y_0 + 3.0$ and $y_{max} \ge y_1 - 3.0$).
   - Cluster accepted candidates by horizontal distance: candidates $s_i, s_j$ belong to the same cluster if $|x_i - x_j| \le 12.0$ pt.
2. **Style Assignment & Oracle Boundary**:
   - **Cluster Size == 1**:
     - `barline_style = "regular"`.
     - `primary_x = round(s[0].x, 3)`.
     - Add to `valid_barlines`.
   - **Cluster Size == 2**:
     - Bound CR-05A to **`barline_style = "double"`** (thick-thin `final` barline classification requires stroke-width evidence; when stroke widths are equal or untyped, classify as `double`).
     - Representative `primary_x` = rightmost stroke if at right system edge ($x \ge x_1 - 10.0$), leftmost stroke if at left system edge ($x \le x_0 + 10.0$), or leftmost stroke if internal.
     - Primary candidate detail: `final_decision = "accepted"`, `barline_style = "double"`.
     - Secondary candidate detail: `final_decision = "rejected"`, `rejection_reason = "pdf_barline_double_secondary"`, `barline_style = "double"`.
     - Add `primary_x` to `valid_barlines`.
   - **Cluster Size > 2**:
     - All candidates in cluster: `final_decision = "rejected"`, `rejection_reason = "pdf_barline_ambiguous"`, `barline_style = "ambiguous"`.
3. **Exact Producer/Consumer Data Seam**:
   - Producer: `pdf.py:filter_tab_barline_candidates()`.
   - Output Dictionary inside `barline_candidates_details`:
     ```python
     {
         "x": float,
         "height": float,
         "final_decision": "accepted" | "rejected",
         "rejection_reason": str | None,
         "barline_style": "regular" | "double" | "ambiguous",
         "cluster_size": int
     }
     ```
   - Diagnostic Consumer: `_TabSystem.barline_candidates_details` -> `report.py` HTML report.

---

### 6.3 Text Classification & Title Ownership Ranking Algorithm

#### Inputs
- `text_words`: List of text words extracted from page `p` with bounding box `[x0, y0, x1, y1]`, font name, font size `f_size`.
- `systems`: List of `_TabSystem` instances on page `p`.
- `median_font_size`: Median font size across all text on page `p`.

#### Deterministic Classification Rules
1. **Piece Title Candidate**:
   - Condition: Page $p = 1$, $y_{center} < \text{system}_1.y_0 - 15.0$ pt, $f_{size} \ge 1.25 \times \text{median\_font\_size}$.
   - Classify as `category = "piece_title"`.
2. **Phrase Title / Section Header Candidate**:
   - Condition: Text matches section keywords (`Intro`, `Verse`, `Chorus`, `Bridge`, `Outro`, `Solo`) or text string above system $k$ ($y_{center} < \text{system}_k.y_0$).
   - Classify as `category = "section_header"` or `"phrase_title"`.
3. **Tempo Instruction Candidate**:
   - Condition: Regex match `r"(\b[qQ]\s*=\s*\d+\b|\b\d+\s*bpm\b|\bAllegro\b|\bAndante\b|\bModerato\b)"`.
   - Classify as `category = "tempo_instruction"`.
4. **Chord Symbol Candidate**:
   - Condition: Text above staff matching chord regex `r"^[A-G][#b]?(m|maj|min|dim|aug|7|9|11|13|add\d+)?(\/[A-G][#b]?)?$"`.
   - Classify as `category = "chord_symbol"`.

#### Ownership & Exclusivity Ranking Rules
1. **Document-Level Ownership (`TitleDocumentOwnership`)**:
   - Candidate text with `category = "piece_title"` on Page 1 is ranked by font size $f_{size}$ then vertical position $y_0$.
   - The highest-ranked candidate is assigned as the exclusive `piece_title` for the document.
2. **System-Level Ownership (`TitleSystemOwnership`)**:
   - Candidate text with `category = "phrase_title"` or `"section_header"` above System $k$ is evaluated against all systems on page $p$.
   - **Exclusivity Constraint**: Calculate vertical distance $d_k = \text{system}_k.y_0 - y_{center}$. Assign exclusively to System $k$ where $d_k > 0$ is minimized.
   - Must **not** be assigned to System $k+1$ or any non-adjacent system.
3. **Measure-Level Ownership (`TitleMeasureOwnership`)**:
   - Map text candidate horizontal midpoint $x_{center} = (x_0 + x_1) / 2$ to Measure Region $m$ of System $k$ via `system.bar_for_x(x_center)`.
4. **Ambiguity / Absence Resolution**:
   - If a phrase title candidate lies equidistant between System $k$ and System $k+1$ ($|d_k - d_{k+1}| < 5.0$ pt), assign `ownership_status = "ambiguous_ownership"` and fail closed.

---

## 7. Required State Separation Data Models

```python
from typing import Literal
from pydantic import BaseModel, Field

class PdfTabBarlineCandidateDetail(BaseModel):
    """Typed candidate detail item produced by filter_tab_barline_candidates on the PDF-tab seam."""
    idx: int
    x: float
    y0: float
    y1: float
    height: float
    final_decision: Literal["accepted", "rejected"]
    rejection_reason: str | None = None
    barline_style: Literal["regular", "double", "ambiguous"]
    cluster_size: int = Field(ge=1)

class SystemLayoutBreakEvidence(BaseModel):
    """Decoupled system break evidence structure."""
    system_index: int = Field(ge=1)
    page_index: int = Field(ge=1)
    x0: float
    x1: float
    y0: float
    y1: float
    is_system_start: bool
    is_system_end: bool
    leading_connector_kind: Literal["leading_barline", "bracket_curve", "brace_curve", "none"] = "none"

class PageLayoutBreakEvidence(BaseModel):
    """Decoupled page break evidence structure."""
    page_index: int = Field(ge=1)
    is_page_start: bool
    is_page_end: bool

class TextClassificationEvidence(BaseModel):
    """Classification of extracted PDF text spans."""
    text_id: str
    raw_text: str
    bbox: list[float]  # [x0, y0, x1, y1]
    font_name: str | None = None
    font_size: float | None = None
    category: Literal[
        "piece_title",
        "phrase_title",
        "section_header",
        "tempo_instruction",
        "chord_symbol",
        "technique_text",
        "tuning_text",
        "unclassified"
    ]
    confidence: float = Field(ge=0.0, le=1.0)

class TitleSystemOwnership(BaseModel):
    """Spatial and structural ownership linking a title to a system."""
    title_text_id: str
    system_index: int = Field(ge=1)
    page_index: int = Field(ge=1)
    spatial_relation: Literal["above_system", "within_system_margin", "page_header"]
    vertical_distance_pt: float
    exclusivity_status: Literal["assigned_exclusive", "ambiguous_ownership"]

class TitleMeasureOwnership(BaseModel):
    """Spatial and structural ownership linking a title or phrase mark to a measure."""
    title_text_id: str
    system_index: int = Field(ge=1)
    measure_region_index: int = Field(ge=1)
    start_x: float
    end_x: float
    overlap_ratio: float = Field(ge=0.0, le=1.0)

class StructuralAbsenceOfEvidence(BaseModel):
    """Explicit model for absence of evidence vs detection failure."""
    target_feature: Literal["barline", "system_break", "page_break", "title"]
    location_scope: str
    reason: Literal["no_vector_primitives", "below_detection_threshold", "suppressed_by_rule"]

class StructuralAmbiguousEvidence(BaseModel):
    """Explicit model for unresolved structural evidence."""
    feature_kind: Literal["barline_cluster", "overlapping_systems", "conflicting_titles"]
    competing_candidates: list[str]
    resolution_status: Literal["unresolved_refusal", "deferred_to_user"]
```

---

## 8. Required Falsification & Negative Controls

| # | Rule / Claim | Positive Example | Negative Control | Ambiguity / Conflict Case | Smallest Broken Implementation | Observable Output Failure | Stop / Pivot Criteria |
|---|--------------|------------------|------------------|---------------------------|--------------------------------|---------------------------|-----------------------|
| **1** | Double barline must not force a system break | Mid-system double barline between m2 & m3 | Regular single barline at m2 | Double barline within 15pt of system edge | Splitting `_TabSystem` whenever `cluster_size == 2` | Erroneous system break creating two 2-measure systems in output | If double barline splits system: **STOP & PIVOT** |
| **2** | System break must not require a double barline | System 1 ending with regular single barline | System ending with open staff (no final barline) | System ending near right margin with missing line | Refusing system break unless rightmost barline has `cluster_size >= 2` | `pdf_barlines_not_detected_in_system` refusal on valid single-barline systems | If single-barline system refused: **STOP & PIVOT** |
| **3** | Page-edge proximity alone must not cause false break | Staff line extending within 10pt of right page edge | Short staff ending 100pt from edge | Fragmented vector stroke near right margin | Triggering layout break if `x1 > page_width - margin` | Truncated measure regions near page margins | If margin causes false break: **STOP & PIVOT** |
| **4** | Arbitrary text above staff must not become phrase title | Large bold centered text `"Intro"` above measure 1 | Tempo text `"Allegro q=120"` or chord `"Am"` above staff | Mixed text `"Section A - Am"` | Assigning `category="piece_title"` to any text where `y < min_staff_y` | Corrupted track title metadata and invalid chord symbol warnings | If tempo/chord misclassified as title: **STOP & PIVOT** |
| **5** | One title must not be assigned to multiple systems | Title `"Minuet in G"` assigned exclusively to System 1 | System 2 inheriting top page title | Title vertically equidistant between System 1 and System 2 | Broad y-distance threshold matching all staves on page | Duplicate title annotations emitted on every system in ScoreIR | If title assigned to >1 system: **STOP & PIVOT** |
| **6** | Generic geometry must not use hardcoded page coordinates | Title classification via font-size ratio `(f_size / median) > 1.25` | Hardcoded threshold `y < 100.0` pt | Small PDF page size (A5 vs A4 vs Letter) | Classifying title using fixed absolute Y coordinate `y < 80.0` | Title misclassified on custom/large page sizes | If absolute Y fails on A5/Letter: **STOP & PIVOT** |

---

## 9. Outcome & Recommended Developer Implementation Slice

- **Selected Outcome**: `CONTINUE`

### 9.1 Bounded Developer Implementation Slice: `CR-05A`
- **Slice Name**: `CR-05A: PDF-Tab Barline Style Classification Seam`
- **Authorized Product Files**:
  - `docs/design/cr05-structural-layout-and-titles-architecture.md` (this report)
  - `src/score2gp/pdf.py` (update `filter_tab_barline_candidates()` to populate `barline_style` in candidate details)
  - `src/score2gp/report.py` (propagate `barline_style` in HTML candidate details rendering)
  - `tests/test_cr05_barline_style_classification.py` (new public test file)
- **Public / Synthetic Fixtures**:
  - `fixtures/public/generated_paired_notation_tab_system_double_barline.json`
  - Synthetic 2-barline double-stroke test fixture in `tests/test_cr05_barline_style_classification.py`
- **Production Seam**:
  - Producer: `src/score2gp/pdf.py:filter_tab_barline_candidates()`
  - Update candidate details dictionaries to include `barline_style: Literal["regular", "double", "ambiguous"]`.
  - For a 2-stroke cluster within `DOUBLE_BARLINE_CLUSTERING_TOLERANCE` (12.0 pt), mark `barline_style = "double"` on both primary (accepted) and secondary (rejected) candidate dictionaries.
  - For 1-stroke candidates, mark `barline_style = "regular"`.
  - Pass `barline_candidates_details` through `_TabSystem` to `report.py` diagnostics.
- **Acceptance Assertions**:
  1. 2-stroke clusters in `filter_tab_barline_candidates()` produce `barline_style = "double"` in `barline_candidates_details`.
  2. Single vertical strokes produce `barline_style = "regular"`.
  3. `valid_barlines` float array and system bounds remain 100% backward-compatible.
- **Negative Controls**:
  1. Single vertical line produces `barline_style = "regular"`.
  2. No system breaks are added or removed when converting double barline scores.
- **Compatibility Requirements**:
  1. `_TabSystem.barlines` remains a `list[float]` for backward compatibility with `build_ir.py`.
  2. Diagnostic JSON outputs remain schema-compliant with `pdf_staff_geometry_diagnostics_schema.json`.
- **Validation Commands**:
  - `/home/tticom-automation/work/score2gp-workspace/score2gp/.venv/bin/python -m pytest tests/test_cr05_barline_style_classification.py`
  - `/home/tticom-automation/work/score2gp-workspace/score2gp/.venv/bin/python scripts/agent_verify.py`
- **Explicit Non-goals**:
  - No title classification or title ownership code changes in `CR-05A`.
  - No system layout break refactoring in `CR-05A`.
  - No changes to product `build_ir.py` conversion logic in `CR-05A`.
  - Final-barline (thick-thin) classification is deferred until vector stroke-width / drawing-type oracle evidence is added.

---

## 10. Durable Deliverables & Stop Conditions

- **Product Architecture Document**: `docs/design/cr05-structural-layout-and-titles-architecture.md`
- **What Was Not Verified**: Scanned raster-only PDFs without vector line drawings (which require optical music recognition outside current deterministic PDF parsing).
- **Stop Condition**: Publish updated product architecture on branch `agy/cr05-structural-layout-and-titles-architecture` in `tticom/score2gp` for independent Codex re-review. Stop without modifying product source code in `score2gp` or creating governance run records in `score2gp-agentops`.
