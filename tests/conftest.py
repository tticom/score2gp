import os
import sys
import pytest
import shutil
import json
from pathlib import Path

# Add src/ and project root to sys.path and PYTHONPATH so that test subprocesses can find modules.
project_root = Path(__file__).parent.parent.resolve()
src_path = project_root / "src"

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

paths_to_add = f"{src_path}{os.pathsep}{project_root}"
existing_pythonpath = os.environ.get("PYTHONPATH")
os.environ["PYTHONPATH"] = f"{paths_to_add}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else paths_to_add

from score2gp.notation_omr.pipeline import run_recognition_on_file
ARTIFACTS_DIR = Path("tests/artifacts")
PRIVATE_FIXTURES_DIR = Path("fixtures/private")

@pytest.fixture(scope="session", autouse=True)
def setup_private_artifacts():
    """
    Session-scoped fixture that runs the full OMR pipeline on all private PDF fixtures
    and dumps their intermediate representations (artifacts) to tests/artifacts/.
    These artifacts act as the new data sources for unit tests to replace synthetic fixtures.
    """
    if ARTIFACTS_DIR.exists():
        shutil.rmtree(ARTIFACTS_DIR)
    ARTIFACTS_DIR.mkdir(parents=True)

    if not PRIVATE_FIXTURES_DIR.exists():
        return

    # Process each private PDF and save its artifacts
    for pdf_path in PRIVATE_FIXTURES_DIR.glob("*.pdf"):
        try:
            # Run the extraction pipeline
            res = run_recognition_on_file(pdf_path, assume_treble_clef=True)
            if not res:
                continue

            # Save diagnostic and intermediate payload to tests/artifacts/<name>_pipeline_result.json
            out_json = ARTIFACTS_DIR / f"{pdf_path.stem}_pipeline_result.json"
            
            # Since some objects (like Enums, Events, etc) might not be strictly JSON serializable 
            # if they aren't pre-serialized by the pipeline, we just stringify the complex ones 
            # or rely on the pipeline's native dict structure if it's safe.
            # A safer approach for testing is to just write a summary or the raw text if needed.
            # We'll use a custom encoder or just string fallback for safety.
            def safe_default(obj):
                try:
                    return obj.to_dict()
                except AttributeError:
                    return str(obj)

            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(res, f, default=safe_default, indent=2)

        except Exception as e:
            # We allow failures here so the test suite can inspect what failed
            err_file = ARTIFACTS_DIR / f"{pdf_path.stem}_error.log"
            with open(err_file, "w", encoding="utf-8") as f:
                f.write(f"Failed to process {pdf_path.name}: {str(e)}")
