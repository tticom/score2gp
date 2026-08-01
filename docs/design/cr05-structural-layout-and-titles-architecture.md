# CR-05 Structural Layout and Titles Architecture

## 1. Executive Summary

This document establishes a generic, testable, and decoupled technical architecture for score2gp PDF conversion to independently classify:

1. **Ordinary and double barlines** (with explicit vector stroke-width contracts for future final-barline classification);
2. **System and page layout breaks** (separating single-staff tab systems and multi-staff connected systems);
3. **Phrase or piece titles and their ownership by a system or measure**.

### Key Architectural Invariants
- A double or final barline must **never** imply a system break merely because of its barline type.
- A system break must **never** require a double or final barline.
- Title text above or near staves must be explicitly classified using an ordered, mutually exclusive hierarchy, and bound to system or measure ownership rather than being treated as arbitrary or global text.
- Evidence structures for barlines, layout breaks, and titles are strictly separated.

- **Selected Outcome**: **`CONTINUE`** (evidence supports one bounded Developer implementation slice `CR-05A` on the PDF-tab seam; multi-staff connector grouping, font-ratio thresholds, and final-barline stroke width are explicitly recorded as deferred non-goals for future tasks).

---

## 2. Baseline Revisions & Maintainer Authorization

- **Governance Repository Baseline**: `5477038e44bd6ba8e362781eb22fdf6039802533` (`tticom/score2gp-agentops`)
- **Product Repository Baseline**: `f3cf042c96defdaf09c3353f16f9dbcb38e542d3` (`tticom/score2gp`, `origin/main`)
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
  - To record barline style in the PDF-tab conversion path, typed fields (`barline_style: Literal["regular", "double", "ambiguous"]`) must be added directly to the tab-specific candidate details dictionary produced by `filter_tab_barline_candidates()` and carried on `_TabSystem.barline_candidates_details`.
- **Public Reproducer / Verification Command & Observations**:
  - Command: `python -m pytest tests/test_pdf.py::test_double_barline_ambiguity_resolution`
  - Public Fixture: `tests/fixtures/pdf/generated_paired_notation_tab_system_double_barline.pdf` (generated from `fixtures/public/generated_paired_notation_tab_system_double_barline.json`, containing two vertical strokes at x=572.0 and x=575.0).
  - Literal Assertions: `test_double_barline_ambiguity_resolution` verifies `extract_tab()` yields 1 TAB system with 2 playable candidates across 2 bars. In `filter_tab_barline_candidates()`, `valid_barlines` contains `[36.0, 300.0, 575.0]` (x=572.0 rejected with `pdf_barline_double_secondary`), but candidate details carry no `barline_style` metadata.

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

### 3.4 Text Extraction Seam & Coarse Spatial Association
- **Exact File & Functions**: `src/score2gp/pdf.py:_extract_pdf_text_candidates()` (lines 753–1700).
- **Producer / Consumer Path**:
  - PyMuPDF `page.get_text("words")` extracts 8-tuples `(x0, y0, x1, y1, word, block_no, line_no, word_no)`. Note: `get_text("words")` does **not** contain font name or font size metadata.
  - Span-level font metadata (`font`, `size`, `flags`) requires PyMuPDF `page.get_text("dict")` structured blocks (`page.get_text("dict")["blocks"] -> lines -> spans`).
  - Words are assigned a coarse system reference (`system = _nearest_system(systems, x, y)`) and bar index (`system.bar_for_x(cx)`).
  - Regex checks match tuning phrases (`standard tuning`, `drop d`), string pitch labels (`E`, `B`, `G`, `D`, `A`), and section keywords (`verse`, `intro`, `chorus`).
- **Verified Defect**:
  - While coarse spatial association exists for digits and tuning text, **durable title classification, ordered font-ratio ranking, exclusivity rules, and title-to-system/measure ownership contracts are absent**.
  - All non-tuning/non-digit text above or near staves falls through into `non_playable_words` and is emitted as unclassified `candidate-text`.

---

## 4. Hypotheses and Unknowns Ledger

