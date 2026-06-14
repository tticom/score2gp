from __future__ import annotations
import json
from typing import Any
import pytest
from score2gp.pdf_staff_geometry import NotationStaffDiagnostics, StaffLeftMarginAggregateDiagnostics
from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics
from score2gp.pdf_geometry import _LineSegment

class MockPage:
    def __init__(self, rects: list[tuple[float, float, float, float]] | None = None, curves: list[tuple[float, float, float, float]] | None = None, lines: list[tuple[float, float, float, float]] | None = None):
        self._rects = rects or []
        self._curves = curves or []
        self._lines = lines or []
    def get_drawings(self) -> list[dict[str, Any]]:
        drawings = []
        for (x0, y0, x1, y1) in self._rects:
            class MockRect:
                def __init__(self, x0, y0, x1, y1):
                    self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
            drawings.append({"type": "re", "items": [("re", MockRect(x0, y0, x1, y1))]})
        for (x0, y0, x1, y1) in self._curves:
            class MockPoint:
                def __init__(self, x, y):
                    self.x, self.y = x, y
            drawings.append({"type": "f", "items": [("c", MockPoint(x0, y0), MockPoint(x1, y1))]})
        for (x0, y0, x1, y1) in self._lines:
            class MockPoint:
                def __init__(self, x, y):
                    self.x, self.y = x, y
            drawings.append({"type": "s", "items": [("l", MockPoint(x0, y0), MockPoint(x1, y1))]})
        return drawings
    def get_text(self, option: str) -> dict[str, Any]:
        return {"blocks": []}

class MockPageWithText(MockPage):
    def __init__(self, lines: list[tuple[float, float, float, float]], spans: list[dict[str, Any]]):
        super().__init__(lines=lines)
        self._spans = spans
    def get_text(self, option: str) -> dict[str, Any]:
        return {"blocks": [{"lines": [{"spans": self._spans}]}]}

def test_margin_filtering_counts_and_excludes() -> None:
    # staff.x0 = 10, y0 = 100, y1 = 140
    # staff lines at 100, 110, 120, 130, 140 => staff_space = 10.0
    # margin_x_limit = 10 + 10.0 * 10 = 110.0
    # curve 1 inside margin: x0=20, x1=40 (center 30 <= 110)
    # curve 2 outside margin: x0=120, x1=140 (center 130 > 110)
    # rect 1 inside margin: x0=50, x1=60 (center 55 <= 110)
    page = MockPage(
        lines=[
            (10.0, 100.0, 200.0, 100.0),
            (10.0, 110.0, 200.0, 110.0),
            (10.0, 120.0, 200.0, 120.0),
            (10.0, 130.0, 200.0, 130.0),
            (10.0, 140.0, 200.0, 140.0),
            (30.0, 100.0, 30.0, 140.0), # vertical stroke inside margin
            (150.0, 100.0, 150.0, 140.0), # vertical stroke outside margin
            (30.0, 110.0, 40.0, 120.0), # diagonal stroke inside margin
        ],
        curves=[
            (20.0, 100.0, 40.0, 140.0),
            (120.0, 100.0, 140.0, 140.0),
        ],
        rects=[
            (50.0, 110.0, 60.0, 120.0),
        ]
    )
    # x0=10.0, y0=100.0, x1=200.0, y1=140.0
    staff_groups = [[_LineSegment(10.0, y, 200.0, y) for y in [100.0, 110.0, 120.0, 130.0, 140.0]]]
    diags = build_notation_diagnostics(page, 1, staff_groups)
    assert len(diags.staves) == 1
    assert diags.staves[0].contract_version == "notation-diagnostics.v0.1"
    lm = diags.staves[0].left_margin
    assert lm is not None
    assert lm.curve_candidate_count == 1
    assert lm.vertical_stroke_candidate_count == 1
    assert lm.rectangle_candidate_count == 1
    
    evidence = lm.evidence
    assert evidence is not None
    assert len(evidence) == 4
    kinds = [e.kind for e in evidence]
    assert "diagonal_stroke" in kinds

