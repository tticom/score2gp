"""Fail mandatory corpus runs on the source-availability reasons censused in tests/.

This pytest plugin measures skip outcomes only; it makes no domain claim.
"""

import os
import re

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
    if os.environ.get("SCORE2GP_REQUIRE_PRIVATE_CORPUS") == "1":
        config.pluginmanager.register(PrivateCorpusGuard(), "private-corpus-skip-guard")
