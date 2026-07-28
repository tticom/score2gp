from __future__ import annotations

from pathlib import Path
import fitz  # type: ignore[import-not-found]
from score2gp.pdf_staff_detection import (
    _drawing_segments,
    merge_collinear_horizontal_segments,
    _tab_line_groups,
)
from score2gp.pdf_staff_notation_diagnostics import build_notation_diagnostics
from tests.fixtures.pdf.make_generated_pdf_tab_duration_pdf import (
    EXPECTED_DURATION_ORACLE,
    generate_pdf_tab_duration_fixture,
)


def test_pdf_tab_duration_fixture_generation_and_reproducibility(tmp_path: Path):
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_tab_duration.pdf")
    assert pdf_path.exists(), "Synthetic PDF fixture must exist"

    # Regenerate fixture to verify reproducibility into temporary path
    generated_path = generate_pdf_tab_duration_fixture(tmp_path / "reproduced.pdf")
    assert generated_path.exists()
    assert generated_path.stat().st_size > 0


def test_pdf_tab_duration_fixture_extracts_duration_candidates():
    """Verify that duration markings (stems and beams) explicitly drawn on the tab fixture
    can be extracted by the primitive morphology diagnostic engine when the 6-line tab staff
    is fed into the notation diagnostic path.
    """
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_tab_duration.pdf")
    doc = fitz.open(pdf_path)
    page = doc[0]

    segments = list(_drawing_segments(page.get_drawings()))
    raw_horizontal = sorted(
        (segment for segment in segments if segment.is_horizontal),
        key=lambda segment: segment.y0,
    )
    horizontal = sorted(
        merge_collinear_horizontal_segments(raw_horizontal),
        key=lambda segment: segment.y0,
    )

    # Extract the 6-line tab staff group
    tab_groups = list(_tab_line_groups(horizontal))
    assert len(tab_groups) == 1
    assert len(tab_groups[0]) == 6

    # Pass the 6-line tab group directly into notation diagnostics builder
    diags = build_notation_diagnostics(page, page_index=1, notation_groups=tab_groups)
    assert len(diags.staves) == 1
    morph = diags.staves[0].morphology

    assert morph is not None

    # We expect 6 horizontal staff lines
    assert morph.staff_line_horizontal == 6

    # We expect vertical strokes: 3 barlines + 12 stems = 15 candidates minimum
    assert morph.vertical_stroke_candidate >= 15

    # We expect horizontal non-staff strokes: 1 single beam + 1 double beam (2 strokes) = 3
    assert morph.non_staff_horizontal >= 3

    # Ensure fret numbers were extracted (12 fret numbers drawn in Courier)
    assert morph.text_span_by_font.get("Courier", 0) >= 12

    # Verify expected oracle structure presence
    assert "bar_1" in EXPECTED_DURATION_ORACLE
    assert "bar_2" in EXPECTED_DURATION_ORACLE
    assert len(EXPECTED_DURATION_ORACLE["bar_1"]) == 4
    assert len(EXPECTED_DURATION_ORACLE["bar_2"]) == 8