def test_invalid_staff_space_fallback() -> None:
    # 0 or 1 staff line yields staff_space = 0.0
    page = MockPage(lines=[(10.0, 100.0, 200.0, 100.0)])
    staff_groups = [[_LineSegment(10.0, 100.0, 200.0, 100.0)]]
    diags = build_notation_diagnostics(page, 1, staff_groups)
    assert len(diags.staves) == 1
    assert diags.staves[0].left_margin is None

def test_aggregate_accuracy() -> None:
    # test font distributions
    # margin_x_limit = 110
    spans = [
        {"text": "f", "font": "Maestro", "bbox": (20, 110, 30, 120)}, # inside, Maestro
        {"text": "p", "font": "Maestro", "bbox": (40, 110, 50, 120)}, # inside, Maestro
        {"text": "1", "font": "Arial", "bbox": (60, 110, 70, 120)},   # inside, Arial
        {"text": "g", "font": "Opus", "bbox": (120, 110, 130, 120)},  # outside, Opus
    ]
    page = MockPageWithText(
        lines=[
            (10.0, 100.0, 200.0, 100.0),
            (10.0, 110.0, 200.0, 110.0),
            (10.0, 120.0, 200.0, 120.0),
            (10.0, 130.0, 200.0, 130.0),
            (10.0, 140.0, 200.0, 140.0),
        ],
        spans=spans
    )
    staff_groups = [[_LineSegment(10.0, y, 200.0, y) for y in [100.0, 110.0, 120.0, 130.0, 140.0]]]
    diags = build_notation_diagnostics(page, 1, staff_groups)
    lm = diags.staves[0].left_margin
    assert lm is not None
    assert lm.text_span_count == 3
    assert lm.distinct_font_count == 2
    assert lm.max_text_spans_for_single_font == 2

def test_schema_does_not_contain_semantic_names() -> None:
    # Ensure JSON schema of the diagnostics does not leak keys like "clef", "pitch", "time_signature"
    schema = StaffLeftMarginAggregateDiagnostics.model_json_schema()
    schema_str = json.dumps(schema).lower()
    for forbidden in ["clef", "pitch", "time_signature", "key_signature", "notehead", "duration"]:
        assert forbidden not in schema_str

    top_level_schema = NotationStaffDiagnostics.model_json_schema()
    top_level_schema_str = json.dumps(top_level_schema).lower()
    for forbidden in ["clef", "pitch", "time_signature", "key_signature", "notehead", "duration"]:
        assert forbidden not in top_level_schema_str

def test_schema_snapshot_gate() -> None:
    from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics
    from pathlib import Path

    schema_path = Path(__file__).parent.parent / "fixtures" / "public" / "pdf_staff_geometry_diagnostics_schema.json"

    # Load the reference schema
    with open(schema_path, "r", encoding="utf-8") as f:
        reference_schema = json.load(f)

    # Generate current schema
    current_schema = PdfStaffNotationGeometryDiagnostics.model_json_schema()

    # Compare. If this fails, it means a documented field was renamed or removed,
    # or the schema drifted in a way that breaks the stability gate.
    # To intentionally update the schema, developer must regenerate the fixture.
    assert current_schema == reference_schema, (
        "Geometry diagnostics schema has changed! "
        "If intentional, regenerate fixtures/public/pdf_staff_geometry_diagnostics_schema.json"
    )

def test_generated_dense_margin_fixture(tmp_path) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_dense_margin.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]
    lm = staff_diag.get("left_margin")
    assert lm is not None

    # The json spec defines multiple margin text spans all using the same font ('helv')
    # Fitz may heuristically merge adjacent spans into a single span, so we check >= 6
    assert lm["text_span_count"] >= 6
    assert lm["distinct_font_count"] == 1
    assert lm["max_text_spans_for_single_font"] >= 6

def test_quarter_note_candidate_diagnostics() -> None:
    import fitz
    from pathlib import Path
    from score2gp.pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_quarter_note.pdf"
    assert pdf_path.exists(), f"Missing fixture: {pdf_path}"

    with fitz.open(pdf_path) as doc:
        page = doc[0]
        diags = extract_notation_diagnostics_dict(page, 1)

    cands = diags.get("quarter_note_candidates", [])
    assert cands is not None
    assert len(cands) == 2
    assert cands[0]["aspect_ratio"] >= 1.2
    assert cands[0]["width"] > 0
    assert cands[0]["height"] > 0


