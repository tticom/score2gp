#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys

def run_cmd(args):
    try:
        res = subprocess.run(args, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return ""

def main():
    parser = argparse.ArgumentParser(description="Gather Score2GP repository status.")
    parser.add_argument("--json", action="store_true", help="Output status in JSON format.")
    args = parser.parse_args()

    repo_url = run_cmd(["git", "config", "--get", "remote.origin.url"])
    branch = run_cmd(["git", "branch", "--show-current"])
    if not branch:
        branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    head_sha = run_cmd(["git", "rev-parse", "HEAD"])
    
    # Base branch
    base_branch = "main"
    
    # Working tree status
    status_porcelain = run_cmd(["git", "status", "--porcelain"])
    working_tree_clean = (status_porcelain == "")
    working_tree_status = "Clean" if working_tree_clean else "Dirty"

    # Recent commits
    recent_commits = run_cmd(["git", "log", "--oneline", "-5"]).splitlines()

    # Schema diff
    schema_diff = run_cmd(["git", "diff", "--name-only", "schemas/"])
    schema_changed = (schema_diff != "")

    # Artifact audit (programmatic)
    try:
        audit_res = subprocess.run([sys.executable, "scripts/artifact_audit.py"], capture_output=True, text=True)
        audit_pass = (audit_res.returncode == 0)
        audit_output = audit_res.stdout.strip() if audit_pass else audit_res.stdout.strip() + "\n" + audit_res.stderr.strip()
    except Exception as e:
        audit_pass = False
        audit_output = str(e)

    # Saved pytest run check
    saved_pytest_summary = "No saved verification run found. Run python scripts/agent_verify.py first."
    pytest_status = "Unknown"
    saved_verify_path = "work/agent_verify.json"
    if os.path.exists(saved_verify_path):
        try:
            with open(saved_verify_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Find pytest step
            pytest_step = None
            for step in data.get("results", []):
                if step.get("name") == "Run pytest":
                    pytest_step = step
                    break
            if pytest_step:
                pytest_status = pytest_step.get("status", "Unknown")
                elapsed = pytest_step.get("elapsed_seconds", 0)
                if pytest_status == "PASS":
                    saved_pytest_summary = f"🟢 Pytest passed in {elapsed}s"
                else:
                    saved_pytest_summary = f"🔴 Pytest failed in {elapsed}s"
            else:
                saved_pytest_summary = "Pytest run data missing from saved verify run."
        except Exception as e:
            saved_pytest_summary = f"Error reading saved verify run: {e}"

    status_data = {
        "repository": repo_url,
        "branch": branch,
        "head_sha": head_sha,
        "base_branch": base_branch,
        "working_tree": working_tree_status,
        "recent_commits": recent_commits,
        "schema_changed": schema_changed,
        "artifact_audit": "PASS" if audit_pass else "FAIL",
        "pytest_status": pytest_status,
        "pytest_summary": saved_pytest_summary,
    }

    if args.json:
        print(json.dumps(status_data, indent=2))
        return

    # Print Markdown status
    print("# Score2GP Agent Repository Status\n")
    print(f"- **Repository**: `{repo_url}`")
    print(f"- **Current Branch**: `{branch}`")
    print(f"- **Base Branch**: `{base_branch}`")
    print(f"- **Head SHA**: `{head_sha}`")
    print(f"- **Working Tree**: `{working_tree_status}`")
    print(f"- **Schema Changed**: `{schema_changed}`")
    print(f"- **Artifact Audit**: `{'🟢 PASS' if audit_pass else '🔴 FAIL'}`")
    print(f"- **Pytest Status**: `{saved_pytest_summary}`")
    
    print("\n## Recent Commits")
    for commit in recent_commits:
        print(f"- {commit}")
    
    if not audit_pass:
        print("\n## Artifact Audit Failure Details")
        print("```text")
        print(audit_output)
        print("```")

if __name__ == "__main__":
    main()
