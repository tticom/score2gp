"""Segmented TAB lines must be recovered without assigning an off-line digit."""

from pathlib import Path
from tempfile import TemporaryDirectory
import pymupdf

from score2gp.pdf import _detect_tab_systems, extract_tab


FIXTURES = Path(__file__).parent / "fixtures" / "pdf" / "dur_03"


def _work_dir() -> Path:
    work = Path(__file__).resolve().parents[1] / "work"
    work.mkdir(parents=True, exist_ok=True)
    return work


def test_segmented_top_three_lines_recover_six_strings() -> None:
    pdf = FIXTURES / "segmented_top_three.pdf"
    with pymupdf.open(pdf) as document:
        systems = _detect_tab_systems(document[0], 1)
    assert len(systems) == 1
    assert len(systems[0].line_ys) == 6
    assert [round(y) for y in systems[0].line_ys] == [100, 106, 112, 118, 124, 130]
    for y, expected in ((100, 1), (106, 2), (112, 3)):
        assert systems[0].string_for_y(y)[0] == expected
    with TemporaryDirectory(dir=_work_dir()) as directory:
        raw = extract_tab(pdf, directory)
    assert [(c["raw_text"], c.get("string"), c.get("bar_index"))
            for c in sorted(raw["candidates"], key=lambda item: item["bbox"]["x0"])] == [
        ("3", 1, 1), ("5", 2, 1), ("7", 3, 1), ("8", 1, 1),
        ("10", 2, 1), ("12", 3, 1), ("15", 1, 1),
    ]


def test_digit_between_recovered_lines_is_refused() -> None:
    pdf = FIXTURES / "digit_between_lines.pdf"
    with pymupdf.open(pdf) as document:
        systems = _detect_tab_systems(document[0], 1)
    assert len(systems) == 1
    assert systems[0].string_for_y(103)[0] is None
    assert "pdf_string_assignment_between_lines" in systems[0].string_for_y(103)[3]
    with TemporaryDirectory(dir=_work_dir()) as directory:
        raw = extract_tab(pdf, directory)
    first = next(c for c in raw["candidates"] if c["raw_text"] == "3")
    assert first.get("string") is None
    assert "pdf_string_assignment_between_lines" in first["raw"]["assignment_warnings"]


def test_two_intact_lines_cannot_recover_staff() -> None:
    with pymupdf.open(FIXTURES / "only_two_intact_lines.pdf") as document:
        assert _detect_tab_systems(document[0], 1) == []


def _digits(pdf: Path) -> list[tuple[str, int | None, int | None]]:
    with TemporaryDirectory(dir=_work_dir()) as directory:
        raw = extract_tab(pdf, directory)
    return [(c["raw_text"], c.get("string"), c.get("bar_index"))
            for c in sorted(raw["candidates"], key=lambda item: item["bbox"]["x0"])
            if c["raw_text"].isdigit()]


def test_final_bar_narrower_than_the_line_filter_belongs_to_the_staff() -> None:
    pdf = FIXTURES / "narrow_final_bar.pdf"
    with pymupdf.open(pdf) as document:
        systems = _detect_tab_systems(document[0], 1)
    assert len(systems) == 1
    assert (systems[0].x0, systems[0].x1, systems[0].barlines) == (30.0, 540.0, [30.0, 300.0, 470.0, 540.0])
    assert not systems[0].segmented_lines_recovered
    assert _digits(pdf) == [("3", 1, 1), ("5", 2, 1), ("7", 3, 1), ("8", 1, 2),
                            ("10", 4, 2), ("7", 2, 3)]


def test_final_bar_with_two_drawn_lines_does_not_extend_the_staff() -> None:
    pdf = FIXTURES / "narrow_final_bar_two_lines.pdf"
    with pymupdf.open(pdf) as document:
        systems = _detect_tab_systems(document[0], 1)
    assert len(systems) == 1
    assert (systems[0].x1, systems[0].barlines) == (470.0, [30.0, 300.0, 470.0])
    assert _digits(pdf) == [("3", 1, 1), ("5", 2, 1), ("7", 3, 1), ("8", 1, 2),
                            ("10", 4, 2), ("7", 2, None)]


def test_final_bar_with_only_two_intact_lines_does_not_extend_the_staff() -> None:
    pdf = FIXTURES / "narrow_final_bar_two_intact_lines.pdf"
    with pymupdf.open(pdf) as document:
        systems = _detect_tab_systems(document[0], 1)
    assert len(systems) == 1
    assert (systems[0].x1, systems[0].barlines) == (470.0, [30.0, 300.0, 470.0])
    assert _digits(pdf) == [("3", 1, 1), ("5", 2, 1), ("7", 3, 1), ("8", 1, 2),
                            ("10", 4, 2), ("7", 3, None)]


def test_alternate_lines_of_two_staves_are_not_a_tab_staff() -> None:
    with pymupdf.open(FIXTURES / "alternate_lines_of_two_staves.pdf") as document:
        systems = _detect_tab_systems(document[0], 1)
    assert [(round(system.line_ys[0], 1), len(system.line_ys)) for system in systems] == [(238.4, 6)]
