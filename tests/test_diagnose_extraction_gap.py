from score2gp.pdf_geometry_candidates import LeftMarginPrimitiveCandidate
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "scripts"))
from diagnose_task175_extraction_gap import diagnose_extraction_failure

def test_diagnose_extraction_failure_treble_clef():
    res = diagnose_extraction_failure([], 10.0, 40.0, 50.0, {"label": "treble_clef_candidate"})
    assert res == "treble_clef_candidate"

def test_diagnose_extraction_failure_no_margin():
    res = diagnose_extraction_failure([], 10.0, 40.0, 50.0, {"label": "unknown", "reason": "Missing candidate evidence"})
    assert res == "no_left_margin"

def test_diagnose_extraction_failure_invalid_staff():
    res = diagnose_extraction_failure([], 0.0, 40.0, 50.0, {"label": "unknown", "reason": "Invalid staff geometry"})
    assert res == "staff_association_missing_or_malformed"

def test_diagnose_extraction_failure_wrong_type():
    cands = [
        LeftMarginPrimitiveCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=0, y0=0, x1=10, y1=10, kind="rectangle", source="left_margin"
        )
    ]
    res = diagnose_extraction_failure(cands, 10.0, 40.0, 50.0, {"label": "unknown"})
    assert res == "primitives_found_but_wrong_type"

def test_diagnose_extraction_failure_too_fragmented():
    cands = [
        LeftMarginPrimitiveCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=0, y0=0, x1=10, y1=10, kind="curve", source="left_margin"
        ) for _ in range(11)
    ]
    res = diagnose_extraction_failure(cands, 10.0, 40.0, 50.0, {"label": "unknown"})
    assert res == "primitives_found_but_too_fragmented"

def test_diagnose_extraction_failure_ambiguous():
    cands = [
        LeftMarginPrimitiveCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=50, y0=180, x1=80, y1=250, kind="text_span", source="left_margin"
        )
    ]
    res = diagnose_extraction_failure(cands, 10.0, 40.0, 50.0, {"label": "unknown", "reason": "Ambiguous: multiple candidates"})
    assert res == "primitives_found_but_ambiguous"

def test_diagnose_extraction_failure_malformed():
    cands = [
        LeftMarginPrimitiveCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=50, y0=180, x1=50, y1=180, kind="text_span", source="left_margin" # zero width/height
        )
    ]
    res = diagnose_extraction_failure(cands, 10.0, 40.0, 50.0, {"label": "unknown"})
    assert res == "primitives_found_but_malformed"

def test_diagnose_extraction_failure_outside_region():
    cands = [
        LeftMarginPrimitiveCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=500, y0=180, x1=530, y1=250, kind="text_span", source="left_margin" # far from staff_x0=50.0
        )
    ]
    res = diagnose_extraction_failure(cands, 10.0, 40.0, 50.0, {"label": "unknown"})
    assert res == "primitives_found_but_outside_staff_region"

def test_diagnose_extraction_failure_failing_thresholds():
    cands = [
        LeftMarginPrimitiveCandidate(
            page_index=1, system_index=1, staff_index=1,
            x0=50, y0=180, x1=60, y1=190, kind="text_span", source="left_margin" # short, near staff_x0=50.0
        )
    ]
    res = diagnose_extraction_failure(cands, 10.0, 40.0, 50.0, {"label": "unknown"})
    assert res == "primitives_found_but_failing_classifier_thresholds"
