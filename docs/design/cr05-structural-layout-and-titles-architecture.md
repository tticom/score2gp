# CR-05 Structural Layout and Titles Architecture

## 1. Executive Summary

This architecture document establishes a generic, testable, and decoupled framework for score2gp PDF conversion to independently classify:

1. Ordinary, double, and final barlines;
2. System and page layout breaks;
3. Phrase or piece titles and their spatial ownership by a system or measure.

Under this architecture, a double or final barline must **never** imply a system break merely because of its barline type, and a system break must **never** require a double or final barline. Title text above or near staves must be explicitly classified and bound to system or measure ownership rather than being treated as arbitrary or global text.

- **Selected Outcome**: `CONTINUE` (evidence supports one bounded Developer implementation slice).

---

## 2. Accepted Baseline Revisions & Maintainer Authorization

- **Governance Repository Revision**: `5477038e44bd6ba8e362781eb22fdf6039802533` (`tticom/score2gp-agentops`)
- **Product Repository Revision**: `f3cf042c96defdaf09c3353f16f9dbcb38e542d3` (`tticom/score2gp`, `origin/main`)
- **Maintainer Authorization**: Present maintainer authorization explicitly accepts current product `origin/main`, including commit `f3cf042c96defdaf09c3353f16f9dbcb38e542d3`, as the baseline for CR-05 research without requiring historical reconstruction of earlier task records.

---

## 3. Verified Repository Facts

Tracing the current production pipeline across `src/score2gp/pdf.py`, `src/score2gp/pdf_staff_geometry.py`, `src/score2gp/whole_note_recogniser.py`, `src/score2gp/cli.py`, and `src/score2gp/build_ir.py` establishes the following empirical findings:

### 3.1 Barline Type Classification
- **Seam**: `src/score2gp/pdf.py:filter_tab_barline_candidates()` (lines 3730–3850) and `_detect_tab_systems()` (lines 3880–4112).
- **Current Behavior**: Vertical line segments are extracted from vector drawings. When vertical strokes fall within `DOUBLE_BARLINE_CLUSTERING_TOLERANCE` (12.0 pt), `filter_tab_barline_candidates()` selects a single representative stroke x-coordinate for `valid_barlines` and rejects all adjacent secondary strokes under the code `pdf_barline_double_secondary`.
- **Defect**: The semantic barline style (`double`, `final`, `repeat-start`, `repeat-end`) is lost. The accepted barlines are flattened into a simple array of float x-coordinates (`_TabSystem.barlines: list[float]`). `src/score2gp/ir.py:Bar` supports a `barline` field (`Literal["regular", "double", "end", "section", "repeat-start", "repeat-end"]`), but `build_ir.py` cannot populate it from PDF vector input because the classification was discarded in `pdf.py`.

### 3.2 System and Page Layout Break Inference
- **Seam**: `src/score2gp/pdf.py:_detect_tab_systems()` (lines 3880–4112).
- **Current Behavior**: Systems are inferred purely by top-to-bottom spatial grouping of 6-line horizontal staff line sets on each page. Page breaks are inferred purely by PyMuPDF page indices (`page_number`).
- **Defect**: No explicit data structure represents system-break or page-break evidence independently from staff bounding boxes.

### 3.3 Influence of Barline Type on Layout Breaks
- **Seam**: `src/score2gp/pdf.py:_detect_tab_systems()`.
- **Current Behavior**: Double barlines at system edges currently collapse into single float x-coordinates. Internal double barlines with >2 strokes trigger `pdf_barline_ambiguous`.
- **Defect**: Although double barlines do not explicitly trigger system splits in `_detect_tab_systems()`, the lack of explicit state separation creates ambiguity when barlines are missing or rejected: system boundaries default to fallback edge boundary inference (`infer_edge_boundaries()`), conflating barline presence with system layout boundaries.

### 3.4 Text Extraction and Classification
- **Seam**: `src/score2gp/pdf.py:_extract_pdf_text_candidates()` (lines 753–1700).
- **Current Behavior**: PyMuPDF (`fitz`) extracts text words and blocks (`page.get_text("words")`, `page.get_text("blocks")`). Regex checks match specific tuning phrases (`standard tuning`, `drop d`), string pitch labels (`E`, `B`, `G`, `D`, `A`), and section keywords (`verse`, `intro`, `chorus`).
- **Defect**: All other text elements (such as piece titles, phrase titles, artist names, tempo instructions, or measure annotations) fall through into `non_playable_words` and are emitted as unclassified `candidate-text`.

