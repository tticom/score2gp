from __future__ import annotations

from typing import Any
from score2gp.pdf_geometry_candidates import LeftMarginPrimitiveCandidate

class _BBox:
    def __init__(self, x0: float, y0: float, x1: float, y1: float):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    def distance_to(self, other: _BBox) -> float:
        dx = max(0.0, self.x0 - other.x1, other.x0 - self.x1)
        dy = max(0.0, self.y0 - other.y1, other.y0 - self.y1)
        return max(dx, dy)

    def merge(self, other: _BBox) -> _BBox:
        return _BBox(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1)
        )

def _cluster_curves(curves: list[LeftMarginPrimitiveCandidate], threshold: float) -> list[_BBox]:
    if not curves:
        return []

    bboxes = [_BBox(c.x0, c.y0, c.x1, c.y1) for c in curves]
    parent = {i: i for i in range(len(bboxes))}

    def find(i: int) -> int:
        if parent[i] != i:
            parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int) -> None:
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    for i in range(len(bboxes)):
        for j in range(i + 1, len(bboxes)):
            if bboxes[i].distance_to(bboxes[j]) <= threshold:
                union(i, j)

    grouped: dict[int, _BBox] = {}
    for i in range(len(bboxes)):
        root = find(i)
        if root not in grouped:
            grouped[root] = bboxes[i]
        else:
            grouped[root] = grouped[root].merge(bboxes[i])

    return list(grouped.values())

def classify_logical_clef_candidate(
    candidates: list[LeftMarginPrimitiveCandidate] | None,
    staff_spacing: float,
    staff_height: float,
    staff_x0: float
) -> dict[str, Any]:
    """
    Diagnostic-only read-only classifier to extract logical clef candidate
    evidence from existing left-margin primitive candidates.

    A conservative heuristic is used. If evidence is missing, weak, or
    ambiguous, it fails closed and returns 'unknown'.
    """
    if not candidates:
        return {
            "kind": "logical_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Missing candidate evidence",
            "features": {}
        }

    if staff_spacing <= 0.0 or staff_height <= 0.0:
        return {
            "kind": "logical_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Invalid staff geometry",
            "features": {}
        }

    text_spans = [c for c in candidates if c.kind == "text_span"]
    curves = [c for c in candidates if c.kind == "curve"]

    candidate_groups = []
    for ts in text_spans:
        candidate_groups.append({
            "kind": "text_span",
            "bbox": _BBox(ts.x0, ts.y0, ts.x1, ts.y1)
        })

    for cb in _cluster_curves(curves, staff_spacing):
        candidate_groups.append({
            "kind": "curve_group",
            "bbox": cb
        })

    valid_candidates = []

    for group in candidate_groups:
        bbox = group["bbox"]
        c_height = bbox.y1 - bbox.y0
        c_width = bbox.x1 - bbox.x0

        if c_width <= 0.0 or c_height <= 0.0:
            continue

        height_to_spacing = float(c_height) / float(staff_spacing)
        width_to_spacing = float(c_width) / float(staff_spacing)
        height_to_staff_height = float(c_height) / float(staff_height)
        x0_offset = float(bbox.x0) - float(staff_x0)

        if height_to_spacing >= 3.5 and width_to_spacing >= 1.5 and height_to_staff_height > 1.2:
            valid_candidates.append({
                "candidate_kind": group["kind"],
                "height_to_spacing": round(height_to_spacing, 3),
                "width_to_spacing": round(width_to_spacing, 3),
                "height_to_staff_height": round(height_to_staff_height, 3),
                "x0_offset_from_staff_x0": round(x0_offset, 3)
            })

    if len(valid_candidates) == 1:
        return {
            "kind": "logical_clef_candidate_classifier",
            "label": "treble_clef_candidate",
            "reason": "Candidate matches proportional heuristics for a treble clef",
            "features": valid_candidates[0]
        }
    elif len(valid_candidates) > 1:
        return {
            "kind": "logical_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Ambiguous: multiple competing candidates match heuristics",
            "features": {}
        }
    else:
        return {
            "kind": "logical_clef_candidate_classifier",
            "label": "unknown",
            "reason": "Evidence is ambiguous or does not strongly match treble clef heuristics",
            "features": {}
        }