| ID | Subject / Claim | Status | Controlling Facts & Seams | Unknown / Deferred Boundary |
|---|-----------------|--------|---------------------------|-----------------------------|
| **H-01** | Multi-stroke barline clusters (12pt) can be typed as `double` on the PDF-tab seam | Verified Fact | `pdf.py:filter_tab_barline_candidates()` cluster logic | Verified for 2-stroke clusters. Final barline requires vector stroke-width acquisition. |
| **H-02** | System breaks can be represented independently of barline presence | Provisional / Unverified | `pdf.py:_detect_tab_systems()` staff line grouping | Multi-staff connector grouping (`bracket_curve`, `brace_curve`, `leading_barline`) requires explicit connector alignment research. |
| **H-03** | Title text can be classified via font-size ratio from `page.get_text("dict")` | Provisional / Unverified | `page.get_text("dict")` span metadata | Empirical font-size ratio threshold across diverse PDF publisher templates (A4 vs Letter vs custom booklet) requires dynamic fixture probing. |
| **H-04** | Title-to-system ownership can be made exclusive via absolute boundary distance ranking | Provisional / Unverified | Page-level text candidates vs system bounding boxes | Multi-line title blocks and subtitle handling require multi-span bounding box merging. |

---

## 5. Claim-by-Claim Evidence Ledger

| Claim ID | Claim Description | Repository Source / Evidence | Classification | Failure Mode Ruled Out |
|----------|-------------------|------------------------------|----------------|------------------------|
| **C-01** | PDF-tab barlines are flattened into `list[float]`, losing barline style | `pdf.py:filter_tab_barline_candidates()` (lines 3730-3850), `_TabSystem.barlines` | Verified Fact | Ruled out claim that barline style is preserved in IR. |
| **C-02** | `StructuralSkeletonBarlineCandidate` is not on the PDF-tab conversion path | `src/score2gp/pdf_staff_geometry.py` vs `pdf.py` search | Verified Fact | Ruled out editing `pdf_staff_geometry.py` alone as a valid fix for PDF-tab barlines. |
| **C-03** | Double barlines do not force system breaks in `_detect_tab_systems()` | `pdf.py:3880-4112` code inspection | Verified Fact | Ruled out existing code automatically splitting systems on double barlines. |
| **C-04** | `page.get_text("words")` lacks font size; `page.get_text("dict")` is required | `fitz` API signature & `pdf.py:764` inspection | Verified Fact | Ruled out using `words` tuples for font-size-based title classification. |
| **C-05** | Text candidates receive coarse `system_index` but lack title ownership contracts | `pdf.py:753-1700` (`_nearest_system` and `bar_for_x`) | Verified Fact | Ruled out claim of total text spatial decoupling; confirmed title ownership gap. |

---

## 6. Executable Classification Algorithms & Decision Rules

### 6.1 System and Page Layout Break Inference Algorithm

#### Inputs
- `staff_line_groups`: List of horizontal line groups extracted from vector drawings.
- `page_bounds`: Bounding box of PDF page `[0, 0, page_width, page_height]`.
- `vertical_connectors`: List of vertical stroke / curve segments crossing staves.

#### Deterministic Decision Rules
1. **Single-Staff Tab System Extraction**:
   - Group horizontal line segments into 6-line staff groups with equal vertical line spacing $S \in [5.5, 15.0]$ pt.
   - Calculate staff bounding box $B_k = [x_0^k, y_0^k, x_1^k, y_1^k]$ for staff group $k$.
   - A new **System Break** occurs at staff group $k$ if $k = 1$ (page top) or if $y_0^k - y_1^{k-1} > 2.0 \times S$ (vertical gap between staves).
