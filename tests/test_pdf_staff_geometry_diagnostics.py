from __future__ import annotations
import json
from typing import Any
import pytest
from score2gp.pdf import _LineSegment
from score2gp.pdf_staff_geometry import (
    NotationStaffGeometry,
    LocalPrimitivesSummary,
    NotationStaffDiagnostics,
    PdfStaffNotationGeometryDiagnostics
)
from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics

def test_build_notation_diagnostics_mock() -> None:
    group = [
        _LineSegment(50.0, 100.0, 500.0, 100.0),
        _LineSegment(50.0, 108.0, 500.0, 108.0),
        _LineSegment(50.0, 116.0, 500.0, 116.0),
        _LineSegment(50.0, 124.0, 500.0, 124.0),
        _LineSegment(50.0, 132.0, 500.0, 132.0),
    ]

    class MockPoint:
        def __init__(self, x: float, y: float) -> None:
            self.x = x
            self.y = y

    drawings = [
        {
            "rect": (100.0, 100.0, 200.0, 130.0),
            "items": [
                ("l", MockPoint(100.0, 100.0), MockPoint(200.0, 130.0))
            ]
        },
        {
            "rect": (150.0, 110.0, 250.0, 120.0),
            "items": [
                ("c", MockPoint(150.0, 110.0), MockPoint(180.0, 115.0), MockPoint(220.0, 115.0), MockPoint(250.0, 120.0))
            ]
        },
        {
            "rect": (300.0, 105.0, 310.0, 125.0),
            "items": [
                ("re",)
            ]
        },
        {
            "rect": (100.0, 400.0, 200.0, 430.0),
            "items": [
                ("l", MockPoint(100.0, 400.0), MockPoint(200.0, 430.0))
            ]
        }
    ]

    text_dict = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {
                                "text": " trebleClef ",
                                "bbox": (60.0, 95.0, 80.0, 115.0),
                                "font": "GPBravuraRegular"
                            },
                            {
                                "text": " 4 ",
                                "bbox": (110.0, 105.0, 120.0, 115.0),
                                "font": "Times-Roman"
                            },
                            {
                                "text": " Page 1 ",
                                "bbox": (100.0, 500.0, 150.0, 510.0),
                                "font": "Times-Roman"
                            },
                            {
                                "text": "   ",
                                "bbox": (70.0, 100.0, 90.0, 120.0),
                                "font": "GPBravuraRegular"
                            }
                        ]
                    }
                ]
            }
        ]
    }

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return drawings
        def get_text(self, kind: str) -> dict | list:
            if kind == "dict":
                return text_dict
            return []

    page = MockPage()
    notation_diags = build_notation_diagnostics(page, page_index=1, notation_groups=[group])

    assert len(notation_diags.staves) == 1
    diag = notation_diags.staves[0]

    assert diag.staff.page_index == 1
    assert diag.staff.system_index == 1
    assert diag.staff.staff_index == 1
    assert diag.staff.x0 == 50.0
    assert diag.staff.y0 == 100.0
    assert diag.staff.x1 == 500.0
    assert diag.staff.y1 == 132.0
    assert diag.staff.line_y_coords == [100.0, 108.0, 116.0, 124.0, 132.0]

    assert diag.primitives.line_count == 1
    assert diag.primitives.curve_count == 1
    assert diag.primitives.rect_count == 1

    assert diag.primitives.text_span_count_by_font == {
        "GPBravuraRegular": 1,
        "Times-Roman": 1
    }


