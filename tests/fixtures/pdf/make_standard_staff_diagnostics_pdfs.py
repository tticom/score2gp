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
    not_data = data["notation_staff"]
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
        p1 = curve["p1"]
        p2 = curve["p2"]
        p3 = curve["p3"]
        p4 = curve["p4"]
        page.draw_bezier(p1, p2, p3, p4, color=(0, 0, 0), width=1.0)


    doc.save(pdf_path, garbage=4, deflate=True)
    doc.close()
    print(f"Compiled {pdf_path.name} successfully.")

def main() -> None:
    build_pdf("generated_standard_staff_dense_margin.json", "generated_standard_staff_dense_margin.pdf")
    build_pdf("generated_standard_staff_sparse.json", "generated_standard_staff_sparse.pdf")
    build_pdf("generated_standard_staff_wide_curves.json", "generated_standard_staff_wide_curves.pdf")


if __name__ == "__main__":
    main()
