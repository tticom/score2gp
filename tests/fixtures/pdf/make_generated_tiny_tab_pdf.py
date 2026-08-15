from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-not-found]


def main() -> None:
    out = Path(__file__).with_name("generated_tiny_tab.pdf")
    doc = fitz.open()
    page = doc.new_page(width=420, height=320)

    x0 = 72
    x1 = 332
    line_ys = [120, 134, 148, 162, 176, 190]
    bar_xs = [88, 205, 322]

    page.insert_text((72, 78), "Generated Tiny Tab", fontsize=12, fontname="helv")
    page.insert_text((100, 102), "E", fontsize=9, fontname="helv")
    page.insert_text((235, 102), "vib", fontsize=8, fontname="helv")

    for y in line_ys:
        page.draw_line((x0, y), (x1, y), color=(0, 0, 0), width=0.6)
    for x in bar_xs:
        page.draw_line((x, line_ys[0]), (x, line_ys[-1]), color=(0, 0, 0), width=0.6)

    numbers = [
        ("0", 120, line_ys[0]),
        ("1", 148, line_ys[1]),
        ("12", 176, line_ys[0]),
        ("2", 232, line_ys[2]),
        ("3", 260, line_ys[0]),
        ("3", 288, line_ys[1]),
    ]
    for text, x, y in numbers:
        page.insert_text((x, y + 3), text, fontsize=10, fontname="cour")

    doc.save(out, garbage=4, deflate=True)
    doc.close()


if __name__ == "__main__":
    main()
