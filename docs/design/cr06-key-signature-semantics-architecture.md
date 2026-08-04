# CR-06 Key-Signature Semantics Architecture

## Active Blocker

In `tticom/score2gp`, PDF standard staff parsing currently lacks explicit key-signature accidental glyph detection. When key-signature evidence is absent on a notation staff, `src/score2gp/notation_omr/pitch.py` and `src/score2gp/cli.py` hardcode a default fallback of `"C Major"` (0 accidentals). This falsely reports C-Major / A-Minor as a "recognized key signature" when no key-signature evidence exists on the staff, violating the rule that unevidenced staves must not emit assumed key signatures as recognized facts.

## Verified Repository State

1. **Defaulting & Hardcoding**:
   - `src/score2gp/notation_omr/pitch.py` (lines 201–219): In `map_clef_resolved_staff_pitch`, when `explicit_key_signature` is `None` and `semantic_candidates` lacks a valid `"key_signature"` candidate, `key_sig` is hardcoded to `"C Major"`.
   - `src/score2gp/cli.py` (lines 234–243): When displaying semantic summary information for a staff, if `logical_key_signature` is absent, the CLI displays `Key Signature: C Major`.
2. **Accidental Glyph Detection near Clefs**:
   - `src/score2gp/pdf.py`, `src/score2gp/pdf_staff_geometry.py`, and `src/score2gp/whole_note_recogniser.py` contain zero key-signature glyph recognition logic near clefs. No sharp (`#`) or flat (`b`) accidental symbols near clefs are extracted from vector paths or rasters.
3. **ScoreIR and GPIF Representation**:
   - `src/score2gp/ir.py` (lines 112 & 673): `Bar.key_signature` is defined as `KeySignature | None = None`. `ScoreIR` correctly represents unevidenced key signatures as `None`.
   - `src/score2gp/build_ir.py` (line 1585): Constructs `KeySignature(fifths=measure.key_fifths)` only when `measure.key_fifths` is not `None`.
   - `src/score2gp/gpif.py` (lines 614–624 & 1486–1490): GPIF XML export includes `<Key>` in `<MasterBar>` only when `bar.key_signature` is not `None`.
4. **Public Test Coverage**:
   - `tests/test_logical_clef_coverage_proof.py` (lines 355–376): Explicitly tests that an unrecognized or missing key signature falls back to `"C Major"`.

## Research Question

How can `tticom/score2gp` distinguish explicit sharp/flat key-signature glyph evidence from unevidenced staves, ensuring unevidenced staves record key signature as `UNKNOWN` without defaulting to a recognized `"C Major"` key signature in reports or metadata?

## References Reviewed

1. **MusicXML 4.0 Specification — Key Signatures**:
   - Source: W3C MusicXML 4.0 Standard (`<key>` element definition).
   - Direct evidence: MusicXML represents key signatures via `<fifths>` (-7 to +7). The absence of a `<key>` element indicates no key signature changes or unknown key signature.
2. **Guitar Pro GPIF Format Specification — MasterBar Key**:
   - Source: Arobas Music GPIF XML Schema.
   - Direct evidence: `<Key>` node contains `<Fifths>` (-7 to +7) and `<Mode>` ("Major"/"Minor"). Omitting `<Key>` indicates standard/default notation without explicit key signature assertions.
3. **Score2GP Backlog Task Definition — CR-06**:
   - Source: `projects/score2gp/tasks/2026-07-17-visual-output-correctness-backlog.md` (lines 89–95).
   - Direct evidence: "Detect sharp/flat key evidence or record key as unknown. Do not emit a neutral key as recognised and do not create accidentals from unknown evidence."

## Claim-by-Claim Evidence Table

