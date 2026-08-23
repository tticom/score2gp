#!/bin/bash
set -e

echo "=== Static Analysis Evaluation Packet ==="
echo "OS/Runtime: $(uname -a)"
echo "Python Version: $(.venv/bin/python --version)"
echo "Ruff Version: $(.venv/bin/ruff --version)"
echo "Pylint Version: $(.venv/bin/pylint --version | head -n 1)"
echo "Source SHA: $(git rev-parse HEAD)"
echo ""

echo "--- Benchmarking Ruff ---"
rm -f ruff_output.txt
set +e
time .venv/bin/ruff check src/ tests/ > ruff_output.txt 2>&1
RUFF_EXIT=$?
set -e
echo "Ruff Exit Code: $RUFF_EXIT"
echo "Ruff Raw Output Digest (SHA256): $(sha256sum ruff_output.txt | awk '{print $1}')"
echo ""

echo "--- Benchmarking Pylint ---"
rm -f pylint_output.txt
set +e
time .venv/bin/pylint src/ tests/ > pylint_output.txt 2>&1
PYLINT_EXIT=$?
set -e
echo "Pylint Exit Code: $PYLINT_EXIT"
echo "Pylint Raw Output Digest (SHA256): $(sha256sum pylint_output.txt | awk '{print $1}')"
echo ""

