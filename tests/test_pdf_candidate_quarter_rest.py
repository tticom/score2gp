import pytest
from score2gp.pdf_geometry_candidates import (
    GeometryCandidateSet,
    XAlignedPrimitiveClusterCandidate,
    PrimitiveEvidenceCandidate
)
from score2gp.pdf_candidate_quarter_rest import extract_quarter_rest_candidates
from score2gp.pdf_candidate_whole_half_rest import extract_whole_half_rest_candidates

def make_cluster(kind: str, x0: float, y0: float, x1: float, y1: float, count: int = 1) -> XAlignedPrimitiveClusterCandidate:
    prims = []
    for _ in range(count):
        prims.append(
            PrimitiveEvidenceCandidate(
                page_index=1,
                system_index=1,
                staff_index=1,
                x0=x0, y0=y0, x1=x1, y1=y1,
                kind=kind,  # type: ignore
                source="x_aligned_cluster"
            )
        )
    return XAlignedPrimitiveClusterCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=x0, x1=x1,
        primitive_count=count,
        primitives=prims
    )

def test_extract_quarter_rest_success():
    # Staff spacing 10, center y = 50 (e.g. staff from 30 to 70)
    # Quarter rest height ~ 30, width ~ 10, center ~ 50
    cluster = make_cluster("curve", x0=100.0, y0=35.0, x1=110.0, y1=65.0)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    rests = extract_quarter_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(rests) == 1
    assert rests[0].x0 == 100.0
    assert rests[0].y1 == 65.0

def test_extract_quarter_rest_fails_isolation():
    # Two primitives in the cluster
    cluster = make_cluster("curve", x0=100.0, y0=35.0, x1=110.0, y1=65.0, count=2)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    rests = extract_quarter_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(rests) == 0

def test_extract_quarter_rest_fails_height_ratio():
    # Too short (height = 10, ratio = 1.0)
    cluster = make_cluster("curve", x0=100.0, y0=45.0, x1=110.0, y1=55.0)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    rests = extract_quarter_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(rests) == 0

def test_extract_quarter_rest_fails_aspect_ratio():
    # Too wide (width = 30, height = 30 -> ratio 1.0)
    cluster = make_cluster("curve", x0=100.0, y0=35.0, x1=130.0, y1=65.0)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    rests = extract_quarter_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(rests) == 0

def test_extract_quarter_rest_fails_vertical_centering():
    # Centered at 30, but staff center is 50. Difference is 20 > 5.0 (0.5 * 10)
    cluster = make_cluster("curve", x0=100.0, y0=15.0, x1=110.0, y1=45.0)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    rests = extract_quarter_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(rests) == 0

def test_extract_quarter_rest_ignores_whole_rest():
    # Whole rest is wider than tall and hanging/short (e.g. width = 12, height = 5)
    cluster = make_cluster("curve", x0=100.0, y0=35.0, x1=112.0, y1=40.0)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    rests = extract_quarter_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(rests) == 0

def test_extract_quarter_rest_ignores_half_rest():
    # Half rest is wider than tall and sitting/short (e.g. width = 12, height = 5)
    cluster = make_cluster("curve", x0=100.0, y0=45.0, x1=112.0, y1=50.0)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    rests = extract_quarter_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(rests) == 0

def test_extract_quarter_rest_ignores_overlapping_polyphonic_cluster():
    # Multiple overlapping primitives in the cluster
    cluster = make_cluster("curve", x0=100.0, y0=35.0, x1=110.0, y1=65.0, count=3)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    rests = extract_quarter_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(rests) == 0

def test_extract_whole_rest_success():
    # Whole rest is wider than tall (width = 12, height = 5)
    # y0 = 35.0, y1 = 40.0 (center 37.5 -> in range 50 - 16..50 - 4 = [34, 46])
    cluster = make_cluster("curve", x0=100.0, y0=35.0, x1=112.0, y1=40.0)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    wholes, halfs = extract_whole_half_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(wholes) == 1
    assert len(halfs) == 0
    assert wholes[0].x0 == 100.0
    assert wholes[0].y1 == 40.0

def test_extract_half_rest_success():
    # Half rest is wider than tall (width = 12, height = 5)
    # y0 = 45.0, y1 = 50.0 (center 47.5 -> in range 50 - 4..50 + 4 = [46, 54])
    cluster = make_cluster("curve", x0=100.0, y0=45.0, x1=112.0, y1=50.0)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])

    wholes, halfs = extract_whole_half_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(wholes) == 0
    assert len(halfs) == 1
    assert halfs[0].x0 == 100.0
    assert halfs[0].y1 == 50.0

def test_extract_whole_half_rest_ignored_if_tall():
    # Tall cluster (height = 20) is ignored
    cluster = make_cluster("curve", x0=100.0, y0=30.0, x1=110.0, y1=50.0)
    geometry = GeometryCandidateSet(x_aligned_clusters=[cluster])
    wholes, halfs = extract_whole_half_rest_candidates(geometry, staff_spacing=10.0, staff_center_y=50.0)
    assert len(wholes) == 0
    assert len(halfs) == 0
