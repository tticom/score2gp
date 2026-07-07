#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time

def run_step(name, cmd):
    print(f"Running step: {name} ({' '.join(cmd) if isinstance(cmd, list) else cmd})...")
    start_time = time.time()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - start_time
        return {
            "name": name,
            "command": " ".join(cmd) if isinstance(cmd, list) else cmd,
            "exit_code": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "elapsed_seconds": round(elapsed, 2),
            "status": "PASS" if res.returncode == 0 else "FAIL"
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "name": name,
            "command": " ".join(cmd) if isinstance(cmd, list) else cmd,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "elapsed_seconds": round(elapsed, 2),
            "status": "FAIL"
        }

def make_markdown_report(results, overall_status):
    lines = []
    lines.append("# Score2GP Verification Report")
    lines.append(f"\n**Overall Status**: {'🟢 PASS' if overall_status == 'PASS' else '🔴 FAIL'}")
    lines.append(f"**Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("| Verification Step | Status | Exit Code | Time |")
    lines.append("| :--- | :--- | :--- | :--- |")
    for r in results:
        status_icon = "🟢 PASS" if r["status"] == "PASS" else "🔴 FAIL"
        lines.append(f"| {r['name']} | {status_icon} | {r['exit_code']} | {r['elapsed_seconds']}s |")
    
    lines.append("\n## Step Details\n")
    for r in results:
        lines.append(f"### {r['name']}")
        lines.append(f"- **Command**: `{r['command']}`")
        lines.append(f"- **Status**: {r['status']}")
        lines.append(f"- **Exit Code**: {r['exit_code']}")
        lines.append(f"- **Time**: {r['elapsed_seconds']}s")
        if r["stdout"].strip():
            lines.append("\n**Stdout**:")
            lines.append("```text")
            lines.append(r["stdout"].strip())
            lines.append("```")
        if r["stderr"].strip():
            lines.append("\n**Stderr**:")
            lines.append("```text")
            lines.append(r["stderr"].strip())
            lines.append("```")
        lines.append("\n---")
    return "\n".join(lines)

# Default verification steps list
STEPS = [
    ("Run pytest", [sys.executable, "-m", "pytest"]),
    ("Export schemas", [sys.executable, "-m", "score2gp.cli", "export-schema", "--out", "schemas"]),
    ("Validate IR on tiny_score", [sys.executable, "-m", "score2gp.cli", "validate-ir", "fixtures/public/tiny_score.ir.json"]),
    ("Artifact audit", [sys.executable, "scripts/artifact_audit.py"]),
    ("Git check diff", ["git", "diff", "--check"]),
    ("Git schema diff", ["git", "diff", "--", "schemas"]),
    ("Git status short", ["git", "status", "--short"]),
]

def main():
    parser = argparse.ArgumentParser(description="Run Score2GP agent verification suite.")
    parser.add_argument("--keep-going", action="store_true", help="Continue running verification checks even if one fails.")
    args = parser.parse_args()

    os.makedirs("work", exist_ok=True)
    results = []
    overall_status = "PASS"

    for name, cmd in STEPS:
        res = run_step(name, cmd)
        results.append(res)
        if res["status"] == "FAIL":
            overall_status = "FAIL"
            if not args.keep_going:
                print(f"\nStep failed: {name}. Failing fast.")
                break

    # Write verify JSON
    verify_data = {
        "timestamp": time.time(),
        "overall_status": overall_status,
        "results": results
    }
    with open("work/agent_verify.json", "w", encoding="utf-8") as f:
        json.dump(verify_data, f, indent=2)

    # Write verify Markdown
    markdown_report = make_markdown_report(results, overall_status)
    with open("work/agent_verify.md", "w", encoding="utf-8") as f:
        f.write(markdown_report)

    print(f"\nVerification finished. Overall status: {overall_status}")
    print("Report written to work/agent_verify.json and work/agent_verify.md")
    
    if overall_status == "FAIL":
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
