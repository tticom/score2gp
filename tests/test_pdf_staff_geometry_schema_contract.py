import json
from score2gp.pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics

def test_schema_required_fields_contract() -> None:
    schema = PdfStaffNotationGeometryDiagnostics.model_json_schema()
    schema_str = json.dumps(schema)
    
    required_fields = [
        "staves",
        "staff",
        "primitives",
        "morphology",
        "clustering",
        "left_margin",
        "x_aligned_cluster_count",
        "max_primitives_per_x_aligned_cluster",
        "cluster_primitive_count_summary",
        "text_span_count",
        "curve_candidate_count",
        "vertical_stroke_candidate_count",
        "rectangle_candidate_count"
    ]
    
    for field in required_fields:
        assert f'"{field}"' in schema_str, f"Required diagnostic field '{field}' is missing from schema!"
