from __future__ import annotations

import json
from pathlib import Path

import fitz  # type: ignore[import-not-found]


def build_pdf(json_name: str, pdf_name: str) -> None:
    pdf_dir = Path(__file__).parent
    fixtures_dir = pdf_dir.parents[2] / "fixtures" / "public"

    json_path = fixtures_dir / json_name
    pdf_path = pdf_dir / pdf_name

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    doc = fitz.open()
    page = doc.new_page(width=data["page_width"], height=data["page_height"])

    page.insert_text((36, 40), f"Generated Standard Staff: {pdf_name}", fontsize=12, fontname="helv")

    # Draw standard 5-line notation staff
    staves_data = data.get("notation_staves", [data.get("notation_staff")] if "notation_staff" in data else [])
    for not_data in staves_data:
        if not not_data:
            continue
        not_ys = [not_data["y_start"] + i * not_data["line_gap"] for i in range(not_data["line_count"])]
        for y in not_ys:
            page.draw_line((not_data["x0"], y), (not_data["x1"], y), color=(0, 0, 0), width=0.5)

    # Draw true shared barlines
    for bar in data.get("barlines", []):
        page.draw_line((bar["x"], bar["y_min"]), (bar["x"], bar["y_max"]), color=(0, 0, 0), width=0.6)

    # Insert margin text clusters
    for txt in data.get("margin_text_clusters", []):
        page.insert_text((txt["x"], txt["y"]), txt["text"], fontsize=txt["fontsize"], fontname=txt["fontname"])

    # Draw wide curves (Bezier)
    for curve in data.get("wide_curves", []):
        p0 = curve["p0"]
        p1 = curve["p1"]
        p2 = curve["p2"]
        p3 = curve["p3"]
        page.draw_bezier(p0, p1, p2, p3, color=(0, 0, 0), width=1.0)

    # Draw note clusters
    for cluster in data.get("note_clusters", []):
        for rect in cluster.get("rects", []):
            page.draw_rect(
                (rect["x0"], rect["y0"], rect["x1"], rect["y1"]),
                color=(0, 0, 0),
                fill=(0, 0, 0)
            )
        for line in cluster.get("lines", []):
            page.draw_line(
                (line["x0"], line["y0"]),
                (line["x1"], line["y1"]),
                color=(0, 0, 0),
                width=1.0
            )
        for txt in cluster.get("texts", []):
            page.insert_text(
                (txt["x"], txt["y"]),
                txt["text"],
                fontsize=txt["fontsize"],
                fontname=txt["fontname"]
            )

    # Draw whole notes (hollow ovals)
    for wn in data.get("whole_notes", []):
        page.draw_oval(
            fitz.Rect(wn["x0"], wn["y0"], wn["x1"], wn["y1"]),
            color=(0, 0, 0),
            width=1.5
        )

    # Draw half notes (hollow ovals with a stem)
    for hn in data.get("half_notes", []):
        page.draw_oval(
            fitz.Rect(hn["x0"], hn["y0"], hn["x1"], hn["y1"]),
            color=(0, 0, 0),
            width=1.5
        )
        page.draw_line(
            (hn["stem_x0"], hn["stem_y0"]),
            (hn["stem_x1"], hn["stem_y1"]),
            color=(0, 0, 0),
            width=1.0
        )

    # Draw quarter notes (filled ovals with a stem)
    for qn in data.get("quarter_notes", []):
        page.draw_oval(
            fitz.Rect(qn["x0"], qn["y0"], qn["x1"], qn["y1"]),
            color=(0, 0, 0),
            fill=(0, 0, 0),
            width=1.5
        )
        page.draw_line(
            (qn["stem_x0"], qn["stem_y0"]),
            (qn["stem_x1"], qn["stem_y1"]),
            color=(0, 0, 0),
            width=1.0
        )


    doc.save(pdf_path, garbage=4, deflate=True)
    doc.close()
    print(f"Compiled {pdf_path.name} successfully.")

def main() -> None:
    build_pdf("generated_standard_staff_dense_margin.json", "generated_standard_staff_dense_margin.pdf")
    build_pdf("generated_standard_staff_sparse.json", "generated_standard_staff_sparse.pdf")
    build_pdf("generated_standard_staff_wide_curves.json", "generated_standard_staff_wide_curves.pdf")
    build_pdf("generated_standard_staff_complex_cluster.json", "generated_standard_staff_complex_cluster.pdf")
    build_pdf("generated_standard_staff_multi_staff.json", "generated_standard_staff_multi_staff.pdf")
    build_pdf("generated_standard_staff_multi_staff_unconnected.json", "generated_standard_staff_multi_staff_unconnected.pdf")
    build_pdf("generated_standard_staff_rectangle_positions.json", "generated_standard_staff_rectangle_positions.pdf")
    build_pdf("generated_standard_staff_text_font_diversity.json", "generated_standard_staff_text_font_diversity.pdf")
    build_pdf("generated_standard_staff_left_margin_threshold.json", "generated_standard_staff_left_margin_threshold.pdf")
    build_pdf("generated_standard_staff_negative_tab.json", "generated_standard_staff_negative_tab.pdf")
    build_pdf("generated_standard_staff_negative_blank.json", "generated_standard_staff_negative_blank.pdf")
    build_pdf("generated_standard_staff_negative_noise.json", "generated_standard_staff_negative_noise.pdf")
    build_pdf("generated_standard_staff_whole_note.json", "generated_standard_staff_whole_note.pdf")
    build_pdf("generated_standard_staff_single_whole_note.json", "generated_standard_staff_single_whole_note.pdf")
    build_pdf("generated_standard_staff_half_note.json", "generated_standard_staff_half_note.pdf")
    build_pdf("generated_standard_staff_quarter_note.json", "generated_standard_staff_quarter_note.pdf")
    build_pdf("generated_standard_staff_eighth_notes.json", "generated_standard_staff_eighth_notes.pdf")
    build_pdf("generated_standard_staff_ledger_lines.json", "generated_standard_staff_ledger_lines.pdf")
    build_pdf("generated_standard_staff_bass_clef.json", "generated_standard_staff_bass_clef.pdf")
    build_pdf("generated_standard_staff_alto_clef.json", "generated_standard_staff_alto_clef.pdf")
if __name__ == "__main__":
    main()
