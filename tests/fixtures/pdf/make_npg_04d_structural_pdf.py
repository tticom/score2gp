import fitz
from pathlib import Path

def main():
    doc = fitz.open()
    page = doc.new_page(width=800, height=800)

    # Draw standard staff (System 1)
    # y = 100 to 132 (line gap 8)
    not_y0 = 100
    for i in range(5):
        y = not_y0 + i * 8
        page.draw_line((50, y), (750, y), color=(0, 0, 0), width=0.5)

    # Draw TAB staff (System 1)
    tab_y0 = 160
    for i in range(6):
        y = tab_y0 + i * 10
        page.draw_line((50, y), (750, y), color=(0, 0, 0), width=0.5)

    # Connect them (bracket or barline)
    page.draw_line((50, not_y0), (50, tab_y0 + 50), color=(0, 0, 0), width=1.0)

    # Draw barlines for both
    for x in [750]:
        page.draw_line((x, not_y0), (x, not_y0 + 32), color=(0, 0, 0), width=0.5)
        page.draw_line((x, tab_y0), (x, tab_y0 + 50), color=(0, 0, 0), width=0.5)

    # Add a start repeat
    page.draw_rect(fitz.Rect(253.5, not_y0, 256.5, not_y0 + 32), color=(0, 0, 0), fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(258.0, not_y0, 258.5, not_y0 + 32), color=(0, 0, 0), fill=(0, 0, 0))

    # Add an end repeat
    page.draw_rect(fitz.Rect(491.5, not_y0, 492.0, not_y0 + 32), color=(0, 0, 0), fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(493.5, not_y0, 496.5, not_y0 + 32), color=(0, 0, 0), fill=(0, 0, 0))

    # Add an end repeat at x=500 (thin then thick)
    page.draw_line((492, not_y0), (492, not_y0 + 32), color=(0, 0, 0), width=0.5)
    page.draw_line((495, not_y0), (495, not_y0 + 32), color=(0, 0, 0), width=3.0)

    page.insert_text((250, 80), "Chorus", fontsize=12, fontname="hebo")
    page.insert_text((500, 80), "UnknownBold", fontsize=12, fontname="hebo")

    page.insert_text((150, tab_y0 + 4), "0", fontsize=8, fontname="helv")
    page.insert_text((350, tab_y0 + 4), "1", fontsize=8, fontname="helv")
    page.insert_text((650, tab_y0 + 4), "2", fontsize=8, fontname="helv")

    page.draw_line((150, not_y0 + 10), (150, not_y0 - 20), color=(0, 0, 0), width=1.0)
    page.draw_rect(fitz.Rect(147, not_y0 + 8, 153, not_y0 + 12), color=(0, 0, 0), fill=(0, 0, 0))

    page.draw_line((350, not_y0 + 10), (350, not_y0 - 20), color=(0, 0, 0), width=1.0)
    page.draw_rect(fitz.Rect(347, not_y0 + 8, 353, not_y0 + 12), color=(0, 0, 0), fill=(0, 0, 0))

    page.draw_line((650, not_y0 + 10), (650, not_y0 - 20), color=(0, 0, 0), width=1.0)
    page.draw_rect(fitz.Rect(647, not_y0 + 8, 653, not_y0 + 12), color=(0, 0, 0), fill=(0, 0, 0))

    pdf_path = Path(__file__).parent / "npg_04d_structural.pdf"
    doc.save(pdf_path)

if __name__ == "__main__":
    main()
