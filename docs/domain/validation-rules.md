# Validation Rules

## Purpose

This document defines validation rules for `score2gp`.

Validation is how the project distinguishes a useful conversion from a file that merely exists.

A valid output should preserve musical meaning, expose uncertainty and avoid silent corruption.

## Validation layers

Use layered validation:

1. **Input evidence validation**: can the source evidence be read safely?
2. **Extraction validation**: were expected symbols detected?
3. **Grouping validation**: were symbols grouped into plausible musical objects?
4. **Timing validation**: do durations and voices make sense?
5. **Guitar semantics validation**: are string/fret/tuning relationships valid?
6. **Output validation**: can the target artifact be written and checked?
7. **Privacy validation**: were no private artifacts committed or exposed?

## Severity levels

Recommended severities:

- `info`: useful context, not a problem.
- `warning`: conversion may be incomplete or uncertain.
- `error`: output is likely musically wrong or structurally invalid.
- `fatal`: processing cannot safely continue.

A task should define which warnings are acceptable.

## Measure validation

Check:

- measure has a time signature in force,
- measure capacity is known,
- each voice duration is valid or explicitly unknown,
- measure is not overfull,
- underfull measures are explained,
- pickup/final bars are recognised where applicable,
- barline/repeat metadata does not create impossible structure.

Do not treat every underfull measure as a defect without checking for pickup or ending context.

## Duration validation

Check:

- all notes/rests have exact durations or explicit unknown-duration status,
- dotted durations are calculated correctly,
- tuplets are represented exactly if supported,
- no unsupported tuplet is converted as a rough approximation,
- ties extend duration without creating duplicate attacks unless intended.

## Voice validation

Check:

- events in one voice do not overlap unexpectedly,
- chords share a common onset,
- sustained notes do not erase moving notes in another voice,
- voice assignment does not depend only on x-coordinate proximity,
- missing rests/gaps are represented honestly.

## Tablature validation

Check:

- string numbers are within instrument range,
- fret values are valid integers or recognised markers,
- multi-digit fret numbers are grouped correctly,
- `0` is treated as open string,
- muted/dead notes are not treated as normal pitched notes,
- tuning is known or defaulted under explicit policy,
- string/fret and pitch agree where pitch evidence exists.

## Staff/tab reconciliation validation

When both staff and tab are available, check:

- rhythmic alignment between staff and tab,
- pitch agreement where calculable,
- measure boundary agreement,
- voice agreement where visible,
- detected conflicts are reported.

A conflict does not always mean the conversion must fail. It does mean the result must not pretend both sources agreed.

## Technique validation

Check:

- recognised techniques are attached to the correct event range,
- unsupported techniques generate warnings,
- slurs and ties are not confused silently,
- bends/slides/hammer-ons/pull-offs are not emitted without enough evidence.

## Output artifact validation

Check:

- artifact exists,
- artifact is non-empty,
- artifact has expected extension,
- writer returned success,
- artifact can be parsed or smoke-tested if tooling exists,
- expected measures/events are present,
- no unexpected private content appears in tracked files.

## Privacy and artifact hygiene

Before committing or opening a PR, run checks appropriate to the repository.

Recommended commands:

```bash
git status
git status --ignored
git ls-files
find . -path "./.git" -prune -o -type f -size +10M -print
```

Do not commit:

- private PDFs,
- private Guitar Pro files,
- generated MusicXML unless explicitly intended,
- diagnostic HTML from private input,
- logs,
- extracted text dumps,
- screenshots of private scores,
- local environment files,
- tokens or credentials.

## Evidence required in agent reports

Developer and reviewer reports should include:

- branch name,
- commit hash,
- changed files,
- commands run,
- test results,
- generated artifact paths if any,
- warnings/errors observed,
- what was not tested,
- clean working tree status,
- privacy/artifact check status,
- PR link if opened.

## Acceptance criteria for validation work

A validation task is complete only when:

- the rule being validated is explicitly named,
- at least one positive case exists,
- at least one failure or warning case exists where practical,
- diagnostics are understandable,
- tests can be run by another agent,
- limitations are recorded.

## Stop conditions

Stop and report if:

- validation would require committing private material,
- the expected output is not defined,
- tests assert only that a file exists,
- a rule cannot be checked from available data,
- the implementation hides uncertainty to satisfy tests.
