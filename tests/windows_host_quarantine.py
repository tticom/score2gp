"""Exact-ID strict-xfail quarantine for tests that cannot pass on a Windows host.

Reason record: docs/testing/windows_host_quarantine.md (FND-06).
Matching is by exact pytest node ID only: no wildcards, no skips, no deselection.
Every entry still runs and is reported as XFAIL by name; because the mark is
strict, an entry that starts passing fails the suite until it is removed.
"""
import sys

import pytest

REASON_RECORD = "docs/testing/windows_host_quarantine.md"

# Cause: the tests write a '#!/bin/bash' mock Audiveris executable; CreateProcess
# rejects it (WinError 193), so the CLI reports an error instead of the contract
# outcome. Expiry: remove the ID once the mock launcher is host-portable.
QUARANTINED_IDS = frozenset({
    "tests/test_omr_contract.py::test_omr_artifact_contract_success",
    "tests/test_omr_contract.py::test_omr_artifact_contract_failed_exec_with_pre_existing_xml",
    "tests/test_omr_contract.py::test_omr_artifact_contract_success_exec_no_files",
    "tests/test_omr_contract.py::test_omr_artifact_contract_escaped_symlink",
    "tests/test_omr_contract.py::test_omr_artifact_contract_nested_valid_xml",
    "tests/test_omr_contract.py::test_omr_artifact_contract_valid_mxl",
    "tests/test_omr_contract.py::test_omr_artifact_contract_mxl_malformed_container",
    "tests/test_omr_contract.py::test_omr_artifact_contract_mxl_missing_rootfile",
    "tests/test_omr_contract.py::test_omr_artifact_contract_mxl_invalid_inner_score",
    "tests/test_omr_contract.py::test_omr_artifact_contract_ambiguous",
    "tests/test_omr_contract.py::test_omr_artifact_contract_malformed_plain_xml",
    "tests/test_omr_contract.py::test_omr_artifact_contract_unsupported_root_xml",
    "tests/test_omr_contract.py::test_omr_artifact_contract_valid_score_timewise",
})


def apply_quarantine(items, platform=sys.platform):
    if platform != "win32":
        return
    for item in items:
        if item.nodeid in QUARANTINED_IDS:
            item.add_marker(
                pytest.mark.xfail(
                    strict=True,
                    reason=f"windows-host quarantine (FND-06); see {REASON_RECORD}",
                )
            )
