#!/usr/bin/env python3
import subprocess
import sys

def run_cmd(args):
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return result.stdout.splitlines()

def main():
    print("Running Repository Artifact Audit...")
    try:
        tracked_files = run_cmd(["git", "ls-files"])
    except Exception as e:
        print(f"FAIL: Failed to run git ls-files. Error: {e}")
        sys.exit(1)

    violations = []

    # Banned root generated files
    banned_root_files = {
        "grouping-diagnostics.html",
        "warnings.json",
        "unboxed_recovery_debug.ir.json",
        "unboxed_recovery_debug.tabraw.json",
        "tuning_outside.tabraw.json",
    }

    # Allowed prefixes for json, png, html
    allowed_json_prefixes = ("tests/", "fixtures/public/", "schemas/", ".antigravitycli/")
    allowed_png_prefixes = ("tests/", "reference/")
    allowed_html_prefixes = ("tests/", "docs/")
    generated_json_suffixes = (".ir.json", ".tabraw.json")

    for file in tracked_files:
        # Rule 1: git ls-files fixtures/private work contains anything except fixtures/private/.gitkeep
        if file.startswith("fixtures/private/") and file != "fixtures/private/.gitkeep":
            violations.append((file, "Tracked file in fixtures/private/ (only .gitkeep allowed)"))

        if file.startswith("work/"):
            violations.append((file, "Tracked file in work/ (entire directory must be untracked)"))

        # Rule 2: Root generated files
        if file in banned_root_files:
            violations.append((file, "Tracked generated root artifact"))

        # Rule 3: inspect/ and overlays/ tracked at the root level (outside allowed test paths like tests/fixtures/)
        if file.startswith("inspect/"):
            violations.append((file, "Tracked file in inspect/ (only tests/fixtures/ allowed)"))
        if file.startswith("overlays/"):
            violations.append((file, "Tracked file in overlays/ (only tests/fixtures/ allowed)"))

        # Rule 4: Private fixture extensions in fixtures/private
        if file.startswith("fixtures/private/") and any(file.endswith(ext) for ext in (".pdf", ".gp", ".mxl", ".musicxml")):
            violations.append((file, "Private fixture file tracked in fixtures/private/"))

        # Rule 5: Generated diagnostic HTML/PNG/JSON outputs tracked outside allowlisted folders
        if file.endswith(".json"):
            if file.endswith(generated_json_suffixes) and not any(file.startswith(p) for p in allowed_json_prefixes):
                violations.append((file, "Generated IR/TabRaw JSON tracked outside allowed public fixture directories"))
                continue
            # Check if it starts with allowed prefixes
            if not any(file.startswith(p) for p in allowed_json_prefixes):
                # Allow root config files if any (e.g. package.json)
                if "/" in file:
                    violations.append((file, "JSON file tracked outside allowed directories (tests/, fixtures/public/, schemas/)"))
        elif file.endswith(".png"):
            if not any(file.startswith(p) for p in allowed_png_prefixes):
                violations.append((file, "PNG file tracked outside allowed directories (tests/, reference/)"))
        elif file.endswith(".html"):
            if not any(file.startswith(p) for p in allowed_html_prefixes):
                violations.append((file, "HTML file tracked outside allowed directories (tests/, docs/)"))

    if violations:
        print("\n=== AUDIT FAIL ===")
        print("The following file hygiene violations were found:")
        for file, reason in violations:
            print(f"  - {file}: {reason}")
        print("\nRemediation Hint:")
        print("  1. Remove private fixtures from tracking: git rm --cached fixtures/private/*")
        print("  2. Remove generated files from tracking: git rm --cached <file_path>")
        print("  3. Ensure your local files are kept but not tracked in git.")
        print("  4. Track fixtures/private/.gitkeep to maintain the directory structure.")
        sys.exit(1)

    print("\n=== AUDIT PASS ===")
    print("All private fixture and generated artifact tracking checks passed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
