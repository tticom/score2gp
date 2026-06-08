from __future__ import annotations

import json
from pathlib import Path

import fitz  # type: ignore[import-not-found]


def main() -> None:
    pdf_dir = Path(__file__).parent
    fixtures_dir = pdf_dir.parents[2] / "fixtures" / "public"

    json_path = fixtures_dir / "generated_standard_staff_dense_margin.json"
    pdf_path = pdf_dir / "generated_standard_staff_dense_margin.pdf"

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    doc = fitz.open()
    page = doc.new_page(width=data["page_width"], height=data["page_height"])

    page.insert_text((36, 40), "Generated Standard Staff Dense Margin", fontsize=12, fontname="helv")

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

    doc.save(pdf_path, garbage=4, deflate=True)
    doc.close()
    print(f"Compiled {pdf_path.name} successfully.")


if __name__ == "__main__":
    main()
