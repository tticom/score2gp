# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists: it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **ADRs**: read ADRs that touch the area you're about to work in.
  - `doc/architecture/decisions/` is the established Score2GP ADR location. Read existing ADRs from here, and **create new ADRs here** too, unless governance explicitly changes that convention. Do not move or rename existing ADRs.
  - `docs/adr/` is only a read-only check, because the skills may reference it as their default. Read it if it exists, but do **not** create it or write new ADRs there; it must not become a second ADR location.

  If the same decision appears in both places, the ADR in `doc/architecture/decisions/` wins.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo:

```
/
├── CONTEXT.md
├── doc/architecture/decisions/   ← Score2GP ADRs (existing and new)
│   └── 0004-retention-of-biomechanical-position-optimization.md
├── docs/adr/                     ← not used; checked only because skills may reference it
└── src/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0004 (retention of biomechanical position optimization), but worth reopening because…_
