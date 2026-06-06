# Release Contract

This document defines the release-hardening contract for the `score2gp` milestone. It sets clear expectations on what input classes are supported, how errors/unsupported cases are handled, and how release quality is audited.

## Supported Release Scope

The tool is designed to process digital born-digital vector guitar scores and convert them into structured intermediate data and valid Guitar Pro packages.

### Accepted Input Class
* **Born-Digital Vector PDF + MusicXML/MXL Sidecar**: The primary input must be a digital vector PDF containing selectable fret text/digits and horizontal vector lines representing a six-line tab staff, accompanied by a matching MusicXML sidecar containing notation and timing details.
* **Born-Digital Text PDF with ASCII Tab + MusicXML/MXL Alignment**: A digital text PDF containing six-row ASCII tab blocks paired with a compatible MusicXML sidecar and a pre-generated column-to-onset alignment map.
* **Hand-Authored ScoreIR**: Directly authored Pydantic `ScoreIR` JSON.

### Expected Output
* **ScoreIR**: A validated JSON file conforming to the `ScoreIR` schema (`score.ir.json`).
* **Guitar Pro Package**: A valid Guitar Pro 7 package (`smoke.gp`) that passes structural zip validation and GPIF XML well-formedness checks.

---

## Current Milestone Fixtures and Validation Counts

Below are the stable regression benchmarks and validation counts for the current milestone (referred to by anonymous/sanitized labels):

| Anonymous Label | Input Type | Playable Fret Count | Matched Count | GP Package Validity |
| :--- | :--- | :--- | :--- | :--- |
| `private_input_1` | Drawn Tab + MusicXML | 153 | 153 / 153 | Valid |
| `private_input_custom_lesson_3` | Drawn Tab + MusicXML | 459 | 459 / 459 | Valid |
| `private_input_custom_lesson_4` | Drawn Tab + MusicXML | 546 | 546 / 546 | Valid |
| `private_input_custom_lesson_5` | Drawn Tab + MusicXML | 295 | 295 / 295 | Valid |
| `private_input_custom_lesson_6` | Drawn Tab + MusicXML | 235 | 235 / 235 | Valid |
| `private_input_custom_lesson_7` | Drawn Tab + MusicXML | 624 | 624 / 624 | Valid |
| `private_input_custom_melodic_soloing` | Drawn Tab + MusicXML | 82 | 82 / 82 | Valid |

---

## Explicit Non-Goals
* **No OCR/OMR Support**: Scanned or rasterized PDF inputs (composed of image pixels rather than vector shapes/text) are unsupported.
* **No pure ASCII Conversion**: Converting ASCII tab sheets to timed GP files without a corresponding MusicXML sidecar is unsupported.
* **No Automated Layout Synthesis**: Preserving print-ready layouts, formatting, page sizing, or complex aesthetic elements in the generated GP files is out of scope.

---

## Refusal-Code Behaviour

The pipeline is hardened to fail cleanly rather than producing invalid ScoreIR or malformed GP packages. The following refusal codes are raised during validation:

* **`missing_pdf_grouping`**: Raised when fret candidates exist on a page but cannot be cleanly assigned to a system, string, or bar box.
* **`missing_musicxml`**: Raised when a drawn vector tab run is initiated without providing the mandatory `--musicxml` argument.
* **`missing_ascii_alignment_sidecar`**: Raised when attempting to process ASCII tab inputs without providing an alignment map.
* **`invalid_timing_refused`**: Raised when the MusicXML sidecar fails voice timeline preflight checks (e.g. overfull measures, overlapping events in a single voice).
* **`unsupported_polyphony_refused`**: Raised when the MusicXML sidecar contains valid polyphony that the ScoreIR voice model does not yet support.

When a gate fails, the pipeline exits with a non-zero code and writes a `build-ir-failure-diagnostics.v0.1` payload (when `--diagnostics-out` is supplied), alongside developer-facing HTML diagnostic reports.

---

## Release Validation Checklist

Before any code change is merged or released, the following checklist must be satisfied:
1. All 467 public test cases must pass.
2. The local private-safety invariant (`git ls-files fixtures/private work`) must output exactly `fixtures/private/.gitkeep`.
3. The post-serialization quality audit must complete successfully without crashing.
4. No private media files, copyrighted scores, or raw candidate dumps may be committed to Git.
