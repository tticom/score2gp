from score2gp.pdf_staff_geometry import NotationStaffDiagnostics
from score2gp.pdf_geometry_candidates import GeometryCandidateSet

def extract_geometry_candidates(diagnostics: NotationStaffDiagnostics) -> GeometryCandidateSet:
    """
    Extract geometry-only candidates from notation staff diagnostics.

    Candidate semantics are intentionally limited to geometry provenance:
    this function transfers already-computed diagnostic candidates into the
    page-level export shape without assigning musical meaning.
    """
    return GeometryCandidateSet(
        left_margin_primitives=list(diagnostics.left_margin_candidates or []),
        x_aligned_clusters=list(diagnostics.x_aligned_cluster_candidates or []),
    )
