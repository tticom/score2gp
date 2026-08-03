from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from .musicxml import parse_musicxml, analyze_musicxml_timing
from .tabraw import TabRaw, TABRAW_SCHEMA_VERSION
from .build_ir import build_ir_with_diagnostics_from_imports


class SidecarEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "passed",
        "empty_musicxml",
        "timing_invalid",
        "handoff_refused",
        "non_deterministic",
    ]
    note_count: int = Field(ge=0)
    rest_count: int = Field(ge=0)
    pitch_count: int = Field(ge=0)
    measure_count: int = Field(ge=0)
    score_ir_event_count: int = Field(ge=0)
    matched_tab_candidate_count: int = Field(ge=0)
    refusal_reason: str | None = None
    provenance: dict = Field(default_factory=dict)


def _compute_sha256(path: Path) -> str | None:
    try:
        if path.exists() and path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        pass
    return None


def _evaluate_once(
    xml_path: Path, pdf_fixture_path: Path | None = None
) -> tuple[
    Literal["passed", "empty_musicxml", "timing_invalid", "handoff_refused", "non_deterministic"],
    int,
    int,
    int,
    int,
    int,
    int,
    str | None,
    dict,
]:
    xml_path = Path(xml_path)
    pdf_path = Path(pdf_fixture_path) if pdf_fixture_path is not None else None

    xml_sha = _compute_sha256(xml_path)
    pdf_sha = _compute_sha256(pdf_path) if pdf_path is not None else None

    provenance = {
        "evaluator_version": "mxs00-v1",
        "xml_path": str(xml_path),
        "xml_sha256": xml_sha,
        "pdf_fixture_path": str(pdf_path) if pdf_path is not None else None,
        "pdf_fixture_sha256": pdf_sha,
    }

    # 1. Xml/MXL Parsing Check
    if not xml_path.exists():
        return (
            "handoff_refused",
            0,
            0,
            0,
            0,
            0,
            0,
            f"xml_file_not_found: {xml_path.name}",
            provenance,
        )

    try:
        musicxml = parse_musicxml(xml_path)
    except Exception as exc:
        return (
            "handoff_refused",
            0,
            0,
            0,
            0,
            0,
            0,
            f"unparseable_xml: {exc}",
            provenance,
        )

    # 2. Count notes, rests, pitches, measures
    measure_count = sum(len(part.measures) for part in musicxml.parts)
    note_count = sum(
        1
        for part in musicxml.parts
        for measure in part.measures
        for note in measure.notes
        if not note.is_rest and not note.is_suppressed
    )
    rest_count = sum(
        1
        for part in musicxml.parts
        for measure in part.measures
        for note in measure.notes
        if note.is_rest and not note.is_suppressed
    )
    pitch_count = sum(
        1
        for part in musicxml.parts
        for measure in part.measures
        for note in measure.notes
        if note.pitch is not None and not note.is_suppressed
    )

    # Zero Note/Rest Check
    if note_count == 0 and rest_count == 0:
        return (
            "empty_musicxml",
            0,
            0,
            0,
            measure_count,
            0,
            0,
            "zero_notes_and_rests",
            provenance,
        )

    # 3. Timing Validation
    try:
        timing_issues = analyze_musicxml_timing(musicxml)
        has_error_timing_issue = any(issue.severity == "error" for issue in timing_issues)
        has_invalid_divisions = any(
            m.divisions <= 0 or m.divisions_missing or m.divisions_changed_mid_measure or m.unbalanced_backup_forward
            for part in musicxml.parts
            for m in part.measures
        )
        if has_error_timing_issue or has_invalid_divisions:
            return (
                "timing_invalid",
                note_count,
                rest_count,
                pitch_count,
                measure_count,
                0,
                0,
                "measure_timing_error",
                provenance,
            )
    except Exception as exc:
        return (
            "timing_invalid",
            note_count,
            rest_count,
            pitch_count,
            measure_count,
            0,
            0,
            f"measure_timing_error: {exc}",
            provenance,
        )

    # 4. Conversion Handoff Check
    if pdf_path is not None and pdf_path.exists():
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                from .pdf import extract_tab

                raw_dict = extract_tab(pdf_path, Path(tmp_dir))
                tabraw = TabRaw.model_validate(raw_dict)
        except Exception:
            tabraw = TabRaw(schema_version=TABRAW_SCHEMA_VERSION, source_pdf=str(pdf_path), candidates=[])
    else:
        tabraw = TabRaw(schema_version=TABRAW_SCHEMA_VERSION, source_pdf=str(xml_path), candidates=[])

    try:
        score_ir, diagnostics = build_ir_with_diagnostics_from_imports(musicxml, tabraw)
        score_ir_event_count = sum(len(bar.events) for bar in score_ir.bars)
    except Exception as exc:
        return (
            "handoff_refused",
            note_count,
            rest_count,
            pitch_count,
            measure_count,
            0,
            0,
            f"handoff_error: {exc}",
            provenance,
        )

    if score_ir_event_count == 0 and (note_count > 0 or rest_count > 0):
        return (
            "handoff_refused",
            note_count,
            rest_count,
            pitch_count,
            measure_count,
            0,
            0,
            "zero_score_ir_events",
            provenance,
        )

    matched_tab_candidate_count = sum(
        1
        for bar in score_ir.bars
        for event in bar.events
        if hasattr(event, "notes")
        for n in getattr(event, "notes", [])
        if getattr(n, "fret", None) is not None
    )

    return (
        "passed",
        note_count,
        rest_count,
        pitch_count,
        measure_count,
        score_ir_event_count,
        matched_tab_candidate_count,
        None,
        provenance,
    )


def evaluate_sidecar(
    xml_path: Path, pdf_fixture_path: Path | None = None
) -> SidecarEvaluationResult:
    xml_path = Path(xml_path)
    pdf_fixture_path = Path(pdf_fixture_path) if pdf_fixture_path is not None else None

    # Run 1
    res1 = _evaluate_once(xml_path, pdf_fixture_path)

    # Run 2 for determinism check
    res2 = _evaluate_once(xml_path, pdf_fixture_path)

    # Compare key fields across runs
    status1, notes1, rests1, pitches1, measures1, ir_events1, matched1, refusal1, prov1 = res1
    status2, notes2, rests2, pitches2, measures2, ir_events2, matched2, refusal2, prov2 = res2

    if (status1, notes1, rests1, pitches1, measures1, ir_events1, matched1) != (
        status2,
        notes2,
        rests2,
        pitches2,
        measures2,
        ir_events2,
        matched2,
    ):
        return SidecarEvaluationResult(
            status="non_deterministic",
            note_count=notes1,
            rest_count=rests1,
            pitch_count=pitches1,
            measure_count=measures1,
            score_ir_event_count=ir_events1,
            matched_tab_candidate_count=matched1,
            refusal_reason="result_discrepancy_across_runs",
            provenance=prov1,
        )

    return SidecarEvaluationResult(
        status=status1,
        note_count=notes1,
        rest_count=rests1,
        pitch_count=pitches1,
        measure_count=measures1,
        score_ir_event_count=ir_events1,
        matched_tab_candidate_count=matched1,
        refusal_reason=refusal1,
        provenance=prov1,
    )
