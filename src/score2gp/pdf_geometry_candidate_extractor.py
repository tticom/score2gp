from score2gp.pdf_staff_geometry import PrimitiveGeometryEvidence, XAlignedPrimitiveClusterEvidence
from score2gp.pdf_geometry_candidates import LeftMarginPrimitiveCandidate, XAlignedPrimitiveClusterCandidate

class PdfGeometryCandidateExtractor:
    def __init__(self) -> None:
        pass

    def extract_left_margin_candidates(
        self,
        evidence: list[PrimitiveGeometryEvidence]
    ) -> list[LeftMarginPrimitiveCandidate]:
        return []

    def extract_x_aligned_cluster_candidates(
        self,
        evidence: list[XAlignedPrimitiveClusterEvidence]
    ) -> list[XAlignedPrimitiveClusterCandidate]:
        return []