### 3.5 Title Ownership Representation
- **Seam**: `src/score2gp/pdf.py` and `src/score2gp/pdf_staff_geometry.py`.
- **Current Behavior**: There is zero representation for title-to-system or title-to-measure ownership in `_TabSystem`, `NotationStaffDiagnostics`, or `IR`.
- **Defect**: Text coordinates are completely decoupled from staff and measure bounding boxes. Title text above system 1 has no ownership reference to System 1 or Measure 1.

---

## 4. Required Architecture State Separation

To eliminate coupling and ambiguity, the architecture defines separate representations for each evidence layer.

```
+-------------------------------------------------------------------------------+
|                             PDF VECTOR & TEXT INPUT                           |
+-----------------------+-------------------------------+-----------------------+
                        |                               |
                        v                               v
         +-----------------------------+ +-----------------------------+
         |     BARLINE EVIDENCE        | |     LAYOUT BREAK EVIDENCE   |
         |  (BarlineStyleClassifier)   | |  (System/PageLayoutEvidence)|
         +--------------+--------------+ +--------------+--------------+
                        |                               |
                        +---------------+---------------+
                                        |
                                        v
                         +-----------------------------+
                         |      MEASURE GRID REGION    |
                         |   (Independent Bar Grid)    |
                         +--------------+--------------+
                                        ^
                                        |
         +------------------------------+------------------------------+
         |                                                             |
         v                                                             v
+------------------------------------+               +-----------------------------------+
|      TEXT CLASSIFICATION           |               |       TITLE OWNERSHIP MODEL       |
| (Piece/Phrase/Tempo/Chord/Section) |               |  (System & Measure Association)   |
+------------------------------------+               +-----------------------------------+
```

### 4.1 Data Models (Pydantic / Type Contracts)

```python
from typing import Literal
from pydantic import BaseModel, Field

class BarlineStrokeEvidence(BaseModel):
    """Raw vector stroke candidate forming part of a barline cluster."""
    x0: float
    y0: float
    x1: float
    y1: float
    width: float

class BarlineClassificationEvidence(BaseModel):
    """
    Decoupled barline evidence.
    Classifies style independently of system layout boundaries.
    """
    primary_x: float
    style: Literal["regular", "double", "final", "repeat_start", "repeat_end", "dashed", "hidden"]
    stroke_count: int = Field(ge=1)
    strokes: list[BarlineStrokeEvidence]
    confidence: float = Field(ge=0.0, le=1.0)

class SystemLayoutBreakEvidence(BaseModel):
    """
    Decoupled system break evidence.
    Reflects horizontal system bounds and leading connectors without barline dependency.
    """
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
    """Decoupled page break evidence."""
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
    """Explicit model for unresolved or conflicting structural evidence."""
    feature_kind: Literal["barline_cluster", "overlapping_systems", "conflicting_titles"]
    competing_candidates: list[str]
    resolution_status: Literal["unresolved_refusal", "deferred_to_user"]
```

---

## 5. Required Falsification & Negative Controls

Every architectural rule was evaluated against explicit positive examples, negative controls, ambiguity cases, broken implementation risks, and observable failure modes:

