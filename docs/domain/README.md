# Domain Knowledge Index

This folder contains product and music-domain knowledge for `score2gp`.

These documents are not agent prompts. They are the shared source of truth that architect, developer and reviewer agents should read when designing, implementing or reviewing changes.

The existing `guitar_notation_guide.md` explains the basic notation vocabulary: staff/stave, guitar written range, note values, bars/measures, rests and dotted notes. The files in this folder build on that guide and describe how those concepts matter to PDF extraction and conversion.

## Recommended reading order

1. `guitar_notation_guide.md`
2. `tablature-semantics.md`
3. `timing-and-voices.md`
4. `pdf-score-extraction.md`
5. `musicxml-model.md`
6. `guitar-pro-format.md`
7. `guitar-pro-relational-schema.md`
8. `validation-rules.md`
9. `notation-readability.md`
10. `guitar-technique-articulation.md`

## How agents should use these files

Architect agents should use these files to define requirements, constraints, acceptance criteria and stop conditions.

Developer agents should use these files to understand what must be preserved by the implementation.

Reviewer agents should use these files to decide whether a change is musically valid, testable and safe to merge.

## Status levels

Use these status labels when changing this folder:

- **Stable**: domain rule is well understood and should guide implementation.
- **Project decision**: chosen by this project; not necessarily a universal music rule.
- **Assumption**: plausible but must be tested against fixtures.
- **Unknown**: not yet established; do not build irreversible behaviour on it.

## Rules for adding domain knowledge

Do not add claims about current code behaviour unless they have been verified in the repository.

Do not add private score content, generated diagnostic dumps, private PDFs, Guitar Pro files, logs or local work artifacts.

Do not treat a single fixture as a universal rule. Record it as an observed case.

Prefer examples that are small, synthetic and safe to commit.

## Cross-cutting principles

The conversion pipeline should preserve musical meaning before cosmetic layout.

Every inferred symbol should remain traceable to source evidence where practical.

Ambiguous extraction should produce warnings and diagnostics, not silent corruption.

Validation must distinguish between:

- a musically impossible result,
- a plausible but uncertain result,
- an unsupported notation feature,
- a parser defect,
- a fixture-specific edge case.
