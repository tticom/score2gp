#!/usr/bin/env python3
"""Real-source native acceptance coordinator for the L3-NATIVE (Lesson 3) slice.

It runs the actual ``score2gp convert`` command on a staged, byte-identical, renamed copy of the original
PDF inside an enforced read boundary, then judges the result against a private, source-adjudicated
manifest using the independent reader in ``native_slice_reference``. It never imports ``score2gp``.

Two verdicts are reported separately and must never be conflated:

* ``HARNESS_VERIFIED`` / ``HARNESS_REFUSED``: whether this run was a trustworthy measurement
  (valid oracle, matching source hash, fresh output, proven isolation, controlled runtime).
* ``L3_NATIVE_NOT_ACHIEVED`` / ``L3_NATIVE_SEMANTIC_PASS``: whether the product met the milestone.
  A refused conversion is ``NOT_CONVERTED`` and every downstream check is ``NOT_EVALUATED``.

Exit status: 0 only if the product milestone is achieved (never true while the Guitar Pro application
check is ``NOT_EVALUATED``); 1 for a verified-red measurement; 2 when the harness refused to measure.

Isolation is explicit and recorded, never assumed. ``--isolation windows-file-lock`` holds exclusive
share-mode handles on the oracle, the sentinel and every ``--protect`` path for the whole generation
run, so the generation process cannot open them. This protects *named files only*; it is not a
whitelist filesystem (see ``ISOLATION_LIMITS``). No provider means no run.

    python scripts/native_slice_acceptance.py --pdf <original.pdf> --oracle <manifest.json> \\
        --out-dir <new-private-dir> --isolation windows-file-lock [--protect <reference.gp>]
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_slice_reference as reference  # noqa: E402  (sibling script, resolved after sys.path change)

RECEIPT_SCHEMA = "native-slice-acceptance-receipt.v0.1"
ISOLATION_PROVIDERS = ("windows-file-lock",)
ISOLATION_LIMITS = {
    "windows-file-lock": "named files only (blacklist); other copies of the reference are not protected; not a whitelist filesystem or container",
}
TARGET_ARGS = ["--pdf-only-tab", "--require-precise-timing", "--strict"]
CHILD_ENV_KEYS = ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC")
DEFAULT_TIMEOUT_SECONDS = 1200

EXIT_ACHIEVED, EXIT_RED, EXIT_REFUSED = 0, 1, 2


class HarnessRefused(RuntimeError):
    """The harness will not measure (as opposed to a product that measured red)."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ------------------------------------------------------------------------------------ isolation


@contextmanager
def windows_file_lock(paths: list[Path]) -> Iterator[None]:
    """Hold exclusive (share mode 0) read handles so no other process can open the files."""
    if os.name != "nt":
        raise HarnessRefused("ISOLATION_UNAVAILABLE", "windows-file-lock requires Windows")
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    invalid = wintypes.HANDLE(-1).value
    handles = []
    try:
        for path in paths:
            handle = kernel32.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
            if handle in (None, invalid):
                raise HarnessRefused("ISOLATION_LOCK_FAILED", f"could not lock {path.name} (error {ctypes.get_last_error()})")
            handles.append(handle)
        yield
    finally:
        for handle in handles:
            kernel32.CloseHandle(handle)


