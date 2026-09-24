# Repository virtualenv on Windows or POSIX, else python on PATH; no shell needed.
PYTHON ?= $(firstword $(wildcard .venv/Scripts/python.exe .venv/bin/python) python)
TEST ?= tests/test_notation_bridge.py
TITLE ?= [PR Title]
SUMMARY ?= [PR Summary]
LIMITATIONS ?= None.
FOCUS ?= Verification and correctness checks.

.PHONY: verify audit pr-body quick

verify:
	$(PYTHON) scripts/agent_verify.py

audit:
	$(PYTHON) scripts/artifact_audit.py

pr-body:
	$(PYTHON) scripts/pr_body.py --title "$(TITLE)" --summary "$(SUMMARY)" --limitations "$(LIMITATIONS)" --review-focus "$(FOCUS)"

quick:
	$(PYTHON) -m pytest $(TEST)