2. **Multi-Staff Connected System Contract (Deferred Non-Goal)**:
   - Filter `vertical_connectors` to leading-edge connectors ($x \le x_0 + 15.0$ pt) spanning from the top line of staff $k-1$ to the bottom line of staff $k$ with horizontal overlap $\frac{\text{overlap}(x^{k-1}, x^k)}{\min(w^{k-1}, w^k)} \ge 0.70$.
   - If a leading-edge connector is present, group staff $k-1$ and staff $k$ into a single multi-staff **System** $m$.
   - Note: Multi-staff connectors are recorded as a deferred non-goal for future research. Single-staff tab system grouping ($y_0^k - y_1^{k-1} > 2.0 \times S$) is the sole rule for `CR-05A`.
3. **Page Break Extraction**:
   - A **Page Break** occurs at page index boundaries ($p_1 \to p_2$).
4. **Absence & Ambiguity Output**:
   - If two staff groups overlap vertically ($y_0^k < y_1^{k-1} - 4.0$) without a connector, emit `pdf_multi_system_order_ambiguous` and fail closed (`status="ambiguous"`).

---

### 6.2 Barline Style Classification Algorithm (PDF-Tab Seam & Vector Stroke-Width Contract)

#### Inputs
- `system_candidates`: List of vertical line segments $s_i = (x_i, y_{min,i}, y_{max,i})$ crossing staff $k$.
- `y0, y1`: Top and bottom $y$-coordinates of staff $k$.
- `line_ys`: $y$-coordinates of the 6 staff lines.
- `DOUBLE_BARLINE_CLUSTERING_TOLERANCE`: 12.0 pt.

#### Deterministic Rules (Bounded for CR-05A)
1. **Single-Linkage Clustering**:
   - Filter candidates that cross at least 4 string gaps ($y_{min} \le y_0 + 3.0$ and $y_{max} \ge y_1 - 3.0$).
   - Cluster accepted candidates by horizontal distance: candidates $s_i, s_j$ belong to the same cluster if $|x_i - x_j| \le 12.0$ pt.
2. **Style Assignment & Vector Stroke-Width Seam**:
   - **Cluster Size == 1**:
     - `barline_style = "regular"`.
     - `primary_x = round(s[0].x, 3)`.
     - Add `primary_x` to `valid_barlines`.
   - **Cluster Size == 2**:
     - **CR-05A Bounded Rule**: Classify as **`barline_style = "double"`** when stroke widths are equal or untyped ($W_1 \approx W_2$).
     - **Future Final Barline Vector Seam Contract (Deferred Non-Goal)**: Vector stroke width is extracted from PyMuPDF `page.get_drawings()` vector drawing dictionaries (`drawing["width"]` / line items `("l", p0, p1)`). A 2-stroke cluster is classified as `final` **only if** rightmost stroke width $W_{right} \ge 2.5 \times W_{left}$ (thin-thick final barline morphology). When $W_{right} \approx W_{left}$, classify as `double`.
     - Representative `primary_x` = rightmost stroke if at right system edge ($x \ge x_1 - 10.0$), leftmost stroke if at left system edge ($x \le x_0 + 10.0$), or leftmost stroke if internal.
     - Primary candidate detail: `final_decision = "accepted"`, `barline_style = "double"`.
     - Secondary candidate detail: `final_decision = "rejected"`, `rejection_reason = "pdf_barline_double_secondary"`, `barline_style = "double"`.
     - Add `primary_x` to `valid_barlines`.
   - **Cluster Size > 2**:
     - All candidates in cluster: `final_decision = "rejected"`, `rejection_reason = "pdf_barline_ambiguous"`, `barline_style = "ambiguous"`.
3. **Exact Additive Producer/Consumer Data Seam**:
   - Producer: `pdf.py:filter_tab_barline_candidates()`.
   - Output Dictionary inside `barline_candidates_details` (preserving all live keys while adding `barline_style` and `cluster_size`):
     ```python
     {
         "idx": int,
         "x": float,
         "y_min": float,
         "y_max": float,
         "height": float,
         "relative_height_ok": bool,
         "absolute_height_ok": bool,
         "gaps_crossed": int,
         "intersects": bool,
         "in_bounds": bool,
         "initially_accepted": bool,
         "final_decision": "accepted" | "rejected",
         "rejection_reason": str | None,
         "barline_style": "regular" | "double" | "ambiguous",
         "cluster_size": int
     }
     ```
   - Diagnostic Consumer: `_TabSystem.barline_candidates_details` -> `report.py` HTML report & JSON payload.

