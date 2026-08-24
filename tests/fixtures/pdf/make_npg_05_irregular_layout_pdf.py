import fitz
from pathlib import Path

def main():
    doc = fitz.open()
    page = doc.new_page(width=800, height=800)

    # SYSTEM 1: 3 bars
    not_y1 = 100
    tab_y1 = 160
    for i in range(5):
        page.draw_line((50, not_y1 + i * 8), (750, not_y1 + i * 8), color=(0,0,0), width=0.5)
    for i in range(6):
        page.draw_line((50, tab_y1 + i * 10), (750, tab_y1 + i * 10), color=(0,0,0), width=0.5)
    
    for x in [50, 250, 500, 750]:
        page.draw_line((x, not_y1), (x, not_y1 + 32), color=(0,0,0), width=1)
        page.draw_line((x, tab_y1), (x, tab_y1 + 50), color=(0,0,0), width=1)
        
    page.insert_text((150, tab_y1 + 25), "1", fontname="helv", fontsize=10)
    page.insert_text((375, tab_y1 + 25), "2", fontname="helv", fontsize=10)
    page.insert_text((625, tab_y1 + 25), "3", fontname="helv", fontsize=10)
    
    for x in [150, 375, 625]:
        page.insert_text((x, not_y1 + 16), "O", fontname="helv", fontsize=10)

    # SYSTEM 2: 4 bars
    not_y2 = 300
    tab_y2 = 360
    for i in range(5):
        page.draw_line((50, not_y2 + i * 8), (750, not_y2 + i * 8), color=(0,0,0), width=0.5)
    for i in range(6):
        page.draw_line((50, tab_y2 + i * 10), (750, tab_y2 + i * 10), color=(0,0,0), width=0.5)
        
    for x in [50, 200, 350, 550, 750]:
        page.draw_line((x, not_y2), (x, not_y2 + 32), color=(0,0,0), width=1)
        page.draw_line((x, tab_y2), (x, tab_y2 + 50), color=(0,0,0), width=1)

    for x in [125, 275, 450, 650]:
        page.insert_text((x, tab_y2 + 25), "0", fontname="helv", fontsize=10)
        page.insert_text((x, not_y2 + 16), "O", fontname="helv", fontsize=10)

    # SYSTEM 3: severely truncated contents (frets close together)
    not_y3 = 500
    tab_y3 = 560
    # Make staff lines long enough to be detected (200pt)
    for i in range(5):
        page.draw_line((50, not_y3 + i * 8), (250, not_y3 + i * 8), color=(0,0,0), width=0.5)
    for i in range(6):
        page.draw_line((50, tab_y3 + i * 10), (250, tab_y3 + i * 10), color=(0,0,0), width=0.5)
        
    # Barlines at 50 and 250
    for x in [50, 250]:
        page.draw_line((x, not_y3), (x, not_y3 + 32), color=(0,0,0), width=1)
        page.draw_line((x, tab_y3), (x, tab_y3 + 50), color=(0,0,0), width=1)
        
    # Put frets extremely close together (x=60, x=80) -> width = 20 < 50
    page.insert_text((60, tab_y3 + 25), "0", fontname="helv", fontsize=10)
    page.insert_text((80, tab_y3 + 25), "1", fontname="helv", fontsize=10)
    page.insert_text((70, not_y3 + 16), "O", fontname="helv", fontsize=10)

    out_path = Path("tests/fixtures/pdf/generated_npg_05_irregular_layout.pdf")
    doc.save(str(out_path))

if __name__ == "__main__":
    main()
