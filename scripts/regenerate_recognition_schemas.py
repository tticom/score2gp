#!/usr/bin/env python3
"""Regenerate and export recognition JSON schemas."""

from pathlib import Path
import sys

# Ensure src/ is in sys.path when script is executed directly
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from score2gp.recognition.schemas import export_recognition_schemas


def main() -> None:
    schema_dir = Path("schemas")
    exported = export_recognition_schemas(schema_dir)
    print(f"Successfully exported {len(exported)} recognition JSON schemas to {schema_dir}/:")
    for path in exported:
        print(f"  - {path.name}")


if __name__ == "__main__":
    main()
