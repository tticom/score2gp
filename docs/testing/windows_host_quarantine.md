# Windows host test quarantine (FND-06)

Baseline measured 2026-10-28 on the Windows author host: 14 failed, 2210 passed,
1 skipped, 1 xfailed (the pre-existing xfail is unrelated). 16 were recorded in
2026-09; 14 remained, one was fixed here, 13 are quarantined.

## Fixed

- `tests/test_raster_diagnostics_gate_report.py::test_subprocess_test_manifest_rejects_absolute_without_leaking`:
  on Windows `/etc/passwd` has no drive so `Path.is_absolute()` is false and the
  unsafe manifest path was accepted. `scripts/raster_diagnostics_gate_report.py`
  now also rejects any path with a root or drive anchor (stricter, not looser).

## Quarantined (strict xfail, exact node ID, Windows only)

All 13 `tests/test_omr_contract.py::test_omr_artifact_contract_*` tests that
build a `#!/bin/bash` mock Audiveris (IDs listed in
`tests/windows_host_quarantine.py`). Cause: CreateProcess cannot run a shell
script (WinError 193), so `score2gp omr` returns an execution error instead of
the contract outcome under test.

Expiry condition: remove an ID when its test uses a host-portable mock launcher.
The xfail is strict, so a quarantined test that passes fails the suite until it
is removed from the list. The marks apply only when `sys.platform == "win32"`;
Linux CI still runs these tests as normal passes.
