# Limitations

PDF-to-GP conversion is not solved by this project yet.

Known limitations:

- Generic OMR tools may miss guitar-specific tab, bends, slides, vibrato, let-ring marks, and fingering details.
- Born-digital PDF text extraction works only when fret numbers and symbols are encoded as extractable text.
- Current system/string/bar inference is heuristic and proven only on controlled public generated fixtures, including a two-system score-like page, not arbitrary score layouts.
- Chord symbols and technique text extracted from PDF-derived TabRaw are preserved and reported, but not yet aligned into ScoreIR events.
- Candidate text near tab systems is preserved as non-playable evidence; it is not interpreted musically.
- Scanned PDFs require OCR/image recognition that is not complete in the first milestone.
- The generated PDF regressions demonstrate controlled born-digital PDF producer paths; they do not mean private or commercial scores will convert cleanly.
- GPIF support is minimal and may not cover every Guitar Pro feature.
- Unsupported or uncertain notation must be reported in warnings and conversion reports.

This tool is for files the user owns or has permission to process. It must not be used to bypass DRM or copy protected scores from unauthorised sources.
