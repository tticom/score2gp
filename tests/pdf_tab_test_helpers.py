from __future__ import annotations

from score2gp.ir import BoundingBox
from score2gp.tabraw import TabCandidate


def make_pdf_tab_candidate(
    id: str = "c-1",
    kind: str = "fret",
    raw_text: str = "5",
    parsed_fret: int | None = 5,
    x: float = 10.0,
    y: float = 10.0,
    string: int = 1,
    bar_index: int = 1,
    system_index: int = 1,
    staff_index: int = 1,
    page_index: int = 1,
    bbox: BoundingBox | None = None,
    confidence: float = 0.5,
) -> TabCandidate:
    """Helper to build a fresh TabCandidate instance with sensible defaults for PDF-only tab testing."""
    if bbox is None:
        bbox = BoundingBox(
            page=page_index,
            x0=x,
            y0=y,
            x1=x + 5.0,
            y1=y + 5.0,
        )
    else:
        bbox = BoundingBox(
            page=bbox.page,
            x0=bbox.x0,
            y0=bbox.y0,
            x1=bbox.x1,
            y1=bbox.y1,
        )

    return TabCandidate(
        id=id,
        kind=kind,
        raw_text=raw_text,
        parsed_fret=parsed_fret,
        x=x,
        y=y,
        string=string,
        bar_index=bar_index,
        system_index=system_index,
        staff_index=staff_index,
        page_index=page_index,
        bbox=bbox,
        confidence=confidence,
    )


def make_pdf_quarter_rest_candidate(
    id: str = "c-rest",
    x: float = 10.0,
    y: float = 10.0,
    string: int = 1,
    bar_index: int = 1,
    system_index: int = 1,
    staff_index: int = 1,
    page_index: int = 1,
    bbox: BoundingBox | None = None,
    confidence: float = 0.95,
) -> TabCandidate:
    """Helper to build a fresh quarter rest TabCandidate instance."""
    return make_pdf_tab_candidate(
        id=id,
        kind="fret",
        raw_text="quarter_rest",
        parsed_fret=None,
        x=x,
        y=y,
        string=string,
        bar_index=bar_index,
        system_index=system_index,
        staff_index=staff_index,
        page_index=page_index,
        bbox=bbox,
        confidence=confidence,
    )
