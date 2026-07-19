from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field



class RuntimeProvenanceRecord(BaseModel):

    """

    Private-safe provenance record for a corpus conversion run.

    This schema ensures that a run can be tied back to the exact code revision,

    environment, and commands used to generate its results.

    """

    model_config = ConfigDict(extra="forbid")



    product_sha: str

    is_dirty: bool

    cli_executable_path: str

    python_import_path: str

    exact_command: str

    input_classification: str



    musicxml_sidecar_info: Optional[Dict[str, str]] = None

    output_report_path: Optional[str] = None

    exit_status: int

    output_written: bool

    stage: str

    refusal_code: Optional[str] = None



    structural_counts: Dict[str, Any] = Field(default_factory=dict)



    @property

    def is_uncontrolled_runtime(self) -> bool:

        """

        A runtime is uncontrolled if the codebase is dirty or if there's an

        import/runtime mismatch (e.g. the executable and library do not share a common environment).

        """

        if self.is_dirty:

            return True



        import os

        from pathlib import Path



        # Check if the import path comes from a developer 'src' checkout instead of an installed package

        import_parts = Path(self.python_import_path).parts

        if "src" in import_parts and "score2gp" in import_parts:

            return True



        try:

            exec_parts = Path(self.cli_executable_path).parts



            # If they don't share at least the first two directories (e.g. /, usr or C:\, Python), they mismatch.

            # But wait, what if it's installed in /opt and /usr? Then common parts is just ('/',).

            # Let's find the common prefix length.

            common_len = 0

            for e, i in zip(exec_parts, import_parts):

                if e == i:

                    common_len += 1

                else:

                    break



            # If the only common part is the root (e.g. '/' or 'C:\'), they are mismatched.

            if common_len <= 1:

                return True

        except Exception:

            return True



        return False