---

### 6.3 Ordered Text Classification & Absolute Ownership Algorithm

#### Span Metadata Source
- Span metadata is extracted from PyMuPDF `page.get_text("dict")` structured blocks: `span["text"]`, `span["bbox"]`, `span["size"]`, `span["flags"]`.
- `median_font_size`: Median font size across all text spans on page $p$.

#### Mutually Exclusive Priority Hierarchy
To eliminate non-deterministic classification (e.g. preventing a large `Allegro` or `Am` from being misclassified as a title), text spans are evaluated in strict priority order:

1. **Priority 1 — Tempo Instruction**:
   - Condition: Span text matches tempo regex `r"(\b[qQ]\s*=\s*\d+\b|\b\d+\s*bpm\b|\bAllegro\b|\bAndante\b|\bModerato\b|\bPresto\b)"`.
   - Classification: `category = "tempo_instruction"`.
2. **Priority 2 — Chord Symbol**:
   - Condition: Span text above staff matching chord regex `r"^[A-G][#b]?(m|maj|min|dim|aug|7|9|11|13|add\d+)?(\/[A-G][#b]?)?$"`.
   - Classification: `category = "chord_symbol"`.
3. **Priority 3 — Tuning Text**:
   - Condition: Span text matches tuning regex or string pitch labels (`Standard Tuning`, `Drop D`, `E A D G B E`).
   - Classification: `category = "tuning_text"`.
4. **Priority 4 — Piece Title Candidate**:
   - Condition: Page $p = 1$, span $y_{center} < \text{system}_1.y_0 - 15.0$ pt, font size $f_{size} \ge 1.25 \times \text{median\_font\_size}$, NOT classified under Priorities 1–3.
   - Classification: `category = "piece_title"`.
5. **Priority 5A — Section Header Candidate**:
   - Condition: Span text above system $k$ ($y_{center} < \text{system}_k.y_0$), matching section keywords (`Intro`, `Verse`, `Chorus`, `Bridge`, `Outro`, `Solo`, `Section`), NOT classified under Priorities 1–4.
   - Classification: `category = "section_header"`.
6. **Priority 5B — Phrase Title Candidate**:
   - Condition: Span text above system $k$ ($y_{center} < \text{system}_k.y_0$), font size $f_{size} \ge \text{median\_font\_size}$, NOT matching section keywords, NOT classified under Priorities 1–5A.
   - Classification: `category = "phrase_title"`.
7. **Priority 6 — Unclassified Fallback**:
   - All other text spans: `category = "unclassified"`.

#### Absolute Ownership Geometry & Ambiguity Controls

```
                        Page Header / Title Zone
    -----------------------------------------------------------------
    Title Span: "Piece Title" (y_center)
    -----------------------------------------------------------------
                           | D_top = |y_center - System_1.y0|
                           v
    +---------------------------------------------------------------+
    | SYSTEM 1  (y0_1, y1_1)                                        |
    +---------------------------------------------------------------+
                           ^
                           | D_upper = |y_center - System_1.y1|
    -----------------------+-----------------------------------------
    Inter-System Gap       | Midpoint y_mid = (y1_1 + y0_2) / 2
                           | [Ambiguity Band: y_mid ± 5.0 pt]
    -----------------------+-----------------------------------------
                           | D_lower = |y_center - System_2.y0|
                           v
    +---------------------------------------------------------------+
    | SYSTEM 2  (y0_2, y1_2)                                        |
    +---------------------------------------------------------------+
```

1. **Document-Level Ownership (`TitleDocumentOwnership`)**:
   - Candidate spans with `category = "piece_title"` on Page 1 are sorted by font size $f_{size}$ (descending) then $y_0$ (ascending).
   - The top candidate is assigned to `TitleDocumentOwnership(title_text_id=..., title_text=...)`.
