"""Enforce read-only private inputs and required-corpus skip policy.

This pytest infrastructure makes no domain claim.
"""

import os
import re
import hashlib
from pathlib import Path
import sys

import pytest


PRIVATE_REASONS = frozenset({
    "private source is not mounted",
    "private Lesson-3 corpus not mounted",
    "private corpus absent",
    "mounted private corpus is unavailable: Melodic Soloing Masterclass.pdf",
    "Lesson-7.pdf required for this private-fixture acceptance test.",
    "private lesson corpus absent",
    "private repeat corpus absent",
    "Lesson-5.pdf required for this private-fixture acceptance test.",
    "Lesson-6.pdf required for this private-fixture acceptance test.",
    "mounted private corpus is unavailable",
})
# The two f-string sites in the census vary only in their missing-name suffix.
PRIVATE_PATTERNS = (
    re.compile(r"private corpus not mounted: .+"),
    re.compile(r"Lesson-6\.pdf required to generate Lesson-6_(?:unowned|invalid)_artifact\.json"),
)
LEGITIMATE_REASONS = frozenset({
    "requires the Windows provider",
    "windows-file-lock is the only provider; off-Windows the harness refuses (asserted in the test above)",
    # This is a separately built local oracle, not a file in the mounted corpus.
    "private adjudicated manifest is not mounted (local ignored artefact: build it with "
    "scripts/native_slice_reference.py build-manifest, or set SCORE2GP_L3_ORACLE); without it the harness "
    "refuses to run, which is asserted in test_native_slice_acceptance.py",
})


def classify(reason):
    if reason in PRIVATE_REASONS or any(p.fullmatch(reason) for p in PRIVATE_PATTERNS):
        return "private-corpus"
    if reason in LEGITIMATE_REASONS:
        return "legitimate"
    return "unrecognised"


class PrivateCorpusGuard:
    def __init__(self):
        self.skips = {}

    def record(self, report):
        if report.skipped and not getattr(report, "wasxfail", False):
            reason = str(report.longrepr[2])
            if reason.startswith("Skipped: "):
                reason = reason[len("Skipped: "):]
            self.skips[(report.nodeid, reason)] = classify(reason)

    def pytest_runtest_logreport(self, report):
        self.record(report)

    def pytest_collectreport(self, report):
        self.record(report)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if "private-corpus" in self.skips.values() and exitstatus in (
            pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED,
        ):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

    def pytest_terminal_summary(self, terminalreporter):
        count = sum(value == "private-corpus" for value in self.skips.values())
        terminalreporter.write_sep("=", f"private-corpus skips: {count} (required)")
        for (nodeid, reason), classification in sorted(self.skips.items()):
            terminalreporter.write_line(f"[{classification}] {nodeid}: {reason}")


def pytest_configure(config):
    config.pluginmanager.register(CorpusWriteGuard(config), "private-corpus-write-guard")
    if os.environ.get("SCORE2GP_REQUIRE_PRIVATE_CORPUS") == "1":
        config.pluginmanager.register(PrivateCorpusGuard(), "private-corpus-skip-guard")


def pytest_addoption(parser):
    parser.addini("private_corpus_roots", "Protected corpus roots (infrastructure probes may override)",
                  type="linelist", default=[])


class CorpusWriteGuard:
    """Block Python mutations and detect persistent writes by child processes.

    The audit hook also catches identical overwrites and create/delete attempts
    that a final hash comparison alone would miss. It is inert after this run.
    """

    def __init__(self, config):
        root = Path(__file__).resolve().parent.parent
        self.roots = tuple(Path(p).resolve() for p in (
            config.getini("private_corpus_roots") or
            [root / "fixtures/private", root.parent / "score2gp-private-fixtures"]
        ))
        self.active = False
        self.writes = set()
        self.nodeid = "collection"

    def snapshot(self):
        return {
            (index, path.relative_to(root).as_posix()): hashlib.sha256(path.read_bytes()).hexdigest()
            for index, root in enumerate(self.roots)
            for path in root.rglob("*") if path.is_file()
        }

    def audit(self, event, args):
        if not self.active:
            return
        paths = ()
        if event == "open":
            path, mode, flags = args
            if (mode and any(c in mode for c in "wax+")) or flags & (
                os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
            ):
                paths = (path,)
        elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime", "os.truncate"}:
            paths = args[:1]
        elif event in {"os.rename", "os.link"}:
            paths = args[:2]
        elif event == "os.symlink":
            paths = args[1:2]
        for path in paths:
            if isinstance(path, (str, bytes, os.PathLike)):
                resolved = Path(os.fsdecode(path)).resolve()
                if any(resolved.is_relative_to(root) for root in self.roots):
                    self.writes.add(self.nodeid)
                    raise PermissionError("private-corpus writes: forbidden; use tmp_path or work")

    @pytest.hookimpl(tryfirst=True)
    def pytest_sessionstart(self, session):
        self.before = self.snapshot()
        sys.addaudithook(self.audit)
        self.active = True

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item):
        self.nodeid = item.nodeid

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        after = self.snapshot()
        self.changed = sum(self.before.get(key) != after.get(key)
                           for key in self.before.keys() | after.keys())
        if self.writes or self.changed:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("=", f"private-corpus writes: {len(self.writes)} blocked; "
                                  f"{self.changed} files changed")
        for nodeid in sorted(self.writes):
            terminalreporter.write_line(nodeid)

    def pytest_unconfigure(self, config):
        self.active = False
