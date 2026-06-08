import pytest
from score2gp.pdf_geometry_candidates import (
    CircularMarkerCandidate,
    VerticalStrokeCandidate,
    HorizontalStrokeCandidate,
    CurveMarkerCandidate,
    RectangleMarkerCandidate,
    TextMarkerCandidate,
    XAlignedPrimitiveCluster,
)
from pydantic import ValidationError

def test_geometry_candidate_bounds() -> None:
    # Valid
    c = CircularMarkerCandidate(x0=10.0, y0=20.0, x1=15.0, y1=25.0)
    assert c.x0 == 10.0
    
    # Invalid x bounds
    with pytest.raises(ValidationError, match="x0 must be <= x1"):
        CircularMarkerCandidate(x0=15.0, y0=20.0, x1=10.0, y1=25.0)

    # Invalid y bounds
    with pytest.raises(ValidationError, match="y0 must be <= y1"):
        VerticalStrokeCandidate(x0=10.0, y0=30.0, x1=15.0, y1=20.0)

def test_frozen_models() -> None:
    c = RectangleMarkerCandidate(x0=10.0, y0=20.0, x1=15.0, y1=25.0)
    with pytest.raises(ValidationError):
        c.x0 = 12.0

def test_x_aligned_primitive_cluster() -> None:
    c = CircularMarkerCandidate(x0=10.0, y0=20.0, x1=12.0, y1=22.0)
    cluster = XAlignedPrimitiveCluster(
        x0=10.0,
        x1=15.0,
        circular_markers=(c,)
    )
    assert len(cluster.circular_markers) == 1
    
    with pytest.raises(ValidationError, match="x0 must be <= x1"):
        XAlignedPrimitiveCluster(x0=20.0, x1=10.0)