2. **Absolute System Ownership Geometry (`TitleSystemOwnership`)**:
   - For a phrase title candidate positioned between System $k$ and System $k+1$ ($\text{system}_k.y_1 < y_{center} < \text{system}_{k+1}.y_0$):
     - Distance to upper system bottom: $D_{upper} = |y_{center} - \text{system}_k.y_1|$.
     - Distance to lower system top: $D_{lower} = |y_{center} - \text{system}_{k+1}.y_0|$.
     - Midpoint $y_{mid} = (\text{system}_k.y_1 + \text{system}_{k+1}.y_0) / 2$.
   - **Exclusivity & Ambiguity Rules**:
     - If $y_{center} \in [y_{mid} - 5.0, y_{mid} + 5.0]$ (midpoint ambiguity band), mark `exclusivity_status = "ambiguous_ownership"` and fail closed.
     - If $D_{upper} < D_{lower} - 5.0$ pt, assign exclusively to System $k$ (`spatial_relation = "below_system"`).
     - If $D_{lower} < D_{upper} - 5.0$ pt, assign exclusively to System $k+1$ (`spatial_relation = "above_system"`).
3. **Measure-Level Ownership (`TitleMeasureOwnership`)**:
   - Map text candidate horizontal midpoint $x_{center} = (x_0 + x_1) / 2$ to Measure Region $m$ of System $k$ via `system.bar_for_x(x_center)`.

---

## 7. Required State Separation Data Models

