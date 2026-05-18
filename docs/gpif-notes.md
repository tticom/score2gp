# GPIF Notes

Guitar Pro 7 `.gp` files are zip packages. A typical package contains:

- `VERSION`
- `Content/score.gpif`
- `Content/Preferences.json`
- `Content/LayoutConfiguration`
- `Content/PartConfiguration`
- `Content/BinaryStylesheet`

The first writer milestone is deliberately conservative:

- It writes a well-formed `Content/score.gpif`.
- It includes metadata, tempo, time signatures, tracks, tunings, bars, beats, notes, rests, chord symbols, and common technique tags.
- It preserves non-GPIF template package members when a template is supplied.
- It does not claim byte-for-byte compatibility with Guitar Pro's own output.

Assumptions are encoded in `score2gp.gpif` and covered by semantic tests.
