# Raster Diagnostics Failure Taxonomy

This document outlines the failure taxonomy for raster diagnostic candidate classifiers (specifically the treble clef candidate classifier) based on anonymised findings from private corpus reviews (e.g., Task 63).

**Important:** This document must remain anonymised and must not expose private fixture names, page images, screenshots, or copyrighted/private content.

## False Negatives Taxonomy (Treble Clef Candidates)

During the diagnostic review, false negatives (valid treble clefs that were classified as `unknown`) were observed. The failures fall into the following anonymised categories:

### 1. Stylized / Non-Standard Fonts
- **Description:** The proportions (height-to-width or height-to-spacing ratios) of the printed clef fall outside the rigid heuristic thresholds.
- **Diagnostic impact:** The candidate is rejected because the bounds do not resemble a standard treble clef shape.
- **Future mitigation:** Expand heuristic bounds when supported by broader evidence, or introduce a more permissive secondary check if isolated from other symbols.

### 2. Extraneous Symbol Overlap
- **Description:** Other musical symbols (e.g., ties, slurs, ledger lines, or `8va` text) physically touch or overlap the clef's bounding box.
- **Diagnostic impact:** The connected components are merged, creating an oversized or disproportionate candidate rectangle that is rejected.
- **Future mitigation:** Implement contour analysis or split disjoint bounding boxes based on internal density.

### 3. Raster Degradation / Fragmentation
- **Description:** Poor scan quality, low resolution, or binarization artifacts cause the clef to break into multiple disjoint candidate boxes.
- **Diagnostic impact:** None of the individual fragments meet the size threshold for a full clef.
- **Future mitigation:** Pre-process morphological closing or cluster nearby fragments before classification.

### 4. Edge Clipping
- **Description:** The clef is partially clipped by the page margin or a harsh scan boundary.
- **Diagnostic impact:** The detected bounding box is too narrow or too short.
- **Future mitigation:** Flag clipped candidates near margins for manual review or context-based inference.

### 5. Multi-Staff / Grand Staff Merging
- **Description:** A bracket or brace connecting a grand staff physically touches the treble clef.
- **Diagnostic impact:** The candidate expands vertically to encompass the entire system, failing the `height_to_spacing` check.
- **Future mitigation:** Detect and strip vertical connectors (brackets/braces) before classifying opening symbols.

---
*Note: This taxonomy is for diagnostic tracking only and does not authorise semantic promotion of candidates.*
