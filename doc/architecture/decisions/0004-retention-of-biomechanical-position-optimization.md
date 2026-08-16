# 4. Retention of Biomechanical Position Optimization

Date: 2026-08-15

## Status

Accepted

## Context

Guitar Pro (.gp) files structurally require a string index and fret number for every note, as the software fundamentally models a physical fretboard. When converting from PDF sheet music, we must provide this ownership data.

The `ScoreIRCompiler` requires all incoming note events to have a valid `FretTokenOwnership` assignment. The question arose whether we could rely entirely on explicit TAB data extracted from the PDF, and thus remove the `BiomechanicalPositionOptimizer` (which infers string and fret positions for standard-notation notes based on physical constraints and transition costs).

A review of the OMR pipeline (`src/score2gp/notation_omr/pipeline.py`) and the private fixtures (`Lesson-5.pdf`, `Lesson-6.pdf`) reveals that while the PDFs themselves contain visual TAB blocks, the current extraction layer only processes standard notation elements (clefs, notes, etc.). The fusion of TAB numbers into the timeline is not yet implemented.

Because explicit TAB data is not currently extracted, every single note recognized in the private fixtures arrives as standard notation without explicit TAB.

## Decision

We will **retain** the `BiomechanicalPositionOptimizer` and its associated cost weights. It is strictly necessary to infer physical hand positions for standard-notation notes until the dual-modality TAB extraction and fusion pipeline is fully integrated. If we were to remove it, all notes would arrive at the compiler unowned, breaking the core conversion loop.

We will remove the synthetic `(string=1, fret=0)` fallback injection from the compiler, as it produces musically corrupt output. Instead, notes that completely fail pitch resolution in the extraction layer (e.g. failing ledger line checks) will be marked as unresolved and cause the measure capacity validation to fail, explicitly invalidating the corrupted measure.
