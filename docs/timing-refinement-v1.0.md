# Timing Refinement v1.0 Design Note

This note defines the conservative timing-refinement boundary used by the public
`feature/pdf-timing-refinement-v1.0` work. It is diagnostic-first: it improves
how timing and layout evidence are classified, but it does not repair MusicXML,
invent missing timing, or weaken ScoreIR gates.

## Current Timing Preflight Model

MusicXML import runs a deterministic voice cursor/timeline preflight before
ScoreIR is written. The preflight simulates note, rest, chord, backup, forward,
and voice cursor movement per part and measure. It reports private-safe counts,
measure/voice identifiers, reason codes, and calibration feasibility.

The preflight deliberately separates:

- valid chord stacks encoded with `<chord/>`, which are not same-voice timing
  overlaps;
- invalid same-voice timelines, including note/note overlap, rest/note overlap,
  overfull measures, impossible cursor movement, and malformed duration grids;
- valid MusicXML multi-voice/polyphonic timelines that are unsupported by the
  current ScoreIR/build-ir shape.

## Safe Timing Refinement

Safe timing refinement means clearer classification and diagnostics only:

- `invalid_timing_refused` for broken MusicXML timelines;
- `unsupported_polyphony_refused` for valid multi-voice timing that ScoreIR does
  not yet represent;
- `mixed_invalid_timing_and_unsupported_polyphony_refused` when both conditions
  are present;
- `timing_warning_or_info_only` when warnings should be inspected but do not
  block by themselves;
- explicit counts for affected measures, voices, and events without score text,
  pitches, lyrics, chord sequences, or private content.

Automatic repair remains unimplemented. If timing is invalid, the correct
outcome is refusal with remediation guidance, not silent timeline mutation.

## PDF/Vector Layout Timing Evidence

PDF x-position to MusicXML onset mapping is also diagnostic evidence. The
`pdf-timing-refinement.v1.0` layer classifies mapping evidence as:

- `safe`: x groups and MusicXML onset groups match in a controlled input;
- `partial`: useful evidence exists but one side has unmatched groups or warning
  quality;
- `ambiguous`: close x groups make visual onset assignment uncertain;
- `incompatible`: non-monotonic or poor layout evidence is unsafe;
- `refused`/`unavailable`: mapping was not attempted because upstream grouping or
  MusicXML timing was unsafe.

The mapping never moves candidates, creates events, infers frets or strings from
MusicXML, or repairs MusicXML durations.

## What Remains Refused

The following stay refused unless a future branch designs and proves a narrow
safe path:

- same-voice timing overlap;
- rest/note timing overlap;
- overfull measures and invalid duration grids;
- valid but unsupported multi-voice/polyphonic MusicXML;
- unsafe PDF grouping;
- unsafe MusicXML preflight;
- non-monotonic vector x-position evidence;
- private examples that do not match a public synthetic proof case.

Future repair work, if any, must be explicitly gated, public-fixture proven,
diagnosable, and refusal-first.