```python
from typing import Literal
from pydantic import BaseModel, Field

class PdfTabBarlineCandidateDetail(BaseModel):
    """
    Typed candidate detail item produced by filter_tab_barline_candidates on the PDF-tab seam.
    Fully additive with existing live pdf.py candidate detail dictionary keys.
    """
    idx: int
    x: float
    y_min: float
    y_max: float
    height: float
    relative_height_ok: bool
    absolute_height_ok: bool
    gaps_crossed: int
    intersects: bool
    in_bounds: bool
    initially_accepted: bool
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
    """Classification of extracted PDF text spans from page.get_text('dict')."""
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

class TitleDocumentOwnership(BaseModel):
    """Document-level piece title ownership."""
    title_text_id: str
    piece_title: str
    page_index: int = Field(default=1, ge=1)
    font_size: float
    confidence: float = Field(ge=0.0, le=1.0)

class TitleSystemOwnership(BaseModel):
    """Spatial and structural ownership linking a title to a system."""
    title_text_id: str
    system_index: int = Field(ge=1)
    page_index: int = Field(ge=1)
    spatial_relation: Literal["above_system", "below_system", "page_header"]
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

## 8. Disconfirmation Record & Falsification Evidence

| # | Rule / Claim | Positive Control / Example | Negative Control | Ambiguity / Conflict Case | Smallest Broken Implementation | Observable Output Failure | Stop / Pivot Criteria | Verification Status & Run Receipt |
|---|--------------|----------------------------|------------------|---------------------------|--------------------------------|---------------------------|-----------------------|----------------------------------|
| **1** | Double barline must not force system break | Mid-system double barline between m2 & m3 | Regular single barline at m2 | Double barline within 15pt of system edge | Splitting `_TabSystem` whenever `cluster_size == 2` | Erroneous system break creating two 2-measure systems in output | If double barline splits system: **STOP & PIVOT** | **Verified Rule**: `pytest tests/test_pdf.py::test_double_barline_ambiguity_resolution` verifies `generated_paired_notation_tab_system_double_barline.pdf` yields 1 system across 2 bars with x=572.0 rejected under `pdf_barline_double_secondary`. |
| **2** | System break must not require double barline | System 1 ending with regular single barline | System ending with open staff (no final barline) | System ending near right margin with missing line | Refusing system break unless rightmost barline has `cluster_size >= 2` | `pdf_barlines_not_detected_in_system` refusal on valid single-barline systems | If single-barline system refused: **STOP & PIVOT** | **Verified Rule**: Standard single-barline PDFs yield valid 1-barline systems without refusal. |
| **3** | Page-edge proximity alone must not cause false break | Staff line extending within 10pt of right page edge | Short staff ending 100pt from edge | Fragmented vector stroke near right margin | Triggering layout break if `x1 > page_width - margin` | Truncated measure regions near page margins | If margin causes false break: **STOP & PIVOT** | **Verified Rule**: Edge boundary fallback (`infer_edge_boundaries`) requires candidate alignment. |
| **4** | Priority hierarchy prevents misclassifying tempo/chords as titles | Large bold text `"Intro"` above m1 classified as `section_header` (Priority 5A) | Tempo `"Allegro q=120"` above m1 classified as `tempo_instruction` (Priority 1) | Mixed text `"Section A - Am"` above staff | Unordered rule classifying any text with `f_size > 12` as `piece_title` | Tempo `"Allegro"` misclassified as piece title in output IR | If tempo/chord misclassified as title: **STOP & PIVOT** | **Provisional / Unexecuted Test Plan**: Text priority hierarchy defined; awaiting span-metadata implementation. |
| **5** | Title ownership uses absolute distance & midpoint ambiguity band | Text at $y=120$ between Sys 1 ($y_1=100$) & Sys 2 ($y_0=200$) assigned to Sys 1 | Text at $y=180$ assigned to Sys 2 | Text at $y=150$ ($y_{mid} \pm 5$pt) marked `ambiguous_ownership` | Using signed distance $d_k > 0$ which makes Sys 1 distance negative & unselectable | Title assigned to Sys 2 even when 5pt below Sys 1 | If midpoint title assigned to single system: **STOP & PIVOT** | **Provisional / Unexecuted Test Plan**: Absolute distance geometry defined; awaiting title ownership implementation. |
| **6** | Generic geometry uses font-size ratio, not hardcoded Y coordinates | Title classified via $(f_{size} / \text{median}) \ge 1.25$ on Page 1 | Normal body text $(f_{size} / \text{median}) \approx 1.0$ | Small page size (A5 / booklet layout) | Hardcoded coordinate check `y < 100.0` pt | Title misclassified as body text on non-standard page sizes | If fixed Y fails on A5/Letter: **STOP & PIVOT** | **Provisional / Unexecuted Test Plan**: Font ratio check defined; awaiting `page.get_text("dict")` implementation. |

---

## 9. Outcome & Recommended Developer Implementation Slice

- **Selected Outcome**: **`CONTINUE`** (Exactly one outcome selected; evidence supports one bounded Developer implementation slice `CR-05A` on the PDF-tab seam).

### 9.1 Bounded Developer Implementation Slice: `CR-05A`
- **Slice Name**: `CR-05A: PDF-Tab Barline Style Classification Seam`
- **Authorized Product Files**:
  - `docs/design/cr05-structural-layout-and-titles-architecture.md` (this report)
  - `src/score2gp/pdf.py` (update `filter_tab_barline_candidates()` to populate `barline_style` in candidate details)
  - `src/score2gp/report.py` (propagate `barline_style` in HTML candidate details rendering)
  - `tests/test_cr05_barline_style_classification.py` (new public test file)
- **Public / Synthetic Fixtures**:
  - `tests/fixtures/pdf/generated_paired_notation_tab_system_double_barline.pdf` (from `fixtures/public/generated_paired_notation_tab_system_double_barline.json`)
  - Synthetic 2-barline double-stroke test fixture in `tests/test_cr05_barline_style_classification.py`
- **Production Seam**:
  - Producer: `src/score2gp/pdf.py:filter_tab_barline_candidates()`
  - Update candidate details dictionaries to include `barline_style: Literal["regular", "double", "ambiguous"]` and `cluster_size: int`.
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
  2. `report.py` HTML and JSON summaries cleanly reflect `barline_style`.
- **Validation Commands**:
  - `/home/tticom-automation/work/score2gp-workspace/score2gp/.venv/bin/python -m pytest tests/test_pdf.py::test_double_barline_ambiguity_resolution`
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