| # | Rule / Claim | Positive Example | Negative Control | Ambiguity / Conflict Case | Smallest Broken Implementation | Observable Output Failure |
|---|--------------|------------------|------------------|---------------------------|--------------------------------|---------------------------|
| **1** | Double barline must not force a system break | Mid-system double barline between measure 2 and 3 | Regular single barline at measure 2 | Double barline within 15pt of system edge | Splitting `_TabSystem` whenever `stroke_count == 2` | Erroneous system break creating two 2-measure systems in output IR |
| **2** | System break must not require a double barline | System 1 ending with a regular single barline | System ending with open staff (no final barline) | System ending near page right margin with missing line | Refusing system break unless rightmost barline has `stroke_count >= 2` | `pdf_barlines_not_detected_in_system` refusal on valid single-barline systems |
| **3** | Page-edge proximity alone must not cause false break | Staff line extending within 10pt of right page edge | Short staff ending 100pt from edge | Fragmented vector stroke near right margin | Triggering layout break if `x1 > page_width - margin` | Truncated measure regions near page margins |
| **4** | Arbitrary text above staff must not become phrase title | Large bold centered text `"Intro"` above measure 1 | Tempo text `"Allegro q=120"` or chord `"Am"` above staff | Mixed text `"Section A - Am"` | Assigning `category="piece_title"` to any text where `y < min_staff_y` | Corrupted track title metadata and invalid chord symbol warnings |
| **5** | One title must not be assigned to multiple systems | Title `"Minuet in G"` assigned exclusively to System 1 | System 2 inheriting top page title | Title vertically equidistant between System 1 and System 2 | Broad y-distance threshold matching all staves on page | Duplicate title annotations emitted on every system in ScoreIR |
| **6** | Generic geometry must not use hardcoded page coordinates | Title classification via font-size ratio `(font_size / staff_height) > 1.2` | Hardcoded threshold `y < 100.0` pt | Small PDF page size (A5 vs A4 vs Letter) | Classifying title using fixed absolute Y coordinate `y < 80.0` | Title misclassified as unclassified on large custom page sizes |

---

## 6. Outcome & Recommended Developer Implementation Slice

- **Selected Outcome**: `CONTINUE`

### 6.1 Bounded Developer Implementation Slice: `CR-05A`
- **Slice Name**: `CR-05A: Barline Style Classification Seam`
- **Authorized Product Files**:
  - `src/score2gp/pdf_staff_geometry.py` (add `barline_style` field to `StructuralSkeletonBarlineCandidate`)
  - `src/score2gp/pdf.py` (update `filter_tab_barline_candidates()` to return `barline_style: Literal["regular", "double", "final"]`)
  - `tests/test_cr05_barline_style_classification.py` (new public test file)
- **Public / Synthetic Fixtures**:
  - `fixtures/public/generated_paired_notation_tab_system_double_barline.json`
  - Synthetic 2-barline double-stroke test fixture in `tests/test_cr05_barline_style_classification.py`
- **Production Seam**:
  In `src/score2gp/pdf.py:filter_tab_barline_candidates()`: when multi-line stroke clusters are detected within `DOUBLE_BARLINE_CLUSTERING_TOLERANCE`, retain the cluster metadata and record `barline_style="double"` or `"final"` on the representative candidate rather than marking secondary strokes as discarded `pdf_barline_double_secondary` errors.
- **Acceptance Assertions**:
  1. Multi-stroke barlines are classified as `barline_style="double"` (or `"final"`) in candidate details.
  2. Single-stroke barlines are classified as `barline_style="regular"`.
  3. System grouping and `valid_barlines` x-coordinates remain identical to baseline.
- **Negative Controls**:
  1. Single vertical line produces `barline_style="regular"`.
  2. No system breaks are added or removed when converting double barline scores.
- **Compatibility Requirements**:
  1. `_TabSystem.barlines` remains a `list[float]` for backward compatibility with `build_ir.py`.
  2. Diagnostic JSON outputs remain schema-compliant with `pdf_staff_geometry_diagnostics_schema.json`.
- **Validation Commands**:
  - `/home/tticom-automation/work/score2gp-workspace/score2gp/.venv/bin/python -m pytest tests/test_cr05_barline_style_classification.py`
  - `/home/tticom-automation/work/score2gp-workspace/score2gp/.venv/bin/python scripts/agent_verify.py`
- **Explicit Non-goals**:
  - No title classification or title ownership changes in `CR-05A`.
  - No system layout break refactoring in `CR-05A`.
  - No changes to product `build_ir.py` conversion logic in `CR-05A`.

---

## 7. Durable Deliverables & Stop Conditions

- **Product Architecture Document**: `docs/design/cr05-structural-layout-and-titles-architecture.md`
- **What Was Not Verified**: Scanned raster-only PDFs without vector line drawings (which require optical music recognition outside current deterministic PDF parsing).
- **Stop Condition**: Publish one product architecture PR in `tticom/score2gp` containing this report on branch `agy/cr05-structural-layout-and-titles-architecture` for independent Codex review. Stop without modifying product source code in `score2gp` or creating governance run records in `score2gp-agentops`.
