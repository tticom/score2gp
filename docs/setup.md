# Setup

This guide describes a Windows-first local setup for `score2gp`, including the optional Audiveris OMR dependency.

The project is intentionally staged. Audiveris can help produce MusicXML/MXL from standard notation, but it does not fully recover guitar tablature, bends, slides, vibrato, or every guitar technique.

## 1. Prerequisites

Required:

- Python 3.11 or newer
- Git
- PowerShell

Recommended:

- GitHub CLI, `gh`, for publishing or cloning private repositories
- Audiveris for optional OMR to MusicXML/MXL
- MuseScore for manual MusicXML inspection

Optional future tooling:

- alphaTab for Guitar Pro parsing/rendering validation
- OpenCV/Pillow image tooling for later tab extraction work

## 2. Clone Or Open The Project

Local development path used by this project:

```powershell
cd C:\Users\niall\src\Python
git clone git@github.com:tticom/score2gp.git
cd score2gp
```

If the repository already exists locally:

```powershell
cd C:\Users\niall\src\Python\score2gp
git pull
```

## 3. Install Python Dependencies

Install the package in editable mode with development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

If pip suggests upgrading itself, use:

```powershell
python -m pip install --upgrade pip
```

Run tests:

```powershell
python -m pytest
```

Use `python -m pytest` rather than plain `pytest` unless your Python Scripts directory is on `PATH`.

## 4. PATH Notes

On some Windows Python installs, scripts are installed to a directory like:

```text
C:\Users\niall\AppData\Local\Python\pythoncore-3.14-64\Scripts
```

If that folder is not on `PATH`, direct commands such as `pytest` and `score2gp` will not resolve. These forms work without changing `PATH`:

```powershell
python -m pytest
python -m score2gp.cli --help
```

After adding the Scripts directory to `PATH`, this should also work:

```powershell
score2gp --help
pytest
```

## 5. Install Audiveris

Audiveris is optional but recommended for the OMR stage.

Install with WinGet:

```powershell
winget install --id audiveris.org.Audiveris --exact
```

The standard Windows installer currently places the executable here:

```text
C:\Program Files\Audiveris\Audiveris.exe
```

Verify the executable:

```powershell
Test-Path "C:\Program Files\Audiveris\Audiveris.exe"
& "C:\Program Files\Audiveris\Audiveris.exe" -version
```

Audiveris may not be on `PATH`, so prefer passing the full path to `score2gp`.

## 6. Private Fixtures

Private score files should stay under:

```text
fixtures/private/
```

That directory is ignored by Git except for `.gitkeep`. Do not commit copyrighted or licence-unclear examples.

Expected local private fixtures for current development:

```text
fixtures/private/Derek Trucks BB King.pdf
fixtures/private/Derek Trucks BB King.gp
```

## 7. Smoke Tests

Inspect the private GP fixture:

```powershell
python -m score2gp.cli inspect-gp "fixtures/private/Derek Trucks BB King.gp"
```

Inspect the PDF and render pages:

```powershell
python -m score2gp.cli inspect-pdf "fixtures/private/Derek Trucks BB King.pdf" --out "work/derek/inspect"
```

Run Audiveris OMR:

```powershell
python -m score2gp.cli omr "fixtures/private/Derek Trucks BB King.pdf" `
  --out "work/derek/omr" `
  --audiveris "C:\Program Files\Audiveris\Audiveris.exe"
```

Expected OMR artefacts:

```text
work/derek/omr/Derek Trucks BB King.mxl
work/derek/omr/Derek Trucks BB King.omr
work/derek/omr/audiveris.log
work/derek/omr/warnings.json
```

Generate and validate a minimal GP package from the public synthetic IR:

```powershell
python -m score2gp.cli write-gp "fixtures/public/tiny_score.ir.json" `
  --template "fixtures/templates/minimal_gp7.gp" `
  --out "work/tiny/output.gp"

python -m score2gp.cli validate "work/tiny/output.gp"
```

## 8. Current Pipeline Status

Working now:

- GP7 package inspection
- GP package validation
- Minimal GP writing from hand-authored ScoreIR
- PDF page rendering and text diagnostics
- Audiveris batch invocation to `.mxl`/`.omr`

Not complete yet:

- MusicXML plus tablature alignment into ScoreIR
- Reliable fret-number extraction from all PDFs
- Full PDF-to-GP conversion
- Complete GPIF technique coverage

The tool should report uncertainty and unsupported features rather than silently dropping them.
