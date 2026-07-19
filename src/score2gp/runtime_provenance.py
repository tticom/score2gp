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
        A runtime is uncontrolled if the codebase is dirty.
        (Further constraints, such as standard installation paths, can be added here).
        """
        return self.is_dirty
