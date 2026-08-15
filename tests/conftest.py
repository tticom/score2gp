import os
from pathlib import Path

# Add src/ and project root to sys.path and PYTHONPATH so that test subprocesses can find modules.
project_root = Path(__file__).parent.parent.resolve()
src_path = project_root / "src"

import sys
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

paths_to_add = f"{src_path}{os.pathsep}{project_root}"
existing_pythonpath = os.environ.get("PYTHONPATH")
os.environ["PYTHONPATH"] = f"{paths_to_add}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else paths_to_add

