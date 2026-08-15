import re

with open("tests/dynamic_fixtures.py", "r") as f:
    content = f.read()

content = "import pytest\n" + content
content = content.replace(
    'return Path("fixtures/private/dummy.pdf")',
    'pytest.skip("No private fixtures found", allow_module_level=True)\n    return Path("fixtures/private/dummy.pdf")'
)
content = content.replace(
    'return Path("tests/artifacts/dummy.musicxml")',
    'pytest.skip("No private fixtures found", allow_module_level=True)\n    return Path("tests/artifacts/dummy.musicxml")'
)

with open("tests/dynamic_fixtures.py", "w") as f:
    f.write(content)
