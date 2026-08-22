import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


def sanitize_exact_command(command: List[str]) -> List[str]:
    """
    Sanitize command-line arguments to anonymize local user file paths, private corpus filenames,
    and directory structures to prevent private data leakage in provenance records.
    """
    sanitized = []
    prev_flag = None

    for arg in command:
        arg_lower = arg.lower()

        # Check if previous arg was a flag specifying input or output path
        if prev_flag in ("--pdf", "--musicxml"):
            sanitized.append("[PRIVATE_INPUT_PATH]")
            prev_flag = None
            continue
        if prev_flag in ("--out", "--out-dir"):
            sanitized.append("[PRIVATE_OUTPUT_PATH]")
            prev_flag = None
            continue

        if arg.startswith("--pdf=") or arg.startswith("--musicxml="):
            sanitized.append(f"{arg.split('=', 1)[0]}=[PRIVATE_INPUT_PATH]")
            prev_flag = None
            continue
        if arg.startswith("--out=") or arg.startswith("--out-dir="):
            sanitized.append(f"{arg.split('=', 1)[0]}=[PRIVATE_OUTPUT_PATH]")
            prev_flag = None
            continue

        if arg in ("--pdf", "--musicxml", "--out", "--out-dir"):
            sanitized.append(arg)
            prev_flag = arg
            continue

        prev_flag = None

        # General path sanitization rules
        if arg_lower.endswith((".pdf", ".musicxml", ".mxl", ".xml")):
            sanitized.append("[PRIVATE_INPUT_PATH]")
        elif arg_lower.endswith(".gp"):
            sanitized.append("[PRIVATE_OUTPUT_PATH]")
        elif "/fixtures/private" in arg_lower or "private_fixtures" in arg_lower or "private_inputs" in arg_lower:
            sanitized.append("[PRIVATE_INPUT_PATH]")
        elif ("work/" in arg_lower or "/work/" in arg_lower) and not arg.startswith("-"):
            sanitized.append("[PRIVATE_OUTPUT_PATH]")
        elif (arg.startswith("/") or arg.startswith("C:\\") or arg.startswith("c:\\")) and (
            "/home/" in arg_lower or "/users/" in arg_lower or "/tmp/" in arg_lower
        ):
            sanitized.append("[PRIVATE_PATH]")
        else:
            sanitized.append(arg)

    return sanitized


def get_git_info(repo_root: Optional[Path] = None) -> tuple[str, bool]:
    """
    Query git for current commit SHA and working tree dirty status.
    Fail-safe: If git execution fails or environment error occurs, return ("unknown", True)
    so is_dirty defaults to True (uncontrolled runtime) instead of raising exceptions.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent

    try:
        res_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res_sha.returncode != 0:
            return "unknown", True
        sha = res_sha.stdout.strip()

        res_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res_status.returncode != 0:
            return sha, True
        is_dirty = bool(res_status.stdout.strip())
        return sha, is_dirty
    except Exception:
        return "unknown", True


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

        if (
            self.stage == "runtime_probe_failed"
            or self.cli_executable_path == "unknown"
            or self.python_import_path == "unknown"
            or self.child_python_executable_path == "unknown"
        ):
            return True

        expected_src_path = str(Path(__file__).parent.resolve())
        child_name = Path(self.child_python_executable_path).name.lower()

        # Versioned Python interpreter matching (e.g., python, python3, python3.12, python3.10.exe)
        is_python_exe = bool(re.match(r"^python(\d+(\.\d+)?)?(\.exe)?$", child_name)) or child_name.startswith("python")

        if is_python_exe:
            if self.python_import_path == expected_src_path:
                return False

        if "/src/score2gp" in self.python_import_path or self.python_import_path.endswith("/src/score2gp"):
            if self.python_import_path != expected_src_path:
                return True

        # Installed package executable or system python environment compatibility check
        try:
            exec_str = str(Path(self.cli_executable_path).resolve())
            import_str = str(Path(self.python_import_path).resolve())

            # Standard Linux/Windows system installation prefixes
            system_prefixes = ["/usr/", "/usr/local/", "/opt/", "c:\\program files", sys.prefix, sys.base_prefix]
            for sys_prefix in system_prefixes:
                if sys_prefix and exec_str.startswith(sys_prefix) and import_str.startswith(sys_prefix):
                    return False

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


def create_runtime_provenance_record(
    *,
    exact_command: List[str],
    input_classification: str,
    output_report_path: Optional[str] = None,
    gp_output_path: Optional[str] = None,
    musicxml_sidecar_info: Optional[Dict[str, str]] = None,
    exit_status: int = 0,
    output_written: bool = True,
    stage: str = "completed",
    refusal_code: Optional[str] = None,
    structural_counts: Optional[Dict[str, Any]] = None,
    repo_root: Optional[Path] = None,
) -> RuntimeProvenanceRecord:
    """
    Helper to construct a validated RuntimeProvenanceRecord capturing git status, executable paths,
    and sanitized execution arguments.
    """
    product_sha, is_dirty = get_git_info(repo_root=repo_root)

    import score2gp
    import_path = str(Path(score2gp.__file__).parent.resolve())
    child_python = sys.executable
    cli_exec = sys.argv[0] if sys.argv else "python3"

    sanitized_cmd = sanitize_exact_command(exact_command)

    return RuntimeProvenanceRecord(
        product_sha=product_sha,
        is_dirty=is_dirty,
        cli_executable_path=cli_exec,
        child_python_executable_path=child_python,
        python_import_path=import_path,
        exact_command=sanitized_cmd,
        input_classification=input_classification,
        musicxml_sidecar_info=musicxml_sidecar_info,
        output_report_path=output_report_path,
        gp_output_path=gp_output_path,
        exit_status=exit_status,
        output_written=output_written,
        stage=stage,
        refusal_code=refusal_code,
        structural_counts=structural_counts or {},
    )
