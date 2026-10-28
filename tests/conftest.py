import os
from pathlib import Path

pytest_plugins = ["private_corpus_guard"]

# Add src/ and project root to sys.path and PYTHONPATH so that test subprocesses can find modules.
project_root = Path(__file__).parent.parent.resolve()
src_path = project_root / "src"

import sys
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

paths_to_add = f"{src_path}{os.pathsep}{project_root}"
existing_pythonpath = os.environ.get("PYTHONPATH")
os.environ["PYTHONPATH"] = f"{paths_to_add}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else paths_to_add


import functools
import subprocess

import pytest


_gpif_acceptance_item = None


def pytest_collection_modifyitems(items):
    from windows_host_quarantine import apply_quarantine

    apply_quarantine(items)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    global _gpif_acceptance_item
    _gpif_acceptance_item = item


def _record_cli_layout(mode):
    if _gpif_acceptance_item is not None:
        _gpif_acceptance_item.user_properties.append(("gpif_cli_layout_checked", mode))


@pytest.fixture(scope="session", autouse=True)
def production_gpif_acceptance():
    # Session scope is essential: private conversions also happen in module-
    # scoped fixtures, before any function-scoped autouse fixture can run.
    with pytest.MonkeyPatch.context() as monkeypatch:
        _install_gpif_acceptance(monkeypatch)
        yield


@pytest.fixture
def legacy_batch_gpif(monkeypatch):
    """Explicit compatibility opt-in for programmatic batch contracts."""
    from gpif_test_helpers import legacy_write_gp

    monkeypatch.setattr("score2gp.batch.write_gp", legacy_write_gp)


def _install_gpif_acceptance(monkeypatch):
    """Every CLI writer must emit relational GPIF, in-process or as a child.

    Explicit legacy unit writers are checked by their existing XML assertions.
    Rejected commands that produce no package have no layout to inspect.
    """
    from score2gp import gp_package
    from typer.testing import CliRunner
    from gpif_test_helpers import assert_production_gpif, assert_production_package

    build = gp_package.build_gpif
    cli_outputs = None

    @functools.wraps(build)
    def checked_build(*args, **kwargs):
        data = build(*args, **kwargs)
        if cli_outputs is not None:
            cli_outputs.append(data)
        if kwargs.get("layout", "relational") == "relational":
            assert_production_gpif(data)
        return data

    monkeypatch.setattr(gp_package, "build_gpif", checked_build)
    invoke = CliRunner.invoke

    @functools.wraps(invoke)
    def checked_invoke(*args, **kwargs):
        nonlocal cli_outputs
        previous, cli_outputs = cli_outputs, []
        try:
            result = invoke(*args, **kwargs)
            for data in cli_outputs:
                assert_production_gpif(data)
                _record_cli_layout("in-process")
            return result
        finally:
            cli_outputs = previous

    monkeypatch.setattr(CliRunner, "invoke", checked_invoke)
    run = subprocess.run

    @functools.wraps(run)
    def checked_run(*args, **kwargs):
        command = kwargs.get("args", args[0] if args else [])
        outputs = []
        output_directories = []
        # Some acceptance commands enter cli.app() through a Python -c wrapper
        # (for example report capture), rather than `-m score2gp.cli`.
        if isinstance(command, (list, tuple)):
            command = list(command)
            for index, arg in enumerate(command[:-1]):
                if arg == "--out":
                    path = Path(command[index + 1])
                    if not path.is_absolute():
                        path = Path(kwargs.get("cwd", Path.cwd())) / path
                    if path.suffix.lower() == ".gp":
                        before = path.stat() if path.is_file() else None
                        outputs.append((path, before))
                        # Private inputs stay in their original temporary paths.
                        # Challenge only the output argument with an equivalent
                        # path whose spelling triggered the removed switch.
                        canonical = path.resolve()
                        if ("pytest" not in str(path) and canonical.parent.is_dir()
                                and canonical.is_relative_to(project_root / "work")):
                            marker = canonical.parent / ".pytest-layout-probe"
                            marker.mkdir(exist_ok=True)
                            command[index + 1] = str(marker / ".." / canonical.name)
            if "diagnose" in command:
                index = command.index("diagnose")
                if len(command) > index + 2:
                    directory = Path(command[index + 2])
                    output_directories.append(directory)
                    outputs.extend((path, path.stat()) for path in directory.rglob("*.gp"))
        try:
            if isinstance(command, list):
                if "args" in kwargs:
                    kwargs = {**kwargs, "args": command}
                else:
                    args = (command, *args[1:])
            return run(*args, **kwargs)
        finally:
            # Inspect artifacts even when check=True raises for a refused command.
            existing = {path for path, before in outputs}
            for directory in output_directories:
                outputs.extend((path, None) for path in directory.rglob("*.gp") if path not in existing)
            for path, before in outputs:
                # A refusing command may leave an existing input/output untouched.
                if path.is_file():
                    after = path.stat()
                    if before is None or (after.st_mtime_ns, after.st_size) != (before.st_mtime_ns, before.st_size):
                        assert_production_package(path)
                        _record_cli_layout("subprocess")

    monkeypatch.setattr(subprocess, "run", checked_run)

