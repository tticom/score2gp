import pytest
from unittest.mock import Mock
from score2gp.pdf_staff_notation_diagnostics import _extract_whole_note_candidates
from score2gp.pdf_staff_geometry import WholeNoteCandidateDiagnostics

def test_extract_whole_note_candidates_font_glyph_success():
    # Mock a PyMuPDF Page
    page_mock = Mock()
    page_mock.get_drawings.return_value = []
    
    # Mock rawdict
    page_mock.get_text.return_value = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {
                                "font": "Emmentaler-20",
                                "chars": [
                                    {
                                        "c": chr(0x15),
                                        "bbox": [10.0, 20.0, 20.0, 60.0],
                                        "origin": [15.0, 40.0]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    candidates = _extract_whole_note_candidates(page_mock)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.glyph_ordinal == 0x15
    assert c.font_name == "Emmentaler-20"
    assert c.origin_x == 15.0
    assert c.origin_y == 40.0
    assert c.width == 10.0
    assert c.height == 40.0
    assert c.source_method == "font_glyph_extraction"

def test_extract_whole_note_candidates_font_glyph_wrong_glyph():
    page_mock = Mock()
    page_mock.get_drawings.return_value = []
    page_mock.get_text.return_value = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {
                                "font": "Emmentaler-20",
                                "chars": [
                                    {
                                        "c": chr(0x16), # Not 0x15
                                        "bbox": [10.0, 20.0, 20.0, 60.0],
                                        "origin": [15.0, 40.0]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    candidates = _extract_whole_note_candidates(page_mock)
    assert len(candidates) == 0

def test_extract_whole_note_candidates_font_glyph_missing_fields_safe():
    page_mock = Mock()
    page_mock.get_drawings.return_value = []
    page_mock.get_text.return_value = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {
                                "font": "Emmentaler-20",
                                "chars": [
                                    {
                                        "c": chr(0x15),
                                        # Missing bbox and origin
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    candidates = _extract_whole_note_candidates(page_mock)
    assert len(candidates) == 0

def test_extract_whole_note_candidates_font_glyph_wrong_font():
    page_mock = Mock()
    page_mock.get_drawings.return_value = []
    page_mock.get_text.return_value = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {
                                "font": "Arial", # Not Emmentaler or feta
                                "chars": [
                                    {
                                        "c": chr(0x15),
                                        "bbox": [10.0, 20.0, 20.0, 60.0],
                                        "origin": [15.0, 40.0]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    candidates = _extract_whole_note_candidates(page_mock)
    assert len(candidates) == 0
