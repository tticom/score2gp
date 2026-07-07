from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import pytest

# Add scripts to sys.path so we can import from them
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import agent_status
import agent_verify
import pr_body


def test_agent_verify_run_step() -> None:
    # Test execution helper run_step with basic commands
    res = agent_verify.run_step("Echo check", [sys.executable, "-c", "print('hello')"])
    assert res["status"] == "PASS"
    assert "hello" in res["stdout"]
    assert res["exit_code"] == 0

    res_fail = agent_verify.run_step("Fail check", [sys.executable, "-c", "import sys; sys.exit(42)"])
    assert res_fail["status"] == "FAIL"
    assert res_fail["exit_code"] == 42


def test_agent_verify_report_generation(tmp_path, monkeypatch) -> None:
    # Test agent_verify writing reports correctly
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["agent_verify.py"])
    
    results = [
        {"name": "Step 1", "command": "cmd1", "exit_code": 0, "stdout": "out1", "stderr": "", "elapsed_seconds": 1.2, "status": "PASS"},
        {"name": "Step 2", "command": "cmd2", "exit_code": 1, "stdout": "", "stderr": "err2", "elapsed_seconds": 0.5, "status": "FAIL"},
    ]

    # Generate Markdown
    md_content = agent_verify.make_markdown_report(results, "FAIL")
    assert "Score2GP Verification Report" in md_content
    assert "🔴 FAIL" in md_content
    assert "Step 1" in md_content
    assert "Step 2" in md_content

    # Mock steps run
    monkeypatch.setattr(agent_verify, "run_step", lambda name, cmd: results[0])
    
    # Override steps to be minimal
    monkeypatch.setattr(agent_verify, "STEPS", [("Step 1", ["echo"])])

    # Run main and verify files written
    try:
        agent_verify.main()
    except SystemExit as e:
        # It fails fast or fails overall since step 1 returns PASS but we can check if file is written
        pass

    assert (tmp_path / "work/agent_verify.json").exists()
    assert (tmp_path / "work/agent_verify.md").exists()


def test_agent_status_reporting(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    
    # Mock Git CLI results
    def mock_run_cmd(args):
        if "remote.origin.url" in args:
            return "https://github.com/tticom/score2gp.git"
        if "show-current" in args:
            return "feature/automation-test"
        if "rev-parse" in args:
            if "--abbrev-ref" in args:
                return "feature/automation-test"
            return "abc123sha"
        if "porcelain" in args:
            return ""
        if "log" in args:
            return "sha1 Commit 1\nsha2 Commit 2"
        if "diff" in args:
            return ""
        return ""

    monkeypatch.setattr(agent_status, "run_cmd", mock_run_cmd)

    # Write a mock verify run JSON file
    os.makedirs(tmp_path / "work", exist_ok=True)
    verify_data = {
        "overall_status": "PASS",
        "results": [
            {"name": "Run pytest", "status": "PASS", "elapsed_seconds": 10.5}
        ]
    }
    with open(tmp_path / "work/agent_verify.json", "w") as f:
        json.dump(verify_data, f)

    # Run agent_status main with json output
    monkeypatch.setattr(sys, "argv", ["agent_status.py", "--json"])
    agent_status.main()
    captured = capsys.readouterr()
    
    status_json = json.loads(captured.out)
    assert status_json["branch"] == "feature/automation-test"
    assert status_json["head_sha"] == "abc123sha"
    assert status_json["pytest_status"] == "PASS"


def test_pr_body_generation(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    # Write mock verify md
    os.makedirs(tmp_path / "work", exist_ok=True)
    with open(tmp_path / "work/agent_verify.md", "w") as f:
        f.write("🟢 Run pytest passed")

    # Mock git changed files
    monkeypatch.setattr(pr_body, "run_cmd", lambda args: "file1.py\nfile2.py")

    monkeypatch.setattr(sys, "argv", [
        "pr_body.py",
        "--title", "Restore boundary",
        "--summary", "Fixed issues with boundary.",
        "--limitations", "None expected.",
        "--review-focus", "Verify git status hygiene."
    ])

    pr_body.main()
    captured = capsys.readouterr()

    assert "# Restore boundary" in captured.out
    assert "Fixed issues with boundary." in captured.out
    assert "file1.py" in captured.out
    assert "🟢 Run pytest passed" in captured.out
    assert "Verify git status hygiene." in captured.out
