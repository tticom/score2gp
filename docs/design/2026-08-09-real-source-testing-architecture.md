# Real-Source Testing & Governance Architecture

**Date**: 2026-08-09  
**Author**: Architect & Researcher (`tticom-automation`)  
**Repository**: `tticom/score2gp`  
**Branch**: `agy/conversion-recovery-architecture`  
**Base Commit**: `4a4f5c339e09987b9f41641397f1db7e8ab1be5d`  

---

## 1. Three-Repository Governance Contract

The Score2GP conversion recovery programme enforces a strict three-repository boundary separation:

```
┌─────────────────────────────────────────────────────────┐
│              score2gp-private-fixtures                  │
│  - Confidential PDFs (Lesson-5.pdf, Lesson-6.pdf)       │
│  - Target Reference GP Files (Lesson-5.gp, Lesson-6.gp)  │
│  - Fixture Manifests & Ground-Truth SHA-256 Hashes      │
└────────────────────────────┬────────────────────────────┘
                             │ (Read-Only Input & Oracle Access)
                             ▼
┌─────────────────────────────────────────────────────────┐
│                        score2gp                         │
│  - Production Conversion Engine & CLI                  │
│  - Generic Bar-Level Comparator (compare.py)            │
│  - Real-Source Harness & Result Schemas                │
└────────────────────────────┬────────────────────────────┘
                             │ (Sanitized Execution Receipts)
                             ▼
┌─────────────────────────────────────────────────────────┐
│                   score2gp-agentops                     │
│  - Task Authority (ACTIVE_TASK.md & QUEUE)              │
│  - Acceptance Policy & Governance Prompts               │
│  - Sanitized Run Records & Audit Evidence               │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Process Isolation Architecture & Reference Non-Leakage

To guarantee that the conversion pipeline cannot cheat or calibrate rules to target files, generation is strictly isolated from reference data:

```
[ Phase 1: Subprocess Generation ]
   Input:  --pdf path/to/Lesson-5.pdf ONLY
   Output: /tmp/work/generated.gp
   ISOLATION GUARANTEE: Subprocess environment has NO ACCESS to reference .gp path.

[ Phase 2: Post-Generation Oracle Comparison ]
   Input:  Reference GP (path/to/Lesson-5.gp) AND Generated GP (/tmp/work/generated.gp)
   Runner: score2gp.compare (load_bar_data & compare_bar_scores)
   Output: Mismatch Ledger (measure count error, note count error, pitch/rhythm deltas)
```

### Reference Isolation Rules
1. **No Target Calibration**: No code in `score2gp` may inspect filename substrings (`"lesson-5"`), file hashes, page counts, bounding box constants, or expected note counts.
2. **Generic Multi-Score Acceptance**: Every proposed bug fix must pass on `Lesson-5.pdf`, `Lesson-6.pdf`, AND a second distinct score (`Derek Trucks BB King.pdf` or `Melodic Soloing Masterclass.pdf`).
3. **Held-Out Oracle**: `Lesson-6.pdf` serves as a held-out acceptance oracle. No developer or architect prompt may calibrate algorithms directly to `Lesson-6` coordinates.

---

## 3. Inventory of Synthetic Unit Tests & Migration Plan

Currently, `tests/` contains **1,121 unit tests**, 100% of which pass. However, an inventory reveals that **over 90% of conversion tests rely on synthetic JSON mocks**:

| Test File | Current Fixture Type | Claimed Test Purpose | Real-Source Migration Plan |
| :--- | :--- | :--- | :--- |
| `tests/fixtures/tiny_score.ir.json` | Synthetic 1-bar JSON | ScoreIR compilation to GP | Retain as format-only unit test (no conversion claim). |
| `tests/test_pdf_only_tab.py` | Mock-backed candidate pools | TAB candidate alignment | Replace with real-source extraction from `Lesson-5.pdf`. |
| `tests/test_musicxml_generator.py` | Pre-baked MusicXML strings | Timeline MusicXML generation | Replace with real-source sidecar generation from private PDFs. |
| `tests/test_bar_alignment_quality_gate.py` | Refusal string checks | Refusal gate logic | Require paired productive success evidence on real PDFs. |

### Migration Principle
- **Pure Format Tests**: May remain unit tests if they make zero musical/conversion claims.
- **Conversion & Recognition Tests**: MUST be migrated to use real-source extracted cases from approved public/private fixtures.
- **Refusal Tests**: Must prove that refusal gates trigger on invalid inputs while passing cleanly on valid real-source inputs.

---

## 4. Falsification Verification Requirements (Known-Bad Red Testing)

The new real-source testing harness (`scripts/private_e2e_smoke.py` / `tests/test_real_source_oracles.py`) MUST fail **RED** when evaluated against known-bad historical revisions:

```python
# Falsification Matrix: Harness MUST reject these 6 known-bad revisions
KNOWN_BAD_REVISIONS = {
    "300pt_snapping_hack": ("7ad7cb5", "Fails: Lesson-5 bar count error = 39"),
    "duration_scaling_hack": ("6f8e438", "Fails: Lesson-5 rhythm timing risk refusal"),
    "open_string_synthesis_hack": ("28c8a59", "Fails: Lesson-5 note count error = 294"),
    "capacity_fragmentation_hack": ("28c8a59", "Fails: Lesson-5 measure count = 133 vs 43"),
    "page_index_reset_bug": ("main", "Fails: Page 2 measure collision"),
    "proximity_digit_merge_hack": ("70a2d05", "Fails: Digit '1' + fingering '3' merged to '13'"),
}
```

---

## 5. Summary

The real-source testing architecture establishes complete process isolation, eliminates false test signals, and enforces multi-score generic acceptance gates across all upcoming recovery tasks.
