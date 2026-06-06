# Testing Guide

This document describes the test suite, diagnostic audits, and verification procedures required to ensure the stability and correctness of `score2gp`.

## Test Commands and Verification Stages

### 1. Public Test Suite
* **Command**:
  ```bash
  PYTHONPATH=. .venv/bin/python3 -m pytest
  ```
* **Description**: Runs all public unit and integration tests (including the synthetic E2E pipeline proofs).
* **Proves**: That core parsing, ScoreIR models, GPIF serialization, and layout algorithms are structurally correct and free of regression.
* **Expected Result**: 467 tests passed.

### 2. Local Private-Safe E2E Smoke Pass
* **Command**:
  ```bash
  PYTHONPATH=. .venv/bin/python3 scripts/private_e2e_smoke.py
  ```
* **Description**: Runs the E2E extraction and alignment pipeline against all private score PDFs and matching sidecars in `fixtures/private/`. It generates a sanitized, redacted master summary under `work/private_e2e_smoke_v0_1/`.
* **Proves**: That the candidate extraction and alignment gates execute without crashing against real-world scores.
* **Expected Result**: Clean run execution with a generated master summary file.

### 3. Post-Serialization GP Quality Audit
* **Command**:
  ```bash
  PYTHONPATH=. .venv/bin/python3 scripts/private_gp_quality_audit.py
  ```
* **Description**: Checks the serialized `.gp` files for matched candidate counts and quality categorization.
* **Proves**: That the output `.gp` packages contain the correct number of notes and techniques compared to the input specification.
* **Expected Result**: Outputs a master quality table where verified scores show `pass` and unsupported files fail cleanly.

### 4. Private-Safety Invariant Check
* **Command**:
  ```bash
  git ls-files fixtures/private work
  ```
* **Description**: Checks if any local private scores or generated outputs are being tracked by Git.
* **Proves**: That no proprietary or copyrighted material is accidentally added to version control.
* **Expected Result**: Must output exactly:
  ```text
  fixtures/private/.gitkeep
  ```

### 5. Git Diff Hygiene Check
* **Command**:
  ```bash
  git diff --check
  ```
* **Description**: Scans changes for whitespace errors, trailing spaces, or conflict markers.
* **Proves**: That commit formatting remains clean and compliant.
* **Expected Result**: No output (exit code 0).

---

## PR Evidence Requirements

Any Pull Request modifying the codebase must include a verification report in the PR description containing the following details:

1. **Commands Run**: The exact terminal commands executed to verify the change.
2. **Test Results**: The number of passing test cases.
3. **Audit Outcomes**: High-level status of the private smoke pass and quality audits.
4. **Safety Verification**: The exact stdout output of the private-safety invariant command.
5. **Known Limitations**: Any scope constraints or limitations associated with the patch.
