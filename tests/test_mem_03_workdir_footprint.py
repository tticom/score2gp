"""MEM-03: work-directory footprint and peak memory of a real conversion.

Real approved sources only, converted through the actual CLI in a subprocess.
Each test names the wrong implementation it rejects:

* ``test_inspection_is_written_once``: a second inspection (and page renders)
  under ``tab/inspect`` -- the base behaviour -- fails the single-copy checks.
* ``test_heavy_diagnostics_are_opt_in``: grouping overlays and HTML written by
  default fail the default check; a flag that does nothing fails the opt-in check.
* ``test_bytes_per_bar_and_peak_memory_budget``: either mutant above exceeds the
  bytes-per-bar bound; unbounded memory growth exceeds the working-set bound.

Bounds are set from measurement at this change (see the MEM-03 handback).
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"

# Reports the child's peak working set (bytes) without third-party packages.
RUN_WITH_PEAK = """import atexit, os, sys
def peak():
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes as w
        class PMC(ctypes.Structure):
            _fields_ = [('cb', w.DWORD), ('PageFaultCount', w.DWORD),
                        ('PeakWorkingSetSize', ctypes.c_size_t)] + [
                (n, ctypes.c_size_t) for n in ('WorkingSetSize', 'a', 'b', 'c', 'd', 'e', 'f')]
        counters = PMC()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = w.HANDLE
        ctypes.windll.psapi.GetProcessMemoryInfo(
            w.HANDLE(kernel.GetCurrentProcess()), ctypes.byref(counters), counters.cb)
        return counters.PeakWorkingSetSize
    if sys.platform.startswith('linux'):
        # VmHWM is per address space and reset by exec. ru_maxrss is inherited
        # across fork+exec, so it would report the spawning pytest's peak.
        for line in open('/proc/self/status'):
            if line.startswith('VmHWM:'):
                return int(line.split()[1]) * 1024
    import resource
    scale = 1 if sys.platform == 'darwin' else 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
atexit.register(lambda: open(os.environ['MEM03_PEAK'], 'w').write(str(peak())))
from score2gp import cli
cli.app()
"""

# (source, bytes-per-bar bound, peak working set bound). Measured at this change
# (4 runs each): bytes are exactly repeatable, so the bytes bound is the measured
# bytes/bar + 3%; the peak spread across runs was under 0.5%, so the peak bound is
# the Windows PeakWorkingSetSize + 35% to absorb platform/allocator differences
# (Linux reads VmHWM of the child; the bounds were not calibrated on Linux, so the
# headroom is wide and the bound guards against gross growth, not small drift). Base (before
# this change) bytes/bar exceed these bounds on all three sources.
BUDGETS = {
    "Lesson-3.pdf": (1_069_000, 430_000_000),
    "Melodic Soloing Masterclass.pdf": (1_535_000, 425_000_000),
    "A7-Blues-Lick.pdf": (1_578_000, 175_000_000),
}


def _convert(name, scratch, *extra):
    source = PRIVATE / name
    if not source.is_file():
        pytest.skip("private corpus absent")
    peak_path = scratch / "peak.txt"
    result = subprocess.run(
        [sys.executable, "-c", RUN_WITH_PEAK, "convert", "--pdf", str(source),
         "--pdf-only-tab", "--time-signature", "4/4", "--out", str(scratch / "result.gp"),
         "--work-dir", str(scratch / "conversion"), "--json-report", str(scratch / "result.json"),
         *extra],
        capture_output=True, env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "MEM03_PEAK": str(peak_path)})
    payload = json.loads((scratch / "result.json").read_text(encoding="utf-8"))
    assert result.returncode == payload["exit_code"] == 0, result.stderr[-1000:]
    assert payload["status"] == "success"
    files = {p.relative_to(scratch / "conversion").as_posix(): p.stat().st_size
             for p in (scratch / "conversion").rglob("*") if p.is_file()}
    return payload, files, int(peak_path.read_text())


def _scratch():
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    return TemporaryDirectory(prefix="mem03-", dir=work)


@pytest.mark.parametrize("name", ["A7-Blues-Lick.pdf", "Lesson-3.pdf"])
def test_inspection_is_written_once(name):
    with _scratch() as directory:
        _, files, _ = _convert(name, Path(directory))
        assert [f for f in files if f.endswith("inspect_pdf.json")] == ["inspect/inspect_pdf.json"]
        assert not [f for f in files if f.startswith("tab/inspect")], "second inspection written"
        pages = [f for f in files if f.endswith(".png") and "/pages/" in f]
        assert pages and all(f.startswith("inspect/pages/") for f in pages)


def test_heavy_diagnostics_are_opt_in():
    with _scratch() as directory, _scratch() as opted:
        _, default_files, _ = _convert("A7-Blues-Lick.pdf", Path(directory))
        heavy = [f for f in default_files
                 if f.startswith("tab/overlays") or f in ("tab/grouping-diagnostics.html",)
                 or f.startswith("tab/pdf-edge-boundary-report")]
        assert not heavy, "heavy diagnostics written by default"
        _, flagged, _ = _convert("A7-Blues-Lick.pdf", Path(opted), "--diagnostic-artifacts")
        assert "tab/grouping-diagnostics.html" in flagged
        assert any(f.startswith("tab/overlays/") for f in flagged)
        # The flag adds files only; the single inspection copy is unchanged.
        assert not [f for f in flagged if f.startswith("tab/inspect")]
        assert set(default_files) <= set(flagged)


@pytest.mark.parametrize("name", sorted(BUDGETS))
def test_bytes_per_bar_and_peak_memory_budget(name):
    max_bytes_per_bar, max_peak = BUDGETS[name]
    with _scratch() as directory:
        payload, files, peak = _convert(name, Path(directory))
        bars = payload["summary_counts"]["bar_count"]
        assert bars > 0
        total = sum(files.values())
        assert total / bars <= max_bytes_per_bar, f"{total} bytes over {bars} bars"
        assert peak <= max_peak, f"peak working set {peak}"


def test_peak_reading_is_the_childs_not_the_spawning_process():
    # Rejects reading ru_maxrss in the child on Linux, which is inherited across
    # fork+exec and so reports the pytest process's high-water mark (the CI failure).
    ballast = bytearray(b"x" * 700_000_000)  # touched, raises this process's peak
    with _scratch() as directory:
        peak_path = Path(directory) / "peak.txt"
        subprocess.run(
            [sys.executable, "-c", RUN_WITH_PEAK, "--help"], capture_output=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "MEM03_PEAK": str(peak_path)})
        child_peak = int(peak_path.read_text())
    assert len(ballast) and 0 < child_peak < 500_000_000, child_peak
