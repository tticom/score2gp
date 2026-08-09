# Conversion Module Migration Map & Programme Backlog (CRP-00 to CRP-15)

**Date**: 2026-08-09
**Author**: Architect & Researcher (`tticom-automation`)
**Repository**: `tticom/score2gp`
**Branch**: `agy/conversion-recovery-architecture`
**Base Commit**: `4a4f5c339e09987b9f41641397f1db7e8ab1be5d`

---

## 1. Programme Dependency Graph (CRP-00 to CRP-15)

```
[ CRP-00: Preflight & Workaround Hack Cleanup ]
                      │
                      ▼
[ CRP-01: Barline Detection & Threshold Harmonization ]
                      │
                      ▼
[ CRP-02: Topologically Locked System Barlines ]
                      │
                      ▼
[ CRP-03: Page-Continuous Measure Indexing & Offsets ]
                      │
                      ▼
[ CRP-04: Real-Source Oracle Harness & Falsification Suite ]
                      │
                      ▼
[ CRP-05: Sidecar Bake-off & 4/4 Triplet Discriminator ]
                      │
                      ▼
[ CRP-06: Dual-Modality Visual TAB Digit OMR ]
                      │
                      ▼
[ CRP-07: Document Topology Module ]
                      │
                      ▼
[ CRP-08: Recognition Adapter Seams ]
                      │
                      ▼
[ CRP-09: Paired-Staff Evidence Fusion ]
                      │
                      ▼
[ CRP-10: Musical Timeline Replacement ]
                      │
                      ▼
[ CRP-11: Biomechanical Fretboard Position Optimizer ]
                      │
                      ▼
[ CRP-12: ScoreIR / GPIF Compiler Refactor ]
                      │
                      ▼
[ CRP-13: Legacy Removal & Corpus Acceptance Gate ]
```

---

## 2. Implementation-Ready Prompt Specification: First Unblocked Task (CRP-01)

*Note: Recorded here in product architecture for separate AgentOps governance promotion (`projects/score2gp/prompts/next/0044-m6-port-and-harmonize-barline-detection.md`).*

```markdown
# 0044 — Port and Harmonize Barline Detection & Geometry Cleanup (CRP-01)

## Goal
Port valid barline detection thresholds from PR 418 into `src/score2gp/pdf.py`, revert `outer_tolerance = 300.0` hack, and enforce staff-relative barline height bounds without mutating higher-level layout models.

## Allowed Files
- `src/score2gp/pdf.py`
- `src/score2gp/pdf_staff_notation_diagnostics.py`
- `tests/test_pdf_geometry_candidate_extractor.py`

## Implementation Specification
1. Update `pdf.py` barline height check from `height >= 20.0` to `height >= min(15.0, staff_height - 2.0)`.
2. Update inherited bar width check to `MIN_INHERITED_INTERNAL_BAR_WIDTH = 20.0`.
3. Revert `outer_tolerance` in `pdf.py` back to standard tight tolerance (`24.0pt`).
4. Re-enable `pdf_candidate_outside_system` warning gate.

## Acceptance Criteria
- `pytest tests/test_pdf_geometry_candidate_extractor.py` passes cleanly.
- `python3 scripts/private_e2e_smoke.py --pdf fixtures/private/Lesson-5.pdf` successfully extracts 43 notation barlines on `Lesson-5.pdf` without triggering 300pt snapping hacks.
```

---

## 3. Dependent Task Skeleton Specifications (CRP-02 to CRP-13)

### CRP-02: Topologically Locked System Barlines
- **Seam**: `src/score2gp/pdf.py` system grouping.
- **Goal**: Lock 5-line notation barlines to 6-line TAB barlines system-by-system before event extraction.

### CRP-03: Page-Continuous Measure Indexing & Offsets
- **Seam**: `src/score2gp/pdf.py` (`_extract_pdf_text_candidates`).
- **Goal**: Pass `running_bar_index` across multi-page boundaries to prevent measure index reset on Page 2.

### CRP-04: Real-Source Oracle Harness & Falsification Suite
- **Seam**: `scripts/private_e2e_smoke.py` & `tests/test_real_source_oracles.py`.
- **Goal**: Implement subprocess reference isolation and fail red against known-bad historical revisions.

### CRP-05: Sidecar Bake-off & 4/4 Triplet Discriminator
- **Seam**: `src/score2gp/notation_omr/timeline.py`.
- **Goal**: Evaluate sidecar OMR options against `Lesson-6` 4/4 triplet mandatory discriminator.

### CRP-06: Dual-Modality Visual TAB Digit OMR
- **Seam**: `src/score2gp/pdf.py` & `src/score2gp/vector_parser/`.
- **Goal**: Implement vector bezier path classifier for LilyPond/Sibelius TAB fret numbers (`0-24`).

### CRP-07: Document Topology Module
- **Seam**: `src/score2gp/topology.py` (New Module).
- **Goal**: Encapsulate system bounds, staff coordinates, and locked barline grids into explicit `SystemTopology`.

### CRP-08: Recognition Adapter Seams
- **Seam**: `src/score2gp/adapters/` (New Seam).
- **Goal**: Decouple OMR notation adapters from TAB candidate extractors.

### CRP-09: Paired-Staff Evidence Fusion
- **Seam**: `src/score2gp/fusion.py` (New Module).
- **Goal**: Fuse notation pitches/durations with visual TAB string/fret candidates per bar.

### CRP-10: Musical Timeline Replacement
- **Seam**: `src/score2gp/notation_omr/timeline.py`.
- **Goal**: Replace unbounded single-measure aggregation with topologically locked bar timelines.

### CRP-11: Biomechanical Fretboard Position Optimizer
- **Seam**: `src/score2gp/position_optimizer.py` (New Module).
- **Goal**: Implement dynamic programming solver minimizing hand movement and finger stretch costs.

### CRP-12: ScoreIR / GPIF Compiler Refactor
- **Seam**: `src/score2gp/build_ir.py` & `src/score2gp/gp_package.py`.
- **Goal**: Refactor IR construction to compile clean multi-track, multi-voice ScoreIR structures.

### CRP-13: Legacy Removal & Corpus Acceptance Gate
- **Seam**: Full product codebase (`src/score2gp/`).
- **Goal**: Delete legacy fallback paths, remove unneeded temporary scripts, and verify 100% corpus acceptance.

---

## 4. Risks, Rollback Strategy, and Stop Conditions

### Risk Matrix
| Risk | Severity | Mitigation Strategy |
| :--- | :--- | :--- |
| **Vector TAB Digit Misclassification** | High | Train vector path classifier on public LilyPond/Sibelius PDF TAB samples. |
| **OMR Duration Drift on Complex Rhythms** | Medium | Fall back to Score2GP internal duration estimation guided by barline capacity. |
| **Multi-Voice Polyphony Overlaps** | Medium | Strict stem direction (up=Voice 1, down=Voice 2) and Y-position resting. |

### Stop & Pivot Conditions
- **Pivot Condition 1**: If Audiveris sidecar drops 4/4 triplet timing on `Lesson-6.pdf`, pivot immediately to Score2GP internal topology-first timing adapter (Outcome A).
- **Stop Condition 2**: If an implementation task requires hardcoding fixture-specific coordinates or hashes into product code, STOP execution and return to Architect.

---

## 5. Summary

The conversion module migration map provides a clean, single-seam task hierarchy that guarantees incremental, verifiable progress toward 100% note-for-note score conversion fidelity.