def test_diagnostics_private_safety_serialization() -> None:
    group = [
        _LineSegment(50.0, 100.0, 500.0, 100.0),
        _LineSegment(50.0, 108.0, 500.0, 108.0),
        _LineSegment(50.0, 116.0, 500.0, 116.0),
        _LineSegment(50.0, 124.0, 500.0, 124.0),
        _LineSegment(50.0, 132.0, 500.0, 132.0),
    ]

    class MockPoint:
        def __init__(self, x: float, y: float) -> None:
            self.x = x
            self.y = y

    # Drawing with unique coordinates (999.123, 888.456)
    drawings = [
        {
            "rect": (100.0, 100.0, 200.0, 130.0),
            "items": [
                ("l", MockPoint(999.123, 888.456), MockPoint(200.0, 130.0))
            ]
        }
    ]

    # Text spans with PUA characters, sensitive text, and unique coordinate
    text_dict = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            {
                                "text": "SECRET_LYRICS_DO_NOT_LEAK",
                                "bbox": (60.0, 95.0, 80.0, 115.0),
                                "font": "GPBravuraRegular"
                            },
                            {
                                "text": "\ue002\uf003", # PUA characters
                                "bbox": (110.0, 105.0, 120.0, 115.0),
                                "font": "Times-Roman"
                            }
                        ]
                    }
                ]
            }
        ]
    }

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return drawings
        def get_text(self, kind: str) -> dict | list:
            if kind == "dict":
                return text_dict
            return []

    page = MockPage()
    notation_diags = build_notation_diagnostics(page, page_index=1, notation_groups=[group])

    # Dump using Pydantic serialization
    serialized = notation_diags.model_dump() if hasattr(notation_diags, "model_dump") else notation_diags.dict()
    json_str = json.dumps(serialized)

    # Assert no sensitive text appears
    assert "SECRET_LYRICS_DO_NOT_LEAK" not in json_str
    assert "SECRET_LYRICS" not in json_str

    # Assert no PUA character appears (\ue002 or \uf003)
    assert "\ue002" not in json_str
    assert "\uf003" not in json_str

    # Search for PUA code points generally: 0xE000-0xF8FF and 0xF0000-0x10FFFF
    for char in json_str:
        val = ord(char)
        is_pua = (0xE000 <= val <= 0xF8FF) or (0xF0000 <= val <= 0xFFFFD) or (0x100000 <= val <= 0x10FFFD)
        assert not is_pua, f"Found PUA character: {char!r}"

    # Assert no individual drawing item coordinates (like 999.123 or 888.456) appear
    assert "999.123" not in json_str
    assert "888.456" not in json_str


def test_diagnostics_out_of_zone_filtering() -> None:
    group = [
        _LineSegment(100.0, 100.0, 200.0, 100.0),
        _LineSegment(100.0, 108.0, 200.0, 108.0),
        _LineSegment(100.0, 116.0, 200.0, 116.0),
        _LineSegment(100.0, 124.0, 200.0, 124.0),
        _LineSegment(100.0, 132.0, 200.0, 132.0),
    ]
    # x0 = 100.0, x1 = 200.0
    # y0 = 100.0, y1 = 132.0
    # y0_padded = 80.0, y1_padded = 152.0

    class MockPoint:
        def __init__(self, x: float, y: float) -> None:
            self.x = x
            self.y = y

    drawings = [
        # Inside
        {
            "rect": (120.0, 90.0, 180.0, 120.0),
            "items": [("l", MockPoint(120.0, 90.0), MockPoint(180.0, 120.0))]
        },
        # Above y0_padded (y1 <= 80.0)
        {
            "rect": (120.0, 50.0, 180.0, 80.0),
            "items": [("l", MockPoint(120.0, 50.0), MockPoint(180.0, 80.0))]
        },
        # Below y1_padded (y0 >= 152.0)
        {
            "rect": (120.0, 152.0, 180.0, 170.0),
            "items": [("l", MockPoint(120.0, 152.0), MockPoint(180.0, 170.0))]
        },
        # Left of x0 (x1 < 100.0)
        {
            "rect": (50.0, 90.0, 99.0, 120.0),
            "items": [("l", MockPoint(50.0, 90.0), MockPoint(99.0, 120.0))]
        },
        # Right of x1 (x0 > 200.0)
        {
            "rect": (201.0, 90.0, 250.0, 120.0),
            "items": [("l", MockPoint(201.0, 90.0), MockPoint(250.0, 120.0))]
        }
    ]

    text_dict = {
        "blocks": [
            {
                "lines": [
                    {
                        "spans": [
                            # Inside
                            {
                                "text": "inside",
                                "bbox": (120.0, 90.0, 180.0, 120.0),
                                "font": "InsideFont"
                            },
                            # Outside Above
                            {
                                "text": "above",
                                "bbox": (120.0, 50.0, 180.0, 80.0),
                                "font": "AboveFont"
                            },
                            # Outside Below
                            {
                                "text": "below",
                                "bbox": (120.0, 152.0, 180.0, 170.0),
                                "font": "BelowFont"
                            },
                            # Outside Left
                            {
                                "text": "left",
                                "bbox": (50.0, 90.0, 99.0, 120.0),
                                "font": "LeftFont"
                            },
                            # Outside Right
                            {
                                "text": "right",
                                "bbox": (201.0, 90.0, 250.0, 120.0),
                                "font": "RightFont"
                            },
                            # Empty / Whitespace (Inside)
                            {
                                "text": "   ",
                                "bbox": (120.0, 90.0, 180.0, 120.0),
                                "font": "WhitespaceFont"
                            }
                        ]
                    }
                ]
            }
        ]
    }

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return drawings
        def get_text(self, kind: str) -> dict | list:
            if kind == "dict":
                return text_dict
            return []

    page = MockPage()
    notation_diags = build_notation_diagnostics(page, page_index=1, notation_groups=[group])

    diag = notation_diags.staves[0]
    # Out of the 5 drawings, only the first one is inside (1 line)
    assert diag.primitives.line_count == 1
    # Out of the 6 text spans, only the first one is inside and non-empty (InsideFont)
    assert diag.primitives.text_span_count_by_font == {"InsideFont": 1}


