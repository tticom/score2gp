from typing import Any, Dict, List, Optional

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
    child_python_executable_path: str
    python_import_path: str
    exact_command: List[str]
    input_classification: str



    musicxml_sidecar_info: Optional[Dict[str, str]] = None
    output_report_path: Optional[str] = None
    gp_output_path: Optional[str] = None

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

        if self.stage == "runtime_probe_failed" or self.cli_executable_path == "unknown" or self.python_import_path == "unknown" or self.child_python_executable_path == "unknown":
            return True

        import os
        from pathlib import Path

        # If it's a native module execution (python interpreter) against a developer 'src' checkout, it is controlled.
        # We enforce the exact approved project root by checking that python_import_path matches this file's package dir.
        expected_src_path = str(Path(__file__).parent.resolve())
        child_name = Path(self.child_python_executable_path).name.lower()
        if child_name in ("python", "python.exe", "python3", "python3.exe"):
            if self.python_import_path == expected_src_path:
                return False

        # Otherwise, if it's an installed package executable (like score2gp.exe), it must share a common installation environment.
        try:
            exec_parts = Path(self.cli_executable_path).parts
            import_parts = Path(self.python_import_path).parts

            common_len = 0
            for e, i in zip(exec_parts, import_parts):
                if e == i:
                    common_len += 1
                else:
                    break

            if common_len <= 1:
                return True
        except Exception:
            return True



        return False
