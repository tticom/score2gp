import pytest
import re
from unittest.mock import MagicMock
from score2gp.pdf_staff_geometry import NotationStaffDiagnostics
from score2gp.pdf_geometry_candidate_extraction import extract_geometry_candidates
from score2gp.pdf_geometry_candidates import GeometryCandidateSet

def test_extract_geometry_candidates_returns_empty_set_initially():
    diagnostics = MagicMock(spec=NotationStaffDiagnostics)
    result = extract_geometry_candidates(diagnostics)
    assert isinstance(result, GeometryCandidateSet)
    assert len(result.left_margin_primitives) == 0
    assert len(result.x_aligned_clusters) == 0

def test_geometry_candidate_set_schema_has_no_semantic_leakage():
    schema = GeometryCandidateSet.model_json_schema()
    schema_str = str(schema).lower()

    forbidden_words = [
        "notehead", "stem", "clef", "pitch", "duration",
        "voice", "chord", "key_signature", "time_signature",
        "beat", "rhythm"
    ]

    for word in forbidden_words:
        # use word boundaries to avoid matching "system" for "stem"
        pattern = r'\b' + word + r'\b'
        assert not re.search(pattern, schema_str), f"Semantic leakage detected: {word} found in GeometryCandidateSet schema"
