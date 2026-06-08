from score2gp.pdf_staff_notation_diagnostics import cluster_x_aligned_primitives, PrimitiveGeometry

def test_empty_staff_local_primitive_list_produces_zero_clusters() -> None:
    clusters = cluster_x_aligned_primitives([], 10.0)
    assert len(clusters) == 0

def test_invalid_staff_space_does_not_crash() -> None:
    prims = [PrimitiveGeometry("line", 10.0, 100.0, 10.0, 110.0)]
    assert len(cluster_x_aligned_primitives(prims, 0.0)) == 0
    assert len(cluster_x_aligned_primitives(prims, -1.0)) == 0

def test_primitives_within_half_staff_space_group_into_one_cluster() -> None:
    prims = [
        PrimitiveGeometry("line", 10.0, 100.0, 10.0, 110.0),
        PrimitiveGeometry("rect", 14.0, 105.0, 16.0, 107.0),
    ]
    clusters = cluster_x_aligned_primitives(prims, 10.0)
    assert len(clusters) == 1
    assert len(clusters[0]) == 2

def test_primitives_farther_than_half_staff_space_form_separate_clusters() -> None:
    prims = [
        PrimitiveGeometry("line", 10.0, 100.0, 10.0, 110.0),
        PrimitiveGeometry("rect", 25.0, 105.0, 27.0, 107.0),
    ]
    clusters = cluster_x_aligned_primitives(prims, 10.0)
    assert len(clusters) == 2

def test_cluster_ordering_is_deterministic_left_to_right() -> None:
    prims = [
        PrimitiveGeometry("line", 50.0, 100.0, 50.0, 110.0),
        PrimitiveGeometry("rect", 10.0, 105.0, 12.0, 107.0),
        PrimitiveGeometry("curve", 30.0, 105.0, 32.0, 107.0),
    ]
    clusters = cluster_x_aligned_primitives(prims, 10.0)
    assert len(clusters) == 3
    assert clusters[0][0].type == "rect"
    assert clusters[1][0].type == "curve"
    assert clusters[2][0].type == "line"

def test_wide_primitive_does_not_merge_far_compact_primitives() -> None:
    prims = [
        PrimitiveGeometry("line", 10.0, 100.0, 10.0, 110.0),
        PrimitiveGeometry("wide_curve", 10.0, 95.0, 50.0, 98.0), # wide
        PrimitiveGeometry("line", 50.0, 100.0, 50.0, 110.0),
    ]
    # staff_space = 2.5
    # The wide curve-like primitive is wide (40.0 > 2.0 * 2.5 = 5.0)
    # The two lines should NOT be merged into one cluster by the wide primitive
    clusters = cluster_x_aligned_primitives(prims, 2.5)
    # Actually, the wide curve will cluster with the first line (since center 30 is too far, but dx overlap? No, overlap is ignored for wide primitives)
    # Wait, the rule is: `is_compact_prim = width <= 2.0 * staff_space`
    # For wide_curve, width is 40.0. `is_compact_prim` is False. So overlap is False.
    # It will only cluster by center distance! Center is 30.
    # Distance to 10 is 20 > 0.5*2.5. So wide_curve is its own cluster.
    assert len(clusters) == 3

def test_aggregate_counts_are_deterministic_and_correct() -> None:
    from score2gp.pdf_staff_geometry import XAlignedClusterAggregateDiagnostics, ClusterPrimitiveCountSummary
    from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics

    class MockPoint:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    class MockRect:
        def __init__(self, x0, y0, x1, y1):
            self.x0 = x0
            self.y0 = y0
            self.x1 = x1
            self.y1 = y1

    class MockPage:
        def get_drawings(self):
            return [
                {
                    "rect": (10.0, 90.0, 20.0, 110.0),
                    "items": [
                        ("l", MockPoint(10.0, 100.0), MockPoint(10.0, 110.0)),
                        ("re", MockRect(10.5, 105.0, 11.5, 107.0)),
                        ("l", MockPoint(0.0, 100.0), MockPoint(100.0, 100.0)) # Staff line horizontal! Should be excluded from clustering
                    ]
                },
                {
                    "rect": (50.0, 90.0, 60.0, 110.0),
                    "items": [
                        ("l", MockPoint(50.0, 100.0), MockPoint(50.0, 110.0)),
                    ]
                }
            ]

        def get_text(self, opt):
            return {"blocks": []}

    group = [
        MockRect(0, 100, 100, 100),
        MockRect(0, 102.5, 100, 102.5),
        MockRect(0, 105, 100, 105),
        MockRect(0, 107.5, 100, 107.5),
        MockRect(0, 110, 100, 110),
    ]

    diags = build_notation_diagnostics(MockPage(), 1, [group])

    staff_diag = diags.staves[0]
    assert staff_diag.contract_version == "notation-diagnostics.v0.1"
    clustering = staff_diag.clustering

    assert clustering is not None
    assert clustering.x_aligned_cluster_count == 2
    assert clustering.max_primitives_per_x_aligned_cluster == 2

    assert clustering.clusters_with_vertical_stroke_candidate == 1
    assert clustering.cluster_primitive_count_summary.lines_total == 2
    assert clustering.cluster_primitive_count_summary.rects_total == 1

def test_degenerate_staff_spacing_returns_none() -> None:
    from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics
    class MockPage:
        def get_drawings(self): return []
        def get_text(self, opt): return {}

    class MockRect:
        def __init__(self, x0, y0, x1, y1):
            self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    # Degenerate: all Ys the same
    group = [
        MockRect(0, 100, 100, 100),
        MockRect(0, 100, 100, 100),
    ]
    diags = build_notation_diagnostics(MockPage(), 1, [group])
    assert diags.staves[0].clustering is None

def test_diagnostics_schema_does_not_emit_forbidden_semantic_fields() -> None:
    from score2gp.pdf_staff_geometry import NotationStaffDiagnostics
    schema = NotationStaffDiagnostics.model_json_schema()
    schema_str = str(schema).lower()

    forbidden = ["notehead", "pitch", "clef", "chord", "beat", "onset", "rhythm", "duration", "voice", "scoreir_event"]
    for term in forbidden:
        assert term not in schema_str

def test_import_boundary_guardrail() -> None:
    import ast
    from pathlib import Path

    src_dir = Path("src/score2gp")

    forbidden_modules = [
        "pdf_staff_geometry",
        "pdf_staff_notation_diagnostics",
        "pdf_staff_primitive_clustering"
    ]

    check_areas = [
        "ir.py", "build_ir.py", "gpif.py", "gp_package.py",
        "tabraw.py", "pdf_staff_tab_timing_aligner.py", "musicxml.py"
    ]

    for area in check_areas:
        file_path = src_dir / area
        if not file_path.exists():
            continue

        tree = ast.parse(file_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert forbidden not in alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_modules:
                        assert forbidden not in node.module
