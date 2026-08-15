with open("tests/dynamic_fixtures.py", "r") as f:
    content = f.read()

safe_pdf_func = """
def _get_safe_dynamic_private_pdf() -> Path:
    private_dir = Path("fixtures/private")
    if private_dir.exists():
        pdfs = list(private_dir.glob("*.pdf"))
        if pdfs:
            for p in pdfs:
                if "Lesson-5" in p.name:
                    return p
            return pdfs[0]
    pytest.skip("No private fixtures found", allow_module_level=True)
    return Path("fixtures/private/dummy.pdf")
"""

content += "\n" + safe_pdf_func

with open("tests/dynamic_fixtures.py", "w") as f:
    f.write(content)
