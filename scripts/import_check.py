#!/usr/bin/env python3
import sys
from pathlib import Path

def main():
    try:
        import score2gp
    except ImportError as e:
        print(f"Error: Could not import 'score2gp': {e}", file=sys.stderr)
        sys.exit(1)

    imported_file = Path(score2gp.__file__).resolve()
    workspace_root = Path(__file__).resolve().parent.parent
    expected_file = (workspace_root / "src" / "score2gp" / "__init__.py").resolve()

    print(f"Checking import boundary...")
    print(f"Workspace root: {workspace_root}")
    print(f"Expected import path: {expected_file}")
    print(f"Actual imported path: {imported_file}")

    if imported_file != expected_file:
        print(f"\n==================================================", file=sys.stderr)
        print(f"IMPORT BOUNDARY VIOLATION DETECTED!", file=sys.stderr)
        print(f"Python imported 'score2gp' from an unexpected location:", file=sys.stderr)
        print(f"  {imported_file}", file=sys.stderr)
        print(f"Instead of the local recovery workspace path:", file=sys.stderr)
        print(f"  {expected_file}", file=sys.stderr)
        print(f"\nThis is likely due to the virtual environment having an editable installation", file=sys.stderr)
        print(f"pointing to a different workspace directory.", file=sys.stderr)
        print(f"\nTo resolve this, ensure you execute python with PYTHONPATH=.:src set,", file=sys.stderr)
        print(f"for example:", file=sys.stderr)
        print(f"  env PYTHONPATH=.:src python -m score2gp.cli convert ...", file=sys.stderr)
        print(f"==================================================\n", file=sys.stderr)
        sys.exit(1)

    print("Success: Python imports from the local recovery workspace.")
    sys.exit(0)

if __name__ == "__main__":
    main()