def test_diagnostics_shape_and_staff_index() -> None:
    # Multiple groups representing multiple staff systems on the page
    group1 = [
        _LineSegment(50.0, 100.0, 500.0, 100.0),
        _LineSegment(50.0, 108.0, 500.0, 108.0),
        _LineSegment(50.0, 116.0, 500.0, 116.0),
        _LineSegment(50.0, 124.0, 500.0, 124.0),
        _LineSegment(50.0, 132.0, 500.0, 132.0),
    ]
    group2 = [
        _LineSegment(50.0, 300.0, 500.0, 300.0),
        _LineSegment(50.0, 308.0, 500.0, 308.0),
        _LineSegment(50.0, 316.0, 500.0, 316.0),
        _LineSegment(50.0, 324.0, 500.0, 324.0),
        _LineSegment(50.0, 332.0, 500.0, 332.0),
    ]

    class MockPage:
        def get_drawings(self) -> list[dict]:
            return []
        def get_text(self, kind: str) -> dict | list:
            return {}

    page = MockPage()
    notation_diags = build_notation_diagnostics(page, page_index=1, notation_groups=[group1, group2])

    assert len(notation_diags.staves) == 2

    # Assert shape and staff_index
    for idx, diag in enumerate(notation_diags.staves, start=1):
        assert diag.staff.system_index == idx
        assert diag.staff.staff_index == 1 # Must be 1
        assert diag.staff.page_index == 1

        # Structure check
        assert hasattr(diag, "staff")
        assert hasattr(diag, "primitives")
        assert isinstance(diag.primitives.text_span_count_by_font, dict)
        for font, count in diag.primitives.text_span_count_by_font.items():
            assert isinstance(font, str)
            assert isinstance(count, int)


