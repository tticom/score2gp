from score2gp.pdf_staff_geometry import PrimitiveGeometryEvidence, XAlignedPrimitiveClusterEvidence
from score2gp.pdf_geometry_candidates import LeftMarginPrimitiveCandidate, XAlignedPrimitiveClusterCandidate

class PdfGeometryCandidateExtractor:
    def __init__(self) -> None:
        pass

    def extract_left_margin_candidates(
        self,
        page_index: int,
        system_index: int,
        staff_index: int,
        evidence: list[PrimitiveGeometryEvidence]
    ) -> list[LeftMarginPrimitiveCandidate]:
        return [
            LeftMarginPrimitiveCandidate(
                page_index=page_index,
                system_index=system_index,
                staff_index=staff_index,
                x0=item.x0,
                y0=item.y0,
                x1=item.x1,
                y1=item.y1,
                kind=item.kind,
                font_name=item.font_name,
                font_size=item.font_size,
                source="left_margin",
            )
            for item in evidence
        ]

    def extract_x_aligned_cluster_candidates(
        self,
        evidence: list[XAlignedPrimitiveClusterEvidence]
    ) -> list[XAlignedPrimitiveClusterCandidate]:
        return []