def test_generated_sparse_fixture(tmp_path) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_sparse.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]
    lm = staff_diag.get("left_margin")
    assert lm is not None

    assert lm["text_span_count"] == 0
    assert lm["distinct_font_count"] == 0
    assert lm["max_text_spans_for_single_font"] == 0

def test_generated_wide_curves_fixture(tmp_path) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_wide_curves.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]

    # Assert stable non-margin wide-curve diagnostic presence across the whole staff region
    prims = staff_diag.get("primitives", {})
    assert prims.get("curve_count", 0) == 2

    morph = staff_diag.get("morphology", {})
    if morph:
        assert morph.get("curve_candidate", 0) == 2

    # Since left-margin diagnostics also expose curve counts, assert only the one
    # curve whose geometric centre falls inside the 10-staff-space left-margin window.
    lm = staff_diag.get("left_margin")
    if lm:
        assert lm["curve_candidate_count"] == 1
        assert lm["text_span_count"] == 0

def test_generated_complex_cluster_fixture(tmp_path) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_complex_cluster.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]
    clustering = staff_diag.get("clustering")
    assert clustering is not None

    # The fixture has two note clusters
    # Cluster 1: x around 200. Has 1 vertical stroke (stem), 1 rect (notehead), 1 text (#).
    # Cluster 2: x around 300. Has 1 vertical stroke (stem), 2 rects (noteheads), 1 horizontal line (ledger).
    # The fixture has two barlines, one separate text cluster, and two note clusters. Total = 5 clusters.
    assert clustering["x_aligned_cluster_count"] == 5

    # max_primitives_per_x_aligned_cluster should be at least 4 for cluster 2 (1 vertical, 2 rects, 1 ledger)
    assert clustering["max_primitives_per_x_aligned_cluster"] >= 4

    assert clustering["clusters_with_vertical_stroke_candidate"] >= 1

    summary = clustering.get("cluster_primitive_count_summary", {})
    # lines_total: 2 barlines + 1 vertical for cluster 1 + 1 vertical and 1 horizontal for cluster 2 => 5 lines
    assert summary.get("lines_total", 0) >= 3
    assert summary.get("rects_total", 0) == 3
    assert summary.get("text_spans_total", 0) >= 1

    evidence = clustering.get("evidence", [])
    assert len(evidence) == clustering["x_aligned_cluster_count"]
    
    # Check cluster 2 logic: 1 vertical, 2 rects, 1 horizontal
    cluster2 = next((e for e in evidence if e["primitive_count"] >= 4), None)
    assert cluster2 is not None
    assert cluster2["primitive_count"] == len(cluster2["primitives"])
    
    kinds = [p["kind"] for p in cluster2["primitives"]]
    assert kinds.count("vertical_stroke") >= 1
    assert kinds.count("rectangle") == 2
    assert kinds.count("horizontal_stroke") >= 1

def test_inspect_pdf_multi_staff_fixture(tmp_path: Any) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_multi_staff.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 2

    # Verify that the two staves are correctly assigned to the same system
    assert staves[0]["staff"]["system_index"] == 1
    assert staves[1]["staff"]["system_index"] == 1

    assert staves[0]["staff"]["staff_index"] == 1
    assert staves[1]["staff"]["staff_index"] == 2

    connectors = diags.get("system_connectors", [])
    assert len(connectors) == 1

    conn = connectors[0]
    assert conn["connector_kind"] == "leading_barline"
    assert conn["connected_staff_indices"] == [1, 2]

    # Assert connector bounds match the actual geometry in generated_standard_staff_multi_staff.json
    # x is 50.0, y_min is 100.0, y_max is 284.0
    # PyMuPDF line bounds might include width/2
    assert abs(conn["x0"] - 50.0) < 1.0
    assert abs(conn["x1"] - 50.0) < 1.0
    assert abs(conn["y0"] - 100.0) < 1.0
    assert abs(conn["y1"] - 284.0) < 1.0