def child_env(product_root: Path, tmp_dir: Path, sentinel: Path) -> dict[str, str]:
    """A minimal environment for the generation process. It carries no oracle or reference path."""
    env = {key: os.environ[key] for key in CHILD_ENV_KEYS if key in os.environ}
    env.update({
        "PYTHONPATH": str(product_root / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "TEMP": str(tmp_dir),
        "TMP": str(tmp_dir),
        "SCORE2GP_SENTINEL_REFERENCE": str(sentinel),
    })
    return env


def probe_boundary(python: str, env: dict[str, str], cwd: Path, protected: list[Path], control: Path) -> dict[str, Any]:
    """Prove the boundary by trying to read protected files from inside it; the staged PDF is the control."""
    code = "import sys; open(sys.argv[1], 'rb').read(1)"
    blocked = []
    for path in protected:
        result = subprocess.run([python, "-c", code, str(path)], env=env, cwd=cwd, capture_output=True, timeout=60)
        blocked.append(result.returncode != 0)
    control_ok = subprocess.run([python, "-c", code, str(control)], env=env, cwd=cwd, capture_output=True, timeout=60).returncode == 0
    return {"protected_count": len(protected), "all_unreadable": all(blocked) and bool(blocked), "control_readable": control_ok}


# ------------------------------------------------------------------------------------ provenance


def runtime_provenance(python: str, env: dict[str, str], product_root: Path, cwd: Path) -> dict[str, Any]:
    """Record which score2gp the generation process would import. Anything outside the checkout is uncontrolled."""
    probe = subprocess.run(
        [python, "-c", "import pathlib, score2gp; print(pathlib.Path(score2gp.__file__).resolve())"],
        env=env, cwd=cwd, capture_output=True, text=True, timeout=120,
    )
    import_path = probe.stdout.strip()
    controlled = probe.returncode == 0 and bool(import_path)
    if controlled:
        try:
            Path(import_path).relative_to((product_root / "src").resolve())
        except ValueError:
            controlled = False
    commit = subprocess.run(["git", "-C", str(product_root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(product_root), "status", "--porcelain=v1", "--untracked-files=all"],
                           capture_output=True, text=True).stdout.strip()
    return {"import_path_controlled": controlled, "product_head": commit, "product_tree_clean": not dirty,
            "python_version": subprocess.run([python, "-c", "import sys; print(sys.version.split()[0])"], capture_output=True, text=True).stdout.strip()}


# --------------------------------------------------------------------------------- classification


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def classify_generation(gen: Path, exit_code: int | None, started: float, manifest: dict[str, Any]) -> dict[str, Any]:
    """Classify the conversion. A refusal is NOT_CONVERTED and everything downstream is NOT_EVALUATED."""
    result_path = gen / "result.gp"
    report = read_json(gen / "report.json") or {}
    if exit_code is None:
        return {"conversion": "CONVERSION_TIMED_OUT", "semantic": "NOT_EVALUATED", "application": "NOT_EVALUATED",
                "refusal_code": None, "exit_code": None}
    converted = exit_code == 0 and result_path.is_file()
    stale = converted and result_path.stat().st_mtime < started
    outcome: dict[str, Any] = {
        "exit_code": exit_code, "refusal_code": report.get("refusal_code"), "stage": report.get("stage"),
        "output_written": result_path.is_file(), "application": "NOT_EVALUATED",
    }
    if not converted or stale:
        outcome.update({"conversion": "STALE_OUTPUT" if stale else "NOT_CONVERTED", "semantic": "NOT_EVALUATED"})
        return outcome
    if reference.file_sha256(result_path) == manifest["source"]["gp_sha256"]:
        outcome.update({"conversion": "CONTAMINATED_REFERENCE_ALIAS", "semantic": "NOT_EVALUATED"})
        return outcome
    try:
        comparison = reference.compare(manifest["reference"], reference.expand(reference.read_gpif(result_path)))
    except reference.ReferenceError as error:
        outcome.update({"conversion": "CONVERTED", "semantic": "UNREADABLE_OUTPUT", "semantic_error_code": error.code})
        return outcome
    outcome.update({"conversion": "CONVERTED", "semantic": "PASS" if comparison["equal"] else "FAIL",
                    "layers": comparison["layers"], "first_divergence_location": _location(comparison["first_divergence"])})
    return outcome


def _location(divergence: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if divergence is None else {k: v for k, v in divergence.items() if k not in ("expected", "actual")}


def first_system_divergence(manifest: dict[str, Any], gen: Path) -> dict[str, Any]:
    """Compare the barline topology the product itself reported for the first system with the adjudicated source.

    This reads only the product's own diagnostic artefact, never the reference, and yields counts
    (public) plus coordinates (private).
    """
    first = manifest["adjudication"]["first_system"]
    tab_raw = read_json(gen / "intermediates" / "tab" / "tab_raw.json")
    if tab_raw is None:
        return {"status": "NOT_EVALUATED", "reason": "tab_raw_absent"}
    y0, y1 = first["tab_staff_y"]
    tolerance = first.get("barline_x_tolerance", 0.6)
    for candidate in tab_raw.get("candidates", []):
        raw = candidate.get("raw", {})
        bbox = raw.get("tab_staff_bbox")
        if candidate.get("page_index") != first["page"] or not bbox or not raw.get("barline_xs"):
            continue
        top = bbox[1] if isinstance(bbox, list) else bbox.get("y0")
        if abs(top - y0) > 3.0:
            continue
        observed = sorted(raw["barline_xs"])
        expected = sorted(first["barline_xs"])
        extra = [x for x in observed if not any(abs(x - e) <= tolerance + 0.5 for e in expected)]
        missing = [e for e in expected if not any(abs(x - e) <= tolerance + 0.5 for x in observed)]
        stems = first.get("notation_full_height_stem_xs", [])
        on_stem = [x for x in extra if any(abs(x - s) <= tolerance + 0.5 for s in stems)]
        boxes = raw.get("bar_boxes") or []
        divergent = bool(extra or missing)
        return {
            "status": "DIVERGENT" if divergent else "TOPOLOGY_MATCHES_SOURCE",
            "kind": "barline_set_mismatch" if divergent else None,
            "counts": {"expected_boundaries": len(expected), "observed_boundaries": len(observed),
                       "extra": len(extra), "missing": len(missing), "extra_on_notation_stem": len(on_stem),
                       "measures_expected": len(first["printed_measures"]), "bar_boxes_observed": len(boxes),
                       "grouping_status": raw.get("grouping_status")},
            "private": {"expected_xs": expected, "observed_xs": observed, "extra_xs": extra, "missing_xs": missing},
        }
    return {"status": "NOT_EVALUATED", "reason": "first_system_not_found_in_product_diagnostics"}


# --------------------------------------------------------------------------------------- run


def prepare_output(out_dir: Path) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise HarnessRefused("OUTPUT_NOT_FRESH", "output directory must not exist or must be empty")
    out_dir.mkdir(parents=True, exist_ok=True)


def run(args: argparse.Namespace, created: list[Path] | None = None) -> tuple[int, dict[str, Any]]:
    """Run one acceptance. ``created`` receives the output directory only once this run has created it,
    so a receipt is never written into a directory the run did not own (for example a stale one)."""
    receipt: dict[str, Any] = {"schema": RECEIPT_SCHEMA, "harness": "HARNESS_REFUSED", "product": "NOT_EVALUATED"}
    created = created if created is not None else []
    try:
        return _run(args, receipt, created)
    except HarnessRefused as refusal:
        receipt.update({"harness": "HARNESS_REFUSED", "harness_refusal": {"code": refusal.code, "detail": refusal.detail},
                        "public_summary": {"harness": "HARNESS_REFUSED", "refusal_code": refusal.code}})
        return EXIT_REFUSED, receipt


def _run(args: argparse.Namespace, receipt: dict[str, Any], created: list[Path]) -> tuple[int, dict[str, Any]]:
    if args.isolation not in ISOLATION_PROVIDERS:
        raise HarnessRefused("ISOLATION_REQUIRED", f"choose one of {', '.join(ISOLATION_PROVIDERS)}; no provider means no run")
    pdf, oracle = Path(args.pdf), Path(args.oracle)
    for label, path in (("pdf", pdf), ("oracle", oracle)):
        if not path.is_file():
            raise HarnessRefused("INPUT_MISSING", label)
    try:
        manifest = json.loads(oracle.read_text(encoding="utf-8"))
        reference.validate_manifest(manifest)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HarnessRefused("ORACLE_UNREADABLE", type(error).__name__) from error
    except reference.ReferenceError as error:
        raise HarnessRefused("ORACLE_INVALID", error.code) from error
    pdf_hash = reference.file_sha256(pdf)
    if pdf_hash != manifest["source"]["pdf_sha256"]:
        raise HarnessRefused("SOURCE_MISMATCH", "pdf does not match the oracle's recorded source hash")
    protect = [Path(p) for p in args.protect]
    for path in protect:
        if not path.is_file():
            raise HarnessRefused("PROTECT_PATH_MISSING", path.name)
    product_root = Path(args.product_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    prepare_output(out_dir)
    created.append(out_dir)

    stage, gen, sentinel_dir, tmp = (out_dir / n for n in ("stage", "gen", "sentinel", "tmp"))
    for directory in (stage, gen, sentinel_dir, tmp):
        directory.mkdir()
    staged = stage / f"{secrets.token_hex(8)}.pdf"
    shutil.copyfile(pdf, staged)
    if reference.file_sha256(staged) != pdf_hash:
        raise HarnessRefused("STAGING_CORRUPT", "staged pdf differs from the original")
    sentinel = sentinel_dir / "reference.sentinel"
    sentinel.write_text(secrets.token_hex(16), encoding="utf-8")

    python = args.python
    env = child_env(product_root, tmp, sentinel)
    provenance = runtime_provenance(python, env, product_root, gen)
    if not provenance["import_path_controlled"]:
        raise HarnessRefused("UNCONTROLLED_RUNTIME", "score2gp does not import from the product checkout")

    protected = [oracle.resolve(), sentinel.resolve(), *[p.resolve() for p in protect]]
    command = [python, "-m", "score2gp.cli", "convert", "--pdf", str(staged), *TARGET_ARGS, "--out", str(gen / "result.gp"),
               "--work-dir", str(gen / "intermediates"), "--json-report", str(gen / "report.json")]
    with windows_file_lock(protected):
        boundary = probe_boundary(python, env, gen, protected, staged)
        if not (boundary["all_unreadable"] and boundary["control_readable"]):
            raise HarnessRefused("ISOLATION_NOT_ENFORCED", "probe could read a protected file or could not read the control")
        started = time.time()
        try:
            completed = subprocess.run(command, env=env, cwd=gen, capture_output=True, timeout=args.timeout)
            exit_code: int | None = completed.returncode
            (gen / "stdout.txt").write_bytes(completed.stdout)
            (gen / "stderr.txt").write_bytes(completed.stderr)
        except subprocess.TimeoutExpired:
            exit_code = None

    outcome = classify_generation(gen, exit_code, started, manifest)
    divergence = first_system_divergence(manifest, gen)
    achieved = outcome["conversion"] == "CONVERTED" and outcome["semantic"] == "PASS" and outcome["application"] == "PASS"
    product = "L3_NATIVE_ACHIEVED" if achieved else (
        "L3_NATIVE_SEMANTIC_PASS_APPLICATION_NOT_EVALUATED" if outcome.get("semantic") == "PASS" else "L3_NATIVE_NOT_ACHIEVED")
    public_divergence = {k: v for k, v in divergence.items() if k != "private"}
    receipt.update({
        "harness": "HARNESS_VERIFIED", "product": product,
        "public_summary": {
            "harness": "HARNESS_VERIFIED", "product": product, "source_pdf_sha256": pdf_hash,
            "oracle_reference_fingerprint": manifest["reference_fingerprint"], "generation": {k: v for k, v in outcome.items()},
            "first_system_divergence": public_divergence,
            "isolation": {"provider": args.isolation, "limits": ISOLATION_LIMITS[args.isolation], **boundary},
            "runtime": provenance, "target_command": ["convert", *TARGET_ARGS],
        },
        "private_detail": {"first_system_divergence": divergence.get("private")},
    })
    return (EXIT_ACHIEVED if achieved else EXIT_RED), receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog="Exit: 0 achieved, 1 verified red, 2 harness refused.")
    parser.add_argument("--pdf", required=True, type=Path, help="original source PDF (never modified)")
    parser.add_argument("--oracle", required=True, type=Path, help="private adjudicated manifest")
    parser.add_argument("--out-dir", required=True, type=Path, help="new, empty private output directory")
    parser.add_argument("--isolation", default=None, choices=ISOLATION_PROVIDERS, help="enforced read-boundary provider (required)")
    parser.add_argument("--protect", action="append", default=[], type=Path, help="extra file the generation process must not read (repeatable)")
    parser.add_argument("--product-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    created: list[Path] = []
    code, receipt = run(args, created)
    for out_dir in created:
        (out_dir / "acceptance-receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(receipt.get("public_summary", {}), indent=1, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
