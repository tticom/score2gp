from __future__ import annotations

from pathlib import Path
import fitz  # type: ignore[import-not-found]


def main() -> None:
    out = Path(__file__).with_name("generated_pdf_vertical_overlap_resolved.pdf")
    doc = fitz.open()
    page = doc.new_page(width=420, height=320)

    page.insert_text((50, 40), "Generated Vertical Overlap Resolved", fontsize=12, fontname="helv")

    # Column 1: x_range = [50, 190]
    # System 1: y_range = [100, 150] (spacing = 10)
    line_ys1 = [100, 110, 120, 130, 140, 150]
    bar_xs1 = [60, 120, 180]
    for y in line_ys1:
        page.draw_line((50, y), (190, y), color=(0, 0, 0), width=0.6)
    for x in bar_xs1:
        page.draw_line((x, line_ys1[0]), (x, line_ys1[-1]), color=(0, 0, 0), width=0.6)
    page.insert_text((90, line_ys1[0] + 3), "3", fontsize=10, fontname="cour")

    # System 2: y_range = [200, 250] (spacing = 10)
    line_ys2 = [200, 210, 220, 230, 240, 250]
    bar_xs2 = [60, 120, 180]
    for y in line_ys2:
        page.draw_line((50, y), (190, y), color=(0, 0, 0), width=0.6)
    for x in bar_xs2:
        page.draw_line((x, line_ys2[0]), (x, line_ys2[-1]), color=(0, 0, 0), width=0.6)
    page.insert_text((90, line_ys2[0] + 3), "5", fontsize=10, fontname="cour")

    # Column 2: x_range = [210, 350]
    # System 3: y_range = [120, 170] (spacing = 10)
    # Note that System 3's Y-range [120, 170] vertically overlaps with System 1's Y-range [100, 150]
    line_ys3 = [120, 130, 140, 150, 160, 170]
    bar_xs3 = [220, 280, 340]
    for y in line_ys3:
        page.draw_line((210, y), (350, y), color=(0, 0, 0), width=0.6)
    for x in bar_xs3:
        page.draw_line((x, line_ys3[0]), (x, line_ys3[-1]), color=(0, 0, 0), width=0.6)
    page.insert_text((250, line_ys3[0] + 3), "2", fontsize=10, fontname="cour")

    # System 4: y_range = [220, 270] (spacing = 10)
    # Note that System 4's Y-range [220, 270] vertically overlaps with System 2's Y-range [200, 250]
    line_ys4 = [220, 230, 240, 250, 260, 270]
    bar_xs4 = [220, 280, 340]
    for y in line_ys4:
        page.draw_line((210, y), (350, y), color=(0, 0, 0), width=0.6)
    for x in bar_xs4:
        page.draw_line((x, line_ys4[0]), (x, line_ys4[-1]), color=(0, 0, 0), width=0.6)
    page.insert_text((250, line_ys4[0] + 3), "7", fontsize=10, fontname="cour")

    doc.save(out, garbage=4, deflate=True)
    doc.close()


if __name__ == "__main__":
    main()
