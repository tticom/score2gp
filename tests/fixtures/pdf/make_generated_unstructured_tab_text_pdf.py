from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-not-found]


def main() -> None:
    out = Path(__file__).with_name("generated_unstructured_tab_text.pdf")
    doc = fitz.open()
    page = doc.new_page(width=420, height=300)

    page.insert_text((72, 62), "Generated Unstructured Tab Text", fontsize=12, fontname="helv")
    page.insert_text((86, 96), "Am", fontsize=9, fontname="helv")
    page.insert_text((210, 96), "slide", fontsize=8, fontname="helv")

    # Deliberately omit six horizontal tab lines and barlines. The fixture
    # proves text extraction can work while system/string/bar grouping cannot.
    tokens = [
        ("0", 95, 126),
        ("12", 140, 139),
        ("3", 182, 156),
        ("5", 238, 181),
        ("7", 288, 167),
        ("10", 326, 214),
    ]
    for text, x, y in tokens:
        page.insert_text((x, y), text, fontsize=10, fontname="cour")

    doc.save(out, garbage=4, deflate=True)
    doc.close()


if __name__ == "__main__":
    main()
