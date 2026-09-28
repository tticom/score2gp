# OMIT-01 key-signature reading

The PDF-only route reads the painted accidental contours immediately after a
notation clef. Each sharp or flat must have the corresponding contour shape and
conventional staff position in the order of the circle of fifths. Text glyphs
are accepted for generated public PDFs. A cluster touching the first note is
an event accidental, not a key signature. Unclassified or mixed contours in
the header produce a located refusal. A new explicit signature after a barline
changes the count from that bar. An empty header after a read clef establishes
zero accidentals; no count is inherited across a system break. A refused
mid-system cluster leaves that bar and subsequent bars without a key claim
until another signature is read.

The `note-duration-records.v0.4` sidecar stores each system header and a
`bar_key_signatures` map keyed by zero-based bar index. Each read signature
carries source glyph IDs and a location; an empty header cites its clef.
`build_ir_from_tabraw_only` attaches the bar count even when that bar's events
were refused. GPIF `Key/AccidentalCount` is signed, and the GPIF reader treats
the count as signed regardless of `TransposeAs`.

The accidental count alone cannot identify major or minor. Unless an exact
printed key name beside the staff independently gives mode, the sidecar records
`key_mode_unresolved` and ScoreIR emits a located warning. GPIF requires a
`Mode`, so the writer uses `Major` as its format default for an unresolved
mode. This is a formatting convention, not a recognised musical mode. Neither
pitch content nor reference GP data supplies the mode.
