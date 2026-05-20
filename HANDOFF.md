# Handoff

## Current Context

- Branch: `feature/scoreir-v0.1-contract`
- Pull request: PR #1, draft, targeting `main`
- Latest base checkpoint: `Fix CI test workflow` on top of `d0ee14e Align CI Python version`
- Private fixtures and diagnostic outputs must remain ignored and uncommitted.

## Implemented On This Branch

- ScoreIR v0.1.0 remains the formal interchange contract.
- Native `.mxl` intake reads compressed MusicXML packages via `META-INF/container.xml` without unpacking archives to disk.
- MusicXML timing risk is detected before invalid ScoreIR is written, including overfull bars and risky backup/forward timing.
- PDF extraction emits `missing_pdf_grouping` when playable candidates exist but systems, bars, or strings cannot be inferred.
- Grouping diagnostic HTML and overlay artifacts are written for grouped, partial, and missing playable PDF extraction.
- Public PDF grouping v0.1 is committed for controlled born-digital/generated fixtures with visible six-line tab geometry and barlines.
- Private diagnostic summaries remain count/status based and avoid private score contents.

## Verification Expected For PR #1

- `python -m pytest`
- `python -m score2gp.cli export-schema --out schemas`
- `python -m score2gp.cli validate-ir fixtures/public/tiny_score.ir.json`
- `git diff --check`
- GitHub Actions should run the editable package install with `.[dev]` and then `python -m pytest`.

## Known Limitations

- PDF grouping v0.1 is only proven on controlled generated/born-digital fixtures.
- No OCR, scanned-PDF support, ML layout recognition, or arbitrary commercial score conversion.
- GPIF output remains minimal.
- Chord symbols and technique text are preserved as evidence but are not yet musically attached to ScoreIR events.
- Private real-world conversion remains diagnostic-only.

## Recommended Next Work

- Keep PR #2 stacked on this branch for partial grouping diagnostics.
- Add public fixtures for additional low-confidence grouping cases before another private diagnostic experiment.
- Continue improving reports and diagnostics before expanding GPIF or conversion breadth.
