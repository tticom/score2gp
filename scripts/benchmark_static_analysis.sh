#!/bin/bash
set -e

echo "=== Static Analysis Evaluation Packet ==="
echo "OS/Runtime: $(uname -a)"
echo "Python Version: $(python3 --version)"
echo "Ruff Version: $(ruff --version)"
echo "Pylint Version: $(pylint --version | head -n 1)"
echo "Source SHA: $(git rev-parse HEAD)"
echo ""

echo "--- Benchmarking Ruff ---"
rm -f ruff_output.txt
set +e
time ruff check src/ tests/ > ruff_output.txt 2>&1
RUFF_EXIT=$?
set -e
echo "Ruff Exit Code: $RUFF_EXIT"
echo "Ruff Raw Output Digest (SHA256): $(sha256sum ruff_output.txt | awk '{print $1}')"
echo ""

echo "--- Benchmarking Pylint ---"
rm -f pylint_output.txt
set +e
time pylint src/ tests/ > pylint_output.txt 2>&1
PYLINT_EXIT=$?
set -e
echo "Pylint Exit Code: $PYLINT_EXIT"
echo "Pylint Raw Output Digest (SHA256): $(sha256sum pylint_output.txt | awk '{print $1}')"