def test_inspect_pdf_rectangle_positions_fixture(tmp_path: Any) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_rectangle_positions.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]

    # Primitives total rect count should be 2 (1 in margin, 1 in body)
    prims = staff_diag.get("primitives", {})
    assert prims.get("rect_count", 0) == 2

    # Left margin should have 1 rectangle candidate
    left_margin = staff_diag.get("left_margin", {})
    assert left_margin.get("rectangle_candidate_count", 0) == 1

    # Therefore, body rects = total - margin = 2 - 1 = 1
    body_rects = prims.get("rect_count", 0) - left_margin.get("rectangle_candidate_count", 0)
    assert body_rects == 1

def test_inspect_pdf_multi_staff_unconnected_fixture(tmp_path: Any) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_multi_staff_unconnected.pdf"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)

    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 2

    # Verify that the two staves are correctly assigned to DIFFERENT systems
    assert staves[0]["staff"]["system_index"] == 1
    assert staves[1]["staff"]["system_index"] == 2

    assert staves[0]["staff"]["staff_index"] == 1
    assert staves[1]["staff"]["staff_index"] == 1

    connectors = diags.get("system_connectors", [])
    assert len(connectors) == 0

def test_inspect_pdf_text_font_diversity_fixture(tmp_path: Any) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path
    import json
    import math

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_text_font_diversity.pdf"
    json_path = pdf_path.parents[3] / "fixtures" / "public" / "generated_standard_staff_text_font_diversity.json"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)
    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]
    left_margin = staff_diag.get("left_margin", {})

    with open(json_path, "r") as f:
        fixture_data = json.load(f)

    # Note cluster texts were put in the left margin
    fixture_texts = fixture_data["note_clusters"][0]["texts"]

    staff_geom = staff_diag["staff"]
    staff_x0 = staff_geom["x0"]
    staff_space = staff_geom["line_y_coords"][1] - staff_geom["line_y_coords"][0]
    margin_threshold = staff_x0 + (10.0 * staff_space)

    # Assert explicit coordinates and properties from fixture
    for fixture_text in fixture_texts:
        # Calculate center x (since fixture texts x is just the left edge, we approximate center_x as x + small width)
        # Actually in the fixture we have "x" and "y" which are used to place the text.
        # The margin threshold is staff_x0 + 10.0 * staff_space.
        # staff_space = 8.5, margin = 100.0 + 85.0 = 185.0
        # The fixture text "x" is 110.0, so the center will be roughly 115.0 which is <= 185.0
        fixture_center_x = fixture_text["x"] + 5.0
        assert staff_x0 <= fixture_center_x <= margin_threshold

    # Assert diagnostics counts
    assert left_margin.get("text_span_count", 0) == 3
    assert left_margin.get("distinct_font_count", 0) == 2
    assert left_margin.get("max_text_spans_for_single_font", 0) == 2

