import inspect
import json
import re
from pathlib import Path
import score2gp.pdf_geometry_candidates as candidates_module
from score2gp.pdf_geometry_candidates import (
    PrimitiveEvidenceCandidate,
    LeftMarginPrimitiveCandidate,
    XAlignedPrimitiveClusterCandidate
)

FORBIDDEN_SEMANTIC_TERMS = [
    "notehead", "stem", "clef", "pitch", "duration",
    "voice", "chord", "key_signature", "time_signature",
    "beat", "rhythm", "scoreir"
]

def test_anti_semantic_leakage_in_schemas() -> None:
    schemas = [
        PrimitiveEvidenceCandidate.model_json_schema(),
        LeftMarginPrimitiveCandidate.model_json_schema(),
        XAlignedPrimitiveClusterCandidate.model_json_schema()
    ]
    schema_str = json.dumps(schemas)
    
    for term in FORBIDDEN_SEMANTIC_TERMS:
        pattern = r'\b' + term + r'\b'
        assert not re.search(pattern, schema_str, re.IGNORECASE), f"Forbidden semantic term '{term}' found in candidate schema!"

def test_anti_semantic_leakage_in_public_names() -> None:
    public_names = [name for name in dir(candidates_module) if not name.startswith("_")]
    names_str = " ".join(public_names)
    
    for term in FORBIDDEN_SEMANTIC_TERMS:
        pattern = r'\b' + term + r'\b'
        assert not re.search(pattern, names_str, re.IGNORECASE), f"Forbidden semantic term '{term}' found in public names: {public_names}"

def test_anti_semantic_leakage_in_source_file() -> None:
    source_file = Path(candidates_module.__file__)
    if not source_file.exists():
        return
    content = source_file.read_text(encoding="utf-8")
    
    for term in FORBIDDEN_SEMANTIC_TERMS:
        pattern = r'\b' + term + r'\b'
        assert not re.search(pattern, content, re.IGNORECASE), f"Forbidden semantic term '{term}' found in source code of {source_file.name}!"

def test_anti_semantic_leakage_in_docstrings() -> None:
    for cls in [PrimitiveEvidenceCandidate, LeftMarginPrimitiveCandidate, XAlignedPrimitiveClusterCandidate]:
        doc = inspect.getdoc(cls) or ""
        for term in FORBIDDEN_SEMANTIC_TERMS:
            pattern = r'\b' + term + r'\b'
            assert not re.search(pattern, doc, re.IGNORECASE), f"Forbidden semantic term '{term}' found in docstring of {cls.__name__}!"