| Claim | Source Reference | Repository Verification | Evidence Type |
| :--- | :--- | :--- | :--- |
| `pitch.py` hardcodes `"C Major"` fallback when key sig evidence is missing | `src/score2gp/notation_omr/pitch.py:201` | Verified `key_sig = "C Major"` fallback | Direct Code Fact |
| `cli.py` prints `Key Signature: C Major` for unevidenced staves | `src/score2gp/cli.py:242` | Verified `else: key_text = "C Major"` | Direct Code Fact |
| `ScoreIR` natively supports `None` key signature on `Bar` | `src/score2gp/ir.py:673` | Verified `key_signature: KeySignature \| None = None` | Direct Code Fact |
| `GPIF` omits `<Key>` node when `key_signature` is `None` | `src/score2gp/gpif.py:614` | Verified `if bar.key_signature is not None:` guard | Direct Code Fact |
| PDF/Vector extraction has no key-signature accidental recognizer | `src/score2gp/pdf.py` | Searched `pdf.py` & `pdf_staff_geometry.py`; 0 hits | Direct Code Fact |

## Options Considered

### Option 1: Full End-to-End Key Signature Glyph Extraction & Contract Overhaul
- **Description**: Build a vector/raster accidental glyph detector near clefs and simultaneously refactor pitch mapping, CLI reporting, and ScoreIR.
- **Evaluation**: Violates bounded single-slice rules. Vector accidental recognition near clefs requires geometric primitive clustering and glyph classification that is distinct from key-signature contract state handling.

### Option 2: Architectural Separation — Evidence Contract First (CR-06A), Followed by Glyph Detector (CR-06B)
- **Description**: First introduce a tri-state `logical_key_signature` model (`EVIDENCED`, `UNKNOWN`, `AMBIGUOUS`) in `notation_omr/pitch.py` and `cli.py`. Remove the hardcoded `"C Major"` fallback for unevidenced staves. When `UNKNOWN`, pitch mapping applies 0 alterations without declaring a recognized C Major key signature.
- **Evaluation**: Bounded, testable, and directly addresses the prompt's requirement ("distinguish explicit sharp/flat key-signature glyph evidence from the absence of key-signature evidence").

### Option 3: Retain Current Defaulting Behavior
- **Description**: Keep defaulting unevidenced staves to C Major.
- **Evaluation**: Rejected. Directly violates CR-06 prompt requirement.

## Selected Outcome

**`CONTINUE`**: Evidence supports one bounded Developer slice (CR-06A).

## Proposed Developer Task (CR-06A: Key Signature Evidence Contract & Fallback Removal)

### Authorized Files
- `src/score2gp/notation_omr/pitch.py`
- `src/score2gp/cli.py`
- `tests/test_cr06_key_signature_semantics.py`

### Proposed Changes
1. **`notation_omr/pitch.py`**:
   - Replace hardcoded `key_sig = "C Major"` default with explicit `key_signature_status`.
   - If key signature candidate is provided and valid, set status `EVIDENCED` and apply specified key alterations.
   - If key signature candidate is absent or `None`, set status `UNKNOWN`. Apply 0 key alterations without asserting a recognized `"C Major"` key signature in outputs.
2. **`cli.py`**:
   - Update semantic summary text for key signature: display `Key Signature: Unknown` when `logical_key_signature` status is `UNKNOWN` or missing.
3. **`tests/test_cr06_key_signature_semantics.py`**:
   - Add unit tests verifying that unevidenced staves report `Key Signature: Unknown` and do not assert `"C Major"`.
   - Add unit tests verifying explicit key signatures (e.g. `"G Major"`) apply alterations correctly when `EVIDENCED`.

### Validation Commands
```bash
.venv/bin/python -m pytest tests/test_cr06_key_signature_semantics.py
.venv/bin/python scripts/agent_verify.py
```

## Measurable Success Criterion
1. `pytest tests/test_cr06_key_signature_semantics.py` passes 100%.
2. Unevidenced notation staves report `Key Signature: Unknown` instead of `Key Signature: C Major`.
3. `agent_verify.py` passes cleanly (🟢 PASS).

## Known Risks & Limitations
- **Risk**: Existing tests expecting hardcoded `"C Major"` string in CLI output or pitch mapping diagnostics may require explicit update.
- **Limit**: CR-06A handles state representation and fallback removal. Vector/raster accidental glyph extraction near clefs is deferred to CR-06B.

## What Was Not Verified
- Multi-staff key signature sync across grand staves (e.g. piano treble + bass staves with linked key signatures) is deferred to future multi-staff tasks.