def test_inspect_pdf_left_margin_threshold_fixture(tmp_path: Any) -> None:
    from score2gp.pdf import inspect_pdf
    from pathlib import Path
    import json

    pdf_path = Path(__file__).parent / "fixtures" / "pdf" / "generated_standard_staff_left_margin_threshold.pdf"
    json_path = pdf_path.parents[3] / "fixtures" / "public" / "generated_standard_staff_left_margin_threshold.json"
    out_dir = tmp_path / "out"

    result = inspect_pdf(pdf_path, out_dir)
    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags.get("status") == "success"

    staves = diags.get("staves", [])
    assert len(staves) == 1

    staff_diag = staves[0]
    left_margin = staff_diag.get("left_margin", {})

    with open(json_path, "r") as f:
        fixture_data = json.load(f)

    staff_geom = staff_diag["staff"]
    staff_x0 = staff_geom["x0"]
    staff_space = staff_geom["line_y_coords"][1] - staff_geom["line_y_coords"][0]
    margin_threshold = staff_x0 + (10.0 * staff_space)

    inside_cluster = fixture_data["note_clusters"][0]
    outside_cluster = fixture_data["note_clusters"][1]
    inside_curve = fixture_data["wide_curves"][0]
    outside_curve = fixture_data["wide_curves"][1]
    
    # Assert Inside properties
    inside_rect_center = (inside_cluster["rects"][0]["x0"] + inside_cluster["rects"][0]["x1"]) / 2.0
    inside_line_center = (inside_cluster["lines"][0]["x0"] + inside_cluster["lines"][0]["x1"]) / 2.0
    inside_text_center = inside_cluster["texts"][0]["x"] + 5.0
    inside_curve_center = (inside_curve["p0"][0] + inside_curve["p3"][0]) / 2.0

    assert staff_x0 <= inside_rect_center <= margin_threshold
    assert staff_x0 <= inside_line_center <= margin_threshold
    assert staff_x0 <= inside_text_center <= margin_threshold
    assert staff_x0 <= inside_curve_center <= margin_threshold

    # Assert Outside properties (should be outside margin threshold, but still inside staff box)
    outside_rect_center = (outside_cluster["rects"][0]["x0"] + outside_cluster["rects"][0]["x1"]) / 2.0
    outside_line_center = (outside_cluster["lines"][0]["x0"] + outside_cluster["lines"][0]["x1"]) / 2.0
    outside_text_center = outside_cluster["texts"][0]["x"] + 5.0
    outside_curve_center = (outside_curve["p0"][0] + outside_curve["p3"][0]) / 2.0

    assert not (staff_x0 <= outside_rect_center <= margin_threshold)
    assert not (staff_x0 <= outside_line_center <= margin_threshold)
    assert not (staff_x0 <= outside_text_center <= margin_threshold)
    assert not (staff_x0 <= outside_curve_center <= margin_threshold)
    
    assert staff_geom["x0"] <= outside_rect_center <= staff_geom["x1"]
    assert staff_geom["x0"] <= outside_line_center <= staff_geom["x1"]
    assert staff_geom["x0"] <= outside_text_center <= staff_geom["x1"]
    assert staff_geom["x0"] <= outside_curve_center <= staff_geom["x1"]

    assert left_margin.get("text_span_count", 0) == 1
    assert left_margin.get("curve_candidate_count", 0) == 1
    assert left_margin.get("vertical_stroke_candidate_count", 0) == 1
    assert left_margin.get("rectangle_candidate_count", 0) == 1

    evidence = left_margin.get("evidence", [])
    assert len(evidence) == 4
    
    rect_ev = next(e for e in evidence if e["kind"] == "rectangle")
    assert abs(rect_ev["x0"] - inside_cluster["rects"][0]["x0"]) < 2.0
    assert abs(rect_ev["x1"] - inside_cluster["rects"][0]["x1"]) < 2.0
    assert abs(rect_ev["y0"] - inside_cluster["rects"][0]["y0"]) < 2.0
    assert abs(rect_ev["y1"] - inside_cluster["rects"][0]["y1"]) < 2.0

    stroke_ev = next(e for e in evidence if e["kind"] == "vertical_stroke")
    assert abs(stroke_ev["x0"] - inside_cluster["lines"][0]["x0"]) < 2.0
    assert abs(stroke_ev["x1"] - inside_cluster["lines"][0]["x1"]) < 2.0
    assert abs(stroke_ev["y0"] - inside_cluster["lines"][0]["y0"]) < 2.0
    assert abs(stroke_ev["y1"] - inside_cluster["lines"][0]["y1"]) < 2.0

    curve_ev = next(e for e in evidence if e["kind"] == "curve")
    assert abs(curve_ev["x0"] - inside_curve["p0"][0]) < 2.0
    assert abs(curve_ev["y0"] - min(p[1] for p in [inside_curve["p0"], inside_curve["p1"], inside_curve["p2"], inside_curve["p3"]])) < 2.0
    assert abs(curve_ev["y1"] - max(p[1] for p in [inside_curve["p0"], inside_curve["p1"], inside_curve["p2"], inside_curve["p3"]])) < 2.0

    text_ev = next(e for e in evidence if e["kind"] == "text_span")
    assert text_ev["font_name"] is not None
    assert "helv" in text_ev["font_name"].lower()
    assert text_ev["x0"] > 0.0 and text_ev["x1"] > text_ev["x0"]
    assert text_ev["y0"] > 0.0 and text_ev["y1"] > text_ev["y0"]
