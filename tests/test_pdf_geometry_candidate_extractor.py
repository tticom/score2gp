from score2gp.pdf_geometry_candidate_extractor import PdfGeometryCandidateExtractor
from score2gp.pdf_staff_geometry import PrimitiveGeometryEvidence, XAlignedPrimitiveClusterEvidence

def test_extractor_accepts_evidence_and_returns_empty() -> None:
    extractor = PdfGeometryCandidateExtractor()
    
    # Left margin dummy input
    left_margin_evidence = [
        PrimitiveGeometryEvidence(
            page_index=1,
            system_index=1,
            staff_index=1,
            x0=10.0,
            y0=20.0,
            x1=30.0,
            y1=40.0,
            kind="rectangle",
            font_name=None,
            font_size=None
        )
    ]
    left_margin_candidates = extractor.extract_left_margin_candidates(left_margin_evidence)
    assert left_margin_candidates == []
    
    # X-aligned cluster dummy input
    cluster_evidence = [
        XAlignedPrimitiveClusterEvidence(
            page_index=1,
            system_index=1,
            staff_index=1,
            x0=10.0,
            x1=30.0,
            primitive_count=1,
            primitives=[
                PrimitiveGeometryEvidence(
                    page_index=1,
                    system_index=1,
                    staff_index=1,
                    x0=10.0,
                    y0=20.0,
                    x1=30.0,
                    y1=40.0,
                    kind="vertical_stroke",
                    font_name=None,
                    font_size=None
                )
            ]
        )
    ]
    cluster_candidates = extractor.extract_x_aligned_cluster_candidates(cluster_evidence)
    assert cluster_candidates == []
