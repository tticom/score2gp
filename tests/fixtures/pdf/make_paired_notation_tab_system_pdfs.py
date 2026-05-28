from __future__ import annotations

import json
from pathlib import Path

import fitz  # type: ignore[import-not-found]


def main() -> None:
    pdf_dir = Path(__file__).parent
    fixtures_dir = pdf_dir.parents[2] / "fixtures" / "public"

    # 1. Compile generated_paired_notation_tab_system.json to PDF
    json_path = fixtures_dir / "generated_paired_notation_tab_system.json"
    pdf_path = pdf_dir / "generated_paired_notation_tab_system.pdf"

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    doc = fitz.open()
    page = doc.new_page(width=data["page_width"], height=data["page_height"])

    page.insert_text((36, 40), "Generated Paired Notation TAB System", fontsize=12, fontname="helv")

    # Draw standard 5-line notation staff
    not_data = data["notation_staff"]
    not_ys = [not_data["y_start"] + i * not_data["line_gap"] for i in range(not_data["line_count"])]
    for y in not_ys:
        page.draw_line((not_data["x0"], y), (not_data["x1"], y), color=(0, 0, 0), width=0.5)

    # Draw 6-line TAB staff
    tab_data = data["tab_staff"]
    tab_ys = [tab_data["y_start"] + i * tab_data["line_gap"] for i in range(tab_data["line_count"])]
    for idx, y in enumerate(tab_ys):
        if idx == tab_data["fragmented_line_index"]:
            # Draw split collinear segments with a gap
            page.draw_line((tab_data["fragment_left"]["x0"], y), (tab_data["fragment_left"]["x1"], y), color=(0, 0, 0), width=0.6)
            page.draw_line((tab_data["fragment_right"]["x0"], y), (tab_data["fragment_right"]["x1"], y), color=(0, 0, 0), width=0.6)
        else:
            page.draw_line((tab_data["x0"], y), (tab_data["x1"], y), color=(0, 0, 0), width=0.6)

    # Draw true shared barlines
    for bar in data["barlines"]:
        page.draw_line((bar["x"], bar["y_min"]), (bar["x"], bar["y_max"]), color=(0, 0, 0), width=0.6)

    # Draw notation-only stems
    for stem in data["notation_stems"]:
        page.draw_line((stem["x"], stem["y_min"]), (stem["x"], stem["y_max"]), color=(0, 0, 0), width=0.4)

    # Draw TAB rhythm stems
    for stem in data["tab_rhythm_stems"]:
        page.draw_line((stem["x"], stem["y_min"]), (stem["x"], stem["y_max"]), color=(0, 0, 0), width=0.4)

    # Insert fret candidates
    for fret in data["fret_candidates"]:
        page.insert_text((fret["x"], fret["y"] + 1.8), fret["text"], fontsize=5.5, fontname="cour")

    doc.save(pdf_path, garbage=4, deflate=True)
    doc.close()
    print(f"Compiled {pdf_path.name} successfully.")

    # 2. Compile generated_paired_notation_tab_system_ambiguous.json to PDF
    json_path_amb = fixtures_dir / "generated_paired_notation_tab_system_ambiguous.json"
    pdf_path_amb = pdf_dir / "generated_paired_notation_tab_system_ambiguous.pdf"

    with open(json_path_amb, encoding="utf-8") as f:
        data_amb = json.load(f)

    doc_amb = fitz.open()
    page_amb = doc_amb.new_page(width=data_amb["page_width"], height=data_amb["page_height"])

    page_amb.insert_text((36, 40), "Generated Paired Notation TAB System Ambiguous", fontsize=12, fontname="helv")

    # Draw damaged TAB staff (5 lines, gap 6.4)
    dt_data = data_amb["damaged_tab_staff"]
    dt_ys = [dt_data["y_start"] + i * dt_data["line_gap"] for i in range(dt_data["line_count"])]
    for y in dt_ys:
        page_amb.draw_line((dt_data["x0"], y), (dt_data["x1"], y), color=(0, 0, 0), width=0.6)
    for bar in dt_data["barlines"]:
        page_amb.draw_line((bar["x"], bar["y_min"]), (bar["x"], bar["y_max"]), color=(0, 0, 0), width=0.6)
    for fret in dt_data["fret_candidates"]:
        page_amb.insert_text((fret["x"], fret["y"] + 1.8), fret["text"], fontsize=5.5, fontname="cour")

    # Draw ambiguous damaged staff (5 lines, gap 7.5)
    amb_data = data_amb["ambiguous_damaged_staff"]
    amb_ys = [amb_data["y_start"] + i * amb_data["line_gap"] for i in range(amb_data["line_count"])]
    for y in amb_ys:
        page_amb.draw_line((amb_data["x0"], y), (amb_data["x1"], y), color=(0, 0, 0), width=0.6)
    for bar in amb_data["barlines"]:
        page_amb.draw_line((bar["x"], bar["y_min"]), (bar["x"], bar["y_max"]), color=(0, 0, 0), width=0.6)
    for fret in amb_data["fret_candidates"]:
        page_amb.insert_text((fret["x"], fret["y"] + 1.8), fret["text"], fontsize=5.5, fontname="cour")

    doc_amb.save(pdf_path_amb, garbage=4, deflate=True)
    doc_amb.close()
    print(f"Compiled {pdf_path_amb.name} successfully.")

    # 3. Compile generated_paired_tab_row_fragmentation.json to PDF
    json_path_frag = fixtures_dir / "generated_paired_tab_row_fragmentation.json"
    pdf_path_frag = pdf_dir / "generated_paired_tab_row_fragmentation.pdf"

    with open(json_path_frag, encoding="utf-8") as f:
        data_frag = json.load(f)

    doc_frag = fitz.open()
    page_frag = doc_frag.new_page(width=data_frag["page_width"], height=data_frag["page_height"])

    page_frag.insert_text((36, 40), "Generated Paired TAB Row Fragmentation", fontsize=12, fontname="helv")

    # Draw standard 5-line notation staff
    not_data = data_frag["notation_staff"]
    not_ys = [not_data["y_start"] + i * not_data["line_gap"] for i in range(not_data["line_count"])]
    for y in not_ys:
        page_frag.draw_line((not_data["x0"], y), (not_data["x1"], y), color=(0, 0, 0), width=0.5)

    # Draw split collinear segments across ALL TAB strings
    tab_data = data_frag["tab_staff"]
    tab_ys = [tab_data["y_start"] + i * tab_data["line_gap"] for i in range(tab_data["line_count"])]
    for y in tab_ys:
        page_frag.draw_line((tab_data["fragment_left"]["x0"], y), (tab_data["fragment_left"]["x1"], y), color=(0, 0, 0), width=0.6)
        page_frag.draw_line((tab_data["fragment_right"]["x0"], y), (tab_data["fragment_right"]["x1"], y), color=(0, 0, 0), width=0.6)

    # Draw true shared barlines
    for bar in data_frag["barlines"]:
        page_frag.draw_line((bar["x"], bar["y_min"]), (bar["x"], bar["y_max"]), color=(0, 0, 0), width=0.6)

    # Draw notation-only stems
    for stem in data_frag["notation_stems"]:
        page_frag.draw_line((stem["x"], stem["y_min"]), (stem["x"], stem["y_max"]), color=(0, 0, 0), width=0.4)

    # Draw TAB rhythm stems
    for stem in data_frag["tab_rhythm_stems"]:
        page_frag.draw_line((stem["x"], stem["y_min"]), (stem["x"], stem["y_max"]), color=(0, 0, 0), width=0.4)

    # Insert fret candidates
    for fret in data_frag["fret_candidates"]:
        page_frag.insert_text((fret["x"], fret["y"] + 1.8), fret["text"], fontsize=5.5, fontname="cour")

    doc_frag.save(pdf_path_frag, garbage=4, deflate=True)
    doc_frag.close()
    print(f"Compiled {pdf_path_frag.name} successfully.")


if __name__ == "__main__":
    main()