def test_inspect_pdf_integration_boundary(monkeypatch, tmp_path) -> None:
    import fitz
    from score2gp.pdf import inspect_pdf, _LineSegment

    group = [
        _LineSegment(50.0, 100.0, 500.0, 100.0),
        _LineSegment(50.0, 108.0, 500.0, 108.0),
        _LineSegment(50.0, 116.0, 500.0, 116.0),
        _LineSegment(50.0, 124.0, 500.0, 124.0),
        _LineSegment(50.0, 132.0, 500.0, 132.0),
    ]

    monkeypatch.setattr("score2gp.pdf._detect_notation_staff_groups", lambda page: [group])

    # Mock page class
    class MockRect:
        width = 600.0
        height = 800.0

    class MockPixmap:
        def save(self, path) -> None:
            # Create a dummy file so pix.save does not fail
            with open(path, "wb") as f:
                f.write(b"dummy png data")

    class MockPage:
        rect = MockRect()
        def get_text(self, kind: str) -> Any:
            if kind == "blocks":
                return [(60.0, 95.0, 80.0, 115.0, "SECRET_LYRICS_DO_NOT_LEAK", 0, 0)]
            elif kind == "dict":
                return {
                    "blocks": [
                        {
                            "lines": [
                                {
                                    "spans": [
                                        {
                                            "text": "SECRET_LYRICS_DO_NOT_LEAK",
                                            "bbox": (60.0, 95.0, 80.0, 115.0),
                                            "font": "GPBravuraRegular"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            return []

        def get_drawings(self) -> list:
            return []

        def get_images(self, full: bool) -> list:
            return []

        def get_pixmap(self, matrix=None, alpha=False) -> MockPixmap:
            return MockPixmap()

    # Mock document context manager
    class MockDoc:
        page_count = 1
        def __init__(self, *args, **kwargs) -> None:
            pass
        def __enter__(self) -> MockDoc:
            return self
        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            pass
        def __iter__(self) -> Any:
            yield MockPage()

    monkeypatch.setattr(fitz, "open", MockDoc)

    # We need a dummy input PDF path and temporary output directory
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_text("dummy pdf content")
    out_dir = tmp_path / "out"

    result = inspect_pdf(dummy_pdf, out_dir)

    # Assert result structure
    assert "pages" in result
    assert len(result["pages"]) == 1
    page_info = result["pages"][0]

    assert "pdf_staff_notation_diagnostics" in page_info
    diags = page_info["pdf_staff_notation_diagnostics"]

    # Verify shape
    assert "staves" in diags
    assert len(diags["staves"]) == 1

    # Convert to JSON string to ensure privacy invariants hold at inspect_pdf boundary
    json_str = json.dumps(diags)
    assert "SECRET_LYRICS_DO_NOT_LEAK" not in json_str
    assert "SECRET_LYRICS" not in json_str


def test_silent_exception_handling_behavior(monkeypatch, tmp_path) -> None:
    import fitz
    from score2gp.pdf import inspect_pdf, _LineSegment

    group = [
        _LineSegment(50.0, 100.0, 500.0, 100.0),
        _LineSegment(50.0, 108.0, 500.0, 108.0),
        _LineSegment(50.0, 116.0, 500.0, 116.0),
        _LineSegment(50.0, 124.0, 500.0, 124.0),
        _LineSegment(50.0, 132.0, 500.0, 132.0),
    ]

    monkeypatch.setattr("score2gp.pdf._detect_notation_staff_groups", lambda page: [group])

    # Make build_notation_diagnostics fail
    def failing_build_diagnostics(*args, **kwargs):
        raise ValueError("Simulated sensitive details: /user/local/secret_path and secret_note_content")

    monkeypatch.setattr("score2gp.pdf_staff_notation_diagnostics.build_notation_diagnostics", failing_build_diagnostics)

    # Mock page class
    class MockRect:
        width = 600.0
        height = 800.0

    class MockPixmap:
        def save(self, path) -> None:
            with open(path, "wb") as f:
                f.write(b"dummy png data")

    class MockPage:
        rect = MockRect()
        def get_text(self, kind: str) -> Any:
            return []
        def get_drawings(self) -> list:
            return []
        def get_images(self, full: bool) -> list:
            return []
        def get_pixmap(self, matrix=None, alpha=False) -> MockPixmap:
            return MockPixmap()

    # Mock document context manager
    class MockDoc:
        page_count = 1
        def __init__(self, *args, **kwargs) -> None:
            pass
        def __enter__(self) -> MockDoc:
            return self
        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            pass
        def __iter__(self) -> Any:
            yield MockPage()

    monkeypatch.setattr(fitz, "open", MockDoc)

    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_text("dummy pdf content")
    out_dir = tmp_path / "out"

    result = inspect_pdf(dummy_pdf, out_dir)

    # Ensure diagnostics returns the private-safe status, and has no raw exception details or paths
    page_info = result["pages"][0]
    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags == {"staves": [], "status": "pdf_notation_geometry_diagnostics_failed"}

    # Verify that no raw error details are leaked in the serialization dict
    json_str = json.dumps(diags)
    assert "ValueError" not in json_str
    assert "sensitive" not in json_str
    assert "secret" not in json_str
    assert "local" not in json_str


def test_detect_notation_staff_groups_exception_handling(monkeypatch, tmp_path) -> None:
    import fitz
    from score2gp.pdf import inspect_pdf

    # Make _detect_notation_staff_groups raise an exception
    def failing_detect_notation_staff_groups(*args, **kwargs):
        raise RuntimeError("Failing drawing retrieval with sensitive path /tmp/leak")

    monkeypatch.setattr("score2gp.pdf._detect_notation_staff_groups", failing_detect_notation_staff_groups)

    # Mock page class
    class MockRect:
        width = 600.0
        height = 800.0

    class MockPixmap:
        def save(self, path) -> None:
            with open(path, "wb") as f:
                f.write(b"dummy png data")

    class MockPage:
        rect = MockRect()
        def get_text(self, kind: str) -> Any:
            return []
        def get_drawings(self) -> list:
            return []
        def get_images(self, full: bool) -> list:
            return []
        def get_pixmap(self, matrix=None, alpha=False) -> MockPixmap:
            return MockPixmap()

    # Mock document context manager
    class MockDoc:
        page_count = 1
        def __init__(self, *args, **kwargs) -> None:
            pass
        def __enter__(self) -> MockDoc:
            return self
        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            pass
        def __iter__(self) -> Any:
            yield MockPage()

    monkeypatch.setattr(fitz, "open", MockDoc)

    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_text("dummy pdf content")
    out_dir = tmp_path / "out"

    # When run through inspect_pdf, the exception from _detect_notation_staff_groups should propagate
    # to inspect_pdf and be handled as pdf_notation_geometry_diagnostics_failed status
    result = inspect_pdf(dummy_pdf, out_dir)

    page_info = result["pages"][0]
    diags = page_info["pdf_staff_notation_diagnostics"]
    assert diags == {"staves": [], "status": "pdf_notation_geometry_diagnostics_failed"}

    # Ensure no details of the exception leak
    json_str = json.dumps(diags)
    assert "RuntimeError" not in json_str
    assert "Failing" not in json_str
    assert "leak" not in json_str
