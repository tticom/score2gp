from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-not-found]


OUT_DIR = Path(__file__).parent


def _new_page(title: str) -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=620, height=360)
    page.insert_text((72, 64), title, fontsize=12, fontname="helv")
    return doc, page


def _write_lines(page: fitz.Page, lines: list[str], *, x: float = 72, y: float = 104, line_gap: float = 14) -> None:
    for index, line in enumerate(lines):
        page.insert_text((x, y + index * line_gap), line, fontsize=10, fontname="cour")


def _save(doc: fitz.Document, name: str) -> None:
    doc.save(OUT_DIR / name, garbage=4, deflate=True)
    doc.close()


def make_simple_ascii_tab() -> None:
    doc, page = _new_page("Generated ASCII Tab Simple")
    _write_lines(
        page,
        [
            "e|--0-----3-------|",
            "B|-----1-----3----|",
            "G|--0-------------|",
            "D|--------2-------|",
            "A|----------------|",
            "E|----------------|",
        ],
    )
    _save(doc, "generated_ascii_tab_simple.pdf")


def make_technique_ascii_tab() -> None:
    doc, page = _new_page("Generated ASCII Tab Techniques")
    page.insert_text((72, 88), "Legend: slash, bend, release, hammer, pull, vibrato", fontsize=9, fontname="helv")
    _write_lines(
        page,
        [
            "e|--3/5-------7\\5--------|",
            "B|-------2h4-------5p3---|",
            "G|--7b8r7------------9v--|",
            "D|-----------------------|",
            "A|-----------------------|",
            "E|-----------------------|",
        ],
        y=122,
    )
    _save(doc, "generated_ascii_tab_techniques.pdf")


def make_malformed_ascii_tab() -> None:
    doc, page = _new_page("Generated ASCII Tab Malformed")
    _write_lines(
        page,
        [
            "e|--0-----2-------|",
            "B|-----1-----3----|",
            "G|--0-------------|",
            "D|--------2-------|",
            "A|----------------|",
        ],
    )
    _save(doc, "generated_ascii_tab_malformed.pdf")


def make_barred_ascii_tab() -> None:
    doc, page = _new_page("Generated ASCII Tab Barred")
    _write_lines(
        page,
        [
            "e|--0--1--2--|--3--4--5--|",
            "B|-----------|-----------|",
            "G|--0--------|-----2-----|",
            "D|-----------|-----------|",
            "A|-----------|-----------|",
            "E|-----------|-----------|",
        ],
    )
    _save(doc, "generated_ascii_tab_barred.pdf")


def make_scoreir_gate_ascii_tab() -> None:
    doc, page = _new_page("Generated ASCII Tab ScoreIR Gate")
    _write_lines(
        page,
        [
            "e|--0--1--2--|--3--------|",
            "B|-----------|-----------|",
            "G|-----------|-----------|",
            "D|-----------|-----------|",
            "A|-----------|-----------|",
            "E|-----------|-----------|",
        ],
    )
    _save(doc, "generated_ascii_tab_scoreir_gate.pdf")


def make_equal_width_ascii_tab() -> None:
    doc, page = _new_page("Generated ASCII Tab Equal Width")
    page.insert_text((72, 88), "count: 1 & 2 & 3 & 4 & | 1 & 2 & 3 & 4 &", fontsize=9, fontname="cour")
    _write_lines(
        page,
        [
            "e|--0---1---2---3---|--4---5---6---7---|",
            "B|------------------|------------------|",
            "G|--0-------2-------|--4-------6-------|",
            "D|------------------|------------------|",
            "A|------------------|------------------|",
            "E|------------------|------------------|",
        ],
        y=122,
    )
    _save(doc, "generated_ascii_tab_equal_width.pdf")


def make_uneven_timing_ascii_tab() -> None:
    doc, page = _new_page("Generated ASCII Tab Uneven Timing")
    _write_lines(
        page,
        [
            "e|--0-1-------|--2---3-|",
            "B|------------|--------|",
            "G|--0---------|------2-|",
            "D|------------|--------|",
            "A|------------|--------|",
            "E|------------|--------|",
        ],
    )
    _save(doc, "generated_ascii_tab_uneven_timing.pdf")


def make_no_bar_ascii_tab() -> None:
    doc, page = _new_page("Generated ASCII Tab No Bars")
    _write_lines(
        page,
        [
            "e|--0--1--2--3--",
            "B|--------------",
            "G|--0-----2-----",
            "D|--------------",
            "A|--------------",
            "E|--------------",
        ],
    )
    _save(doc, "generated_ascii_tab_no_bars.pdf")


def main() -> None:
    make_simple_ascii_tab()
    make_technique_ascii_tab()
    make_malformed_ascii_tab()
    make_barred_ascii_tab()
    make_scoreir_gate_ascii_tab()
    make_equal_width_ascii_tab()
    make_uneven_timing_ascii_tab()
    make_no_bar_ascii_tab()


if __name__ == "__main__":
    main()
