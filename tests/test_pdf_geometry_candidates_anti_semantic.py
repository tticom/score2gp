import pytest
from pydantic import BaseModel
import inspect
import score2gp.pdf_geometry_candidates as candidates_module

def test_no_semantic_terms_in_geometry_models() -> None:
    forbidden_terms = ["notehead", "stem", "clef", "pitch", "duration", "voice", "chord", "key_signature", "time_signature", "beat", "rhythm"]
    
    # Iterate over all members of the module
    for name, obj in inspect.getmembers(candidates_module):
        if inspect.isclass(obj) and issubclass(obj, BaseModel):
            # Check class name
            for term in forbidden_terms:
                assert term not in name.lower(), f"Forbidden semantic term '{term}' found in class name: {name}"
            
            # Check fields
            for field_name in obj.model_fields.keys():
                for term in forbidden_terms:
                    assert term not in field_name.lower(), f"Forbidden semantic term '{term}' found in field '{field_name}' of class '{name}'"
