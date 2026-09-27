# OMIT-01 key-signature reading

The PDF-only route reads the painted accidental contours immediately after a
notation clef. Each sharp or flat must have the corresponding contour shape and
conventional staff position in the order of the circle of fifths. Text glyphs
are accepted for generated public PDFs. A cluster touching the first note is
an event accidental, not a key signature. Unclassified or mixed contours in
the header produce a located refusal. A new explicit signature changes the
count; an empty later header carries the last read count. The first empty
header establishes zero accidentals. A refusal breaks that inheritance until
another explicit signature can be read.

The `note-duration-records.v0.3` sidecar stores each system's count in its
diagnostics, alongside the systems in order. It records source
glyph IDs, clef glyph ID, inherited glyph IDs where applicable, and location.
`build_ir_from_tabraw_only` attaches the count to every bar, including bars
whose events were refused. GPIF `Key/AccidentalCount` is signed: flats use a
negative number, as Guitar Pro writes them.

The accidental count alone cannot identify major or minor. Unless an exact
printed key name beside the staff independently gives mode, the sidecar records
`key_mode_unresolved` and ScoreIR emits a located warning. GPIF requires a
`Mode`, so the writer uses `Major` as its format default for an unresolved
mode. This is a formatting convention, not a recognised musical mode. Neither
pitch content nor reference GP data supplies the mode.
