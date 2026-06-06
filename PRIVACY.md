# Privacy and Safety Guidelines

This document outlines the strict guidelines and invariants designed to protect proprietary, copyrighted, and licensed score files from leaking into the public version control history of `score2gp`.

## Private Assets and ignored files

The following files and folders must **never** be committed to Git:
* **Source Scores**: Original score files (PDFs, images).
* **Sidecars**: Imported MusicXML, MXL packages, or customized ASCII alignment configurations.
* **Generated Packages**: Output Guitar Pro `.gp` zip files.
* **Diagnostics and Reports**: Intermediate generated JSON diagnostics, logs, HTML reports, system overlays, or page renders.
* **Working Directory**: The entire `work/` folder and any sub-run directories.

### Folder Invariant: `fixtures/private`
The `fixtures/private/` directory is reserved for local diagnostic assets. It must only contain the `.gitkeep` file in version control:
* Git-tracked files: `fixtures/private/.gitkeep` (all other files are ignored via `.gitignore`).

---

## Private-Safety Command

To verify that no private or generated assets are tracked, run the following safety check:
```bash
git ls-files fixtures/private work
```
**Expected Output**:
```text
fixtures/private/.gitkeep
```
Any other line in the command's output indicates that a private or local-only file has been staged/committed, which violates the safety gate.

---

## Generated Artifact Handling Rules

1. **Local Scope**: All HTML overlays, diagnostics sidecars, and `.gp` packages created during developer CLI operations must remain inside the ignored `work/` directory.
2. **Redacted Summaries**: When checking E2E results or publishing smoke summaries, only use the anonymized and redacted summaries (`private_e2e_summary.json` / `private_e2e_summary.md`). These reports are designed to contain only page counts, candidate counts, and status codes.
3. **No Code Leakage**: Do not copy raw note/tab content, fret sequences, lyrics, song titles, or artist details from private scores into tests, documentation, or commit messages.

---

## Branch and PR Review Privacy Checklist

Before submitting a Pull Request, verify the following:
* [ ] The command `git ls-files fixtures/private work` outputs exactly `fixtures/private/.gitkeep`.
* [ ] No private file paths or names are mentioned in commit messages, branch names, or PR descriptions.
* [ ] No hardcoded private file paths (e.g. referencing `Derek Trucks BB King.gp`) exist in the source code or public test cases.
* [ ] Any newly created scratch files or diagnostic tools are added to `.gitignore` or kept under the ignored `scratch/` directory.
