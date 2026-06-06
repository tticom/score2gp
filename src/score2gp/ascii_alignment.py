from __future__ import annotations

from fractions import Fraction
import html
import json
from pathlib import Path
import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .musicxml import (
    MusicXmlImport,
    MusicXmlMeasure,
    MusicXmlNote,
    MusicXmlTimingIssue,
    analyze_musicxml_timing,
    parse_musicxml,
)
from .tabraw import TabCandidate, TabRaw

ALIGNMENT_SCHEMA_VERSION = "ascii-musicxml-alignment.v0.1"
ALIGNMENT_TOLERANCE = 0.08
AMBIGUOUS_DISTANCE_EPSILON = 0.015


def compute_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


class AsciiMusicXmlAlignmentWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"


class AsciiMusicXmlCandidateMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    string: int | None = None
    fret: int | None = None
    ascii_block_id: str | None = None
    ascii_measure_segment_id: int | None = None
    ascii_global_measure_index: int | None = None
    ascii_normalized_column_position: float | None = None
    ascii_measure_normalized_column: float | None = None
    musicxml_measure_index: int | None = None
    musicxml_measure_number: str | None = None
    nearest_musicxml_note_ids: list[str] = Field(default_factory=list)
    nearest_musicxml_onset_ticks: int | None = None
    nearest_musicxml_normalized_onset: float | None = None
    onset_distance: float | None = None
    tolerance: float = ALIGNMENT_TOLERANCE
    result: Literal["compatible", "ambiguous", "incompatible", "unavailable"]
    confidence: float = Field(ge=0.0, le=1.0)
    warning_codes: list[str] = Field(default_factory=list)


class AsciiMusicXmlAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ascii-musicxml-alignment.v0.1"] = ALIGNMENT_SCHEMA_VERSION
    source_tabraw_file: str | None = None
    source_musicxml_file: str
    source_pdf_hash: str | None = None
    source_musicxml_hash: str | None = None
    parser_versions: dict[str, str] = Field(default_factory=dict)
    tracks_considered: list[str] = Field(default_factory=list)
    parts_considered: list[str] = Field(default_factory=list)
    bars_considered: int = Field(ge=0)
    ascii_block_ids: list[str] = Field(default_factory=list)
    ascii_measure_segment_ids: list[str] = Field(default_factory=list)
    musicxml_measure_ids: list[str] = Field(default_factory=list)
    alignment_attempted: bool = False
    scoreir_written: bool = False
    tolerance: float = ALIGNMENT_TOLERANCE
    overall_status: Literal["compatible", "partial", "ambiguous", "incompatible", "unavailable"]
    summary_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[AsciiMusicXmlAlignmentWarning] = Field(default_factory=list)
    candidate_mappings: list[AsciiMusicXmlCandidateMapping] = Field(default_factory=list)
    musicxml_timing_issues: list[dict[str, Any]] = Field(default_factory=list)

    def to_json_file(self, path: str | Path) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.model_dump_json(indent=2), encoding="utf-8")


def align_ascii_musicxml_files(
    *,
    tabraw_path: str | Path,
    musicxml_path: str | Path,
    out_dir: str | Path | None = None,
) -> AsciiMusicXmlAlignment:
    tabraw = TabRaw.from_json_file(tabraw_path)
    musicxml = parse_musicxml(musicxml_path)
    alignment = align_ascii_musicxml(
        tabraw=tabraw,
        musicxml=musicxml,
        tabraw_source=str(tabraw_path),
        musicxml_source=str(musicxml_path),
    )
    if out_dir is not None:
        write_ascii_musicxml_alignment_outputs(alignment, out_dir)
    return alignment


def align_ascii_musicxml(
    *,
    tabraw: TabRaw,
    musicxml: MusicXmlImport,
    tabraw_source: str | None = None,
    musicxml_source: str | None = None,
) -> AsciiMusicXmlAlignment:
    warnings: list[AsciiMusicXmlAlignmentWarning] = []
    timing_issues = analyze_musicxml_timing(musicxml)
    fatal_timing_issues = [issue for issue in timing_issues if issue.severity == "error"]
    if fatal_timing_issues:
        warnings.append(
            AsciiMusicXmlAlignmentWarning(
                code="musicxml_timing_risk",
                message="MusicXML timing risk prevents ASCII/MusicXML alignment proof.",
                severity="error",
            )
        )
        return _alignment_payload(
            tabraw=tabraw,
            musicxml=musicxml,
            tabraw_source=tabraw_source,
            musicxml_source=musicxml_source,
            warnings=warnings,
            candidate_mappings=[],
            status="unavailable",
            alignment_attempted=False,
            timing_issues=timing_issues,
        )

    candidates = _playable_ascii_candidates(tabraw)
    if not candidates:
        warnings.append(
            AsciiMusicXmlAlignmentWarning(
                code="ascii_tab_candidates_missing",
                message="No playable ASCII-tab fret candidates were available for alignment proof.",
                severity="warning",
            )
        )
        return _alignment_payload(
            tabraw=tabraw,
            musicxml=musicxml,
            tabraw_source=tabraw_source,
            musicxml_source=musicxml_source,
            warnings=warnings,
            candidate_mappings=[],
            status="unavailable",
            alignment_attempted=False,
            timing_issues=timing_issues,
        )

    unavailable = [candidate for candidate in candidates if _ascii_timing_status(candidate) == "timing_unavailable"]
    partial_grouping = [
        candidate
        for candidate in candidates
        if candidate.raw.get("grouping_status") == "partial_ascii_tab_grouping"
        or "partial_ascii_tab_grouping" in _candidate_warning_codes(candidate)
    ]
    if partial_grouping:
        warnings.append(
            AsciiMusicXmlAlignmentWarning(
                code="partial_ascii_tab_grouping",
                message="ASCII-tab grouping is partial; alignment proof is unavailable.",
                severity="error",
            )
        )
    if unavailable:
        warnings.append(
            AsciiMusicXmlAlignmentWarning(
                code="ascii_tab_timing_unavailable",
                message="ASCII-tab candidates lack usable measure timing evidence.",
                severity="error",
            )
        )
    if partial_grouping or unavailable:
        mappings = [_unavailable_mapping(candidate, "ascii_tab_timing_unavailable") for candidate in candidates]
        return _alignment_payload(
            tabraw=tabraw,
            musicxml=musicxml,
            tabraw_source=tabraw_source,
            musicxml_source=musicxml_source,
            warnings=warnings,
            candidate_mappings=mappings,
            status="unavailable",
            alignment_attempted=False,
            timing_issues=timing_issues,
        )

    part = musicxml.parts[0] if musicxml.parts else None
    if part is None:
        warnings.append(
            AsciiMusicXmlAlignmentWarning(
                code="musicxml_parts_missing",
                message="MusicXML contains no parts to compare with ASCII-tab evidence.",
                severity="error",
            )
        )
        mappings = [_unavailable_mapping(candidate, "musicxml_parts_missing") for candidate in candidates]
        return _alignment_payload(
            tabraw=tabraw,
            musicxml=musicxml,
            tabraw_source=tabraw_source,
            musicxml_source=musicxml_source,
            warnings=warnings,
            candidate_mappings=mappings,
            status="unavailable",
            alignment_attempted=False,
            timing_issues=timing_issues,
        )

    segment_keys = _ascii_segment_keys(candidates)
    if len(segment_keys) != len(part.measures):
        warnings.append(
            AsciiMusicXmlAlignmentWarning(
                code="ascii_musicxml_measure_count_mismatch",
                message=(
                    f"ASCII measure segment count {len(segment_keys)} does not match "
                    f"MusicXML measure count {len(part.measures)}."
                ),
                severity="error",
            )
        )

    segment_to_measure = {
        key: part.measures[index]
        for index, key in enumerate(segment_keys)
        if index < len(part.measures)
    }
    mappings = [
        _candidate_mapping(candidate, segment_to_measure, segment_keys)
        for candidate in candidates
    ]
    mappings = _apply_onset_capacity_checks(mappings, part.measures)
    status = _overall_status(mappings, warnings, len(candidates), _pitched_event_count(part.measures))
    if status == "compatible":
        warnings.append(
            AsciiMusicXmlAlignmentWarning(
                code="ascii_musicxml_alignment_compatible",
                message=(
                    "ASCII column evidence is compatible with MusicXML onsets in this controlled fixture; "
                    "this is diagnostic proof only, not ScoreIR conversion permission."
                ),
                severity="info",
            )
        )
    return _alignment_payload(
        tabraw=tabraw,
        musicxml=musicxml,
        tabraw_source=tabraw_source,
        musicxml_source=musicxml_source,
        warnings=warnings,
        candidate_mappings=mappings,
        status=status,
        alignment_attempted=True,
        timing_issues=timing_issues,
    )


def write_ascii_musicxml_alignment_outputs(alignment: AsciiMusicXmlAlignment, out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "ascii_musicxml_alignment.json"
    warnings_path = out / "warnings.json"
    html_path = out / "alignment-diagnostics.html"
    alignment.to_json_file(json_path)
    if alignment.warnings:
        warnings_path.write_text(
            json.dumps([warning.model_dump(mode="json", exclude_none=True) for warning in alignment.warnings], indent=2),
            encoding="utf-8",
        )
    write_ascii_musicxml_alignment_html(html_path, alignment)
    return {
        "alignment": str(json_path),
        "warnings": str(warnings_path) if alignment.warnings else "",
        "html": str(html_path),
    }


def write_ascii_musicxml_alignment_html(path: str | Path, alignment: AsciiMusicXmlAlignment) -> None:
    warning_items = "\n".join(
        f"<li><strong>{html.escape(warning.code)}</strong>: {html.escape(warning.message)}</li>"
        for warning in alignment.warnings
    )
    body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>ASCII/MusicXML Alignment Diagnostics</title></head>
<body>
<h1>ASCII/MusicXML Alignment Diagnostics</h1>
<p>This report checks whether ASCII character-column evidence is compatible with MusicXML onsets. It does not create ScoreIR.</p>
<dl>
  <dt>Status</dt><dd>{html.escape(alignment.overall_status)}</dd>
  <dt>Alignment attempted</dt><dd>{html.escape(str(alignment.alignment_attempted))}</dd>
  <dt>ScoreIR written</dt><dd>{html.escape(str(alignment.scoreir_written))}</dd>
  <dt>TabRaw</dt><dd>{html.escape(str(alignment.source_tabraw_file))}</dd>
  <dt>MusicXML</dt><dd>{html.escape(alignment.source_musicxml_file)}</dd>
  <dt>Tolerance</dt><dd>{alignment.tolerance}</dd>
</dl>
<h2>Summary Counts</h2>
<pre>{html.escape(json.dumps(alignment.summary_counts, indent=2, sort_keys=True))}</pre>
<h2>Warnings</h2>
<ul>{warning_items}</ul>
<h2>Candidate Mappings</h2>
<pre>{html.escape(json.dumps([mapping.model_dump(mode="json", exclude_none=True) for mapping in alignment.candidate_mappings], indent=2))}</pre>
</body>
</html>
"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")


def _alignment_payload(
    *,
    tabraw: TabRaw,
    musicxml: MusicXmlImport,
    tabraw_source: str | None,
    musicxml_source: str | None,
    warnings: list[AsciiMusicXmlAlignmentWarning],
    candidate_mappings: list[AsciiMusicXmlCandidateMapping],
    status: Literal["compatible", "partial", "ambiguous", "incompatible", "unavailable"],
    alignment_attempted: bool,
    timing_issues: list[MusicXmlTimingIssue],
) -> AsciiMusicXmlAlignment:
    candidates = _playable_ascii_candidates(tabraw)
    part = musicxml.parts[0] if musicxml.parts else None
    summary_counts = _summary_counts(candidates, musicxml, candidate_mappings)

    pdf_hash = None
    if tabraw.source_pdf:
        p_path = Path(tabraw.source_pdf)
        if p_path.exists():
            pdf_hash = compute_sha256(p_path)

    mxml_hash = None
    mxml_path_str = musicxml_source or musicxml.source_path
    if mxml_path_str:
        m_path = Path(mxml_path_str)
        if m_path.exists():
            mxml_hash = compute_sha256(m_path)

    return AsciiMusicXmlAlignment(
        source_tabraw_file=tabraw_source,
        source_musicxml_file=musicxml_source or musicxml.source_path,
        source_pdf_hash=pdf_hash,
        source_musicxml_hash=mxml_hash,
        parser_versions={
            "ascii_tab": "ascii-tab.v0.1",
            "ascii_timing": "ascii-timing.v0.1",
            "musicxml_importer": "musicxml-import.v0.1",
        },
        tracks_considered=[part.name] if part is not None else [],
        parts_considered=[part.id] if part is not None else [],
        bars_considered=len(part.measures) if part is not None else 0,
        ascii_block_ids=sorted({str(candidate.raw.get("ascii_block_id")) for candidate in candidates if candidate.raw.get("ascii_block_id")}),
        ascii_measure_segment_ids=[
            f"{block_id}:m{segment_id}"
            for block_id, segment_id in _ascii_segment_keys(candidates)
        ],
        musicxml_measure_ids=[measure.number for measure in part.measures] if part is not None else [],
        alignment_attempted=alignment_attempted,
        scoreir_written=False,
        overall_status=status,
        summary_counts=summary_counts,
        warnings=warnings,
        candidate_mappings=candidate_mappings,
        musicxml_timing_issues=[issue.model_dump(mode="json", exclude_none=True) for issue in timing_issues],
    )


def _playable_ascii_candidates(tabraw: TabRaw) -> list[TabCandidate]:
    return [
        candidate
        for candidate in tabraw.candidates
        if candidate.parsed_fret is not None
        and candidate.raw.get("parser_version") == "ascii-tab.v0.1"
    ]


def _ascii_timing_status(candidate: TabCandidate) -> str | None:
    value = candidate.raw.get("ascii_timing_status")
    return value if isinstance(value, str) else None


def _candidate_warning_codes(candidate: TabCandidate) -> list[str]:
    raw = candidate.raw.get("ascii_timing_warnings")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw]


def _ascii_segment_keys(candidates: list[TabCandidate]) -> list[tuple[str, int]]:
    keys = {
        (str(candidate.raw.get("ascii_block_id")), int(candidate.raw.get("ascii_measure_segment_id")))
        for candidate in candidates
        if candidate.raw.get("ascii_block_id") and candidate.raw.get("ascii_measure_segment_id") is not None
    }
    return sorted(keys, key=lambda item: (item[0], item[1]))


def _candidate_mapping(
    candidate: TabCandidate,
    segment_to_measure: dict[tuple[str, int], MusicXmlMeasure],
    segment_keys: list[tuple[str, int]],
) -> AsciiMusicXmlCandidateMapping:
    raw = candidate.raw
    block_id = str(raw.get("ascii_block_id")) if raw.get("ascii_block_id") else None
    segment_id = raw.get("ascii_measure_segment_id")
    segment_id = int(segment_id) if segment_id is not None else None
    segment_key = (block_id, segment_id) if block_id is not None and segment_id is not None else None
    global_index = segment_keys.index(segment_key) + 1 if segment_key in segment_keys else None
    normalized = _optional_float(raw.get("ascii_measure_normalized_column"))
    base_kwargs = _mapping_base_kwargs(candidate, block_id, segment_id, global_index, normalized)

    if segment_key is None or normalized is None:
        return AsciiMusicXmlCandidateMapping(
            **base_kwargs,
            result="unavailable",
            confidence=0.2,
            warning_codes=["ascii_measure_segment_missing"],
        )
    measure = segment_to_measure.get(segment_key)
    if measure is None:
        return AsciiMusicXmlCandidateMapping(
            **base_kwargs,
            result="incompatible",
            confidence=0.25,
            warning_codes=["ascii_musicxml_measure_count_mismatch"],
        )
    onset_groups = _musicxml_onset_groups(measure)
    if not onset_groups:
        return AsciiMusicXmlCandidateMapping(
            **base_kwargs,
            musicxml_measure_index=measure.index,
            musicxml_measure_number=measure.number,
            result="incompatible",
            confidence=0.25,
            warning_codes=["musicxml_pitched_onsets_missing"],
        )
    distances = sorted(
        ((abs(normalized - group["normalized"]), group) for group in onset_groups),
        key=lambda item: (item[0], item[1]["onset_ticks"]),
    )
    nearest_distance, nearest = distances[0]
    warning_codes = list(_candidate_warning_codes(candidate))
    if nearest_distance > ALIGNMENT_TOLERANCE:
        result: Literal["compatible", "ambiguous", "incompatible", "unavailable"] = "incompatible"
        confidence = 0.3
        warning_codes.append("ascii_musicxml_onset_distance_exceeds_tolerance")
    elif len(distances) > 1 and abs(distances[1][0] - nearest_distance) <= AMBIGUOUS_DISTANCE_EPSILON:
        result = "ambiguous"
        confidence = 0.45
        warning_codes.append("ambiguous_ascii_musicxml_onset")
    elif "ambiguous_ascii_tab_timing" in warning_codes:
        result = "ambiguous"
        confidence = 0.45
    else:
        result = "compatible"
        confidence = max(0.5, 1.0 - nearest_distance)
    return AsciiMusicXmlCandidateMapping(
        **base_kwargs,
        musicxml_measure_index=measure.index,
        musicxml_measure_number=measure.number,
        nearest_musicxml_note_ids=list(nearest["note_ids"]),
        nearest_musicxml_onset_ticks=int(nearest["onset_ticks"]),
        nearest_musicxml_normalized_onset=round(float(nearest["normalized"]), 4),
        onset_distance=round(float(nearest_distance), 4),
        result=result,
        confidence=round(confidence, 3),
        warning_codes=sorted(set(warning_codes)),
    )


def _mapping_base_kwargs(
    candidate: TabCandidate,
    block_id: str | None,
    segment_id: int | None,
    global_index: int | None,
    normalized: float | None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate.id,
        "string": candidate.string,
        "fret": candidate.parsed_fret,
        "ascii_block_id": block_id,
        "ascii_measure_segment_id": segment_id,
        "ascii_global_measure_index": global_index,
        "ascii_normalized_column_position": _optional_float(candidate.raw.get("ascii_normalized_column_position")),
        "ascii_measure_normalized_column": normalized,
    }


def _unavailable_mapping(candidate: TabCandidate, warning_code: str) -> AsciiMusicXmlCandidateMapping:
    raw = candidate.raw
    segment_id = raw.get("ascii_measure_segment_id")
    return AsciiMusicXmlCandidateMapping(
        candidate_id=candidate.id,
        string=candidate.string,
        fret=candidate.parsed_fret,
        ascii_block_id=str(raw.get("ascii_block_id")) if raw.get("ascii_block_id") else None,
        ascii_measure_segment_id=int(segment_id) if segment_id is not None else None,
        ascii_normalized_column_position=_optional_float(raw.get("ascii_normalized_column_position")),
        ascii_measure_normalized_column=_optional_float(raw.get("ascii_measure_normalized_column")),
        result="unavailable",
        confidence=0.2,
        warning_codes=sorted(set([warning_code, *_candidate_warning_codes(candidate)])),
    )


def _apply_onset_capacity_checks(
    mappings: list[AsciiMusicXmlCandidateMapping],
    measures: list[MusicXmlMeasure],
) -> list[AsciiMusicXmlCandidateMapping]:
    capacity: dict[tuple[int, int], int] = {}
    for measure in measures:
        for group in _musicxml_onset_groups(measure):
            capacity[(measure.index, int(group["onset_ticks"]))] = int(group["event_count"])
    grouped: dict[tuple[int, int], list[AsciiMusicXmlCandidateMapping]] = {}
    for mapping in mappings:
        if mapping.result != "compatible":
            continue
        if mapping.musicxml_measure_index is None or mapping.nearest_musicxml_onset_ticks is None:
            continue
        key = (mapping.musicxml_measure_index, mapping.nearest_musicxml_onset_ticks)
        grouped.setdefault(key, []).append(mapping)
    replacements: dict[str, AsciiMusicXmlCandidateMapping] = {}
    for key, values in grouped.items():
        if len(values) <= capacity.get(key, 0):
            continue
        for mapping in values:
            replacements[mapping.candidate_id] = mapping.model_copy(
                update={
                    "result": "ambiguous",
                    "confidence": min(mapping.confidence, 0.45),
                    "warning_codes": sorted(set([*mapping.warning_codes, "ascii_musicxml_onset_capacity_ambiguous"])),
                }
            )
    if not replacements:
        return mappings
    return [replacements.get(mapping.candidate_id, mapping) for mapping in mappings]


def _musicxml_onset_groups(measure: MusicXmlMeasure) -> list[dict[str, Any]]:
    expected = _expected_measure_duration_divisions(measure)
    if expected is None:
        return []
    groups: dict[int, list[MusicXmlNote]] = {}
    for note in measure.notes:
        if note.is_rest or note.pitch is None or note.grace:
            continue
        groups.setdefault(note.onset_divisions, []).append(note)
    result = []
    for onset, notes in sorted(groups.items()):
        onset_ticks, exact = notes[0].onset_ticks(measure.divisions)
        result.append(
            {
                "onset_divisions": onset,
                "onset_ticks": onset_ticks,
                "onset_ticks_exact": exact,
                "normalized": float(Fraction(onset, expected)),
                "event_count": len(notes),
                "note_ids": [note.id for note in notes],
            }
        )
    return result


def _expected_measure_duration_divisions(measure: MusicXmlMeasure) -> int | None:
    value = Fraction(measure.time_signature.numerator * 4 * measure.divisions, measure.time_signature.denominator)
    if value.denominator != 1:
        return None
    return int(value)


def _pitched_event_count(measures: list[MusicXmlMeasure]) -> int:
    return sum(len(_musicxml_onset_groups(measure)) for measure in measures)


def _pitched_note_count(measures: list[MusicXmlMeasure]) -> int:
    return sum(
        1
        for measure in measures
        for note in measure.notes
        if not note.is_rest and note.pitch is not None and not note.grace
    )


def _overall_status(
    mappings: list[AsciiMusicXmlCandidateMapping],
    warnings: list[AsciiMusicXmlAlignmentWarning],
    ascii_candidate_count: int,
    musicxml_onset_group_count: int,
) -> Literal["compatible", "partial", "ambiguous", "incompatible", "unavailable"]:
    if any(warning.severity == "error" and warning.code == "ascii_musicxml_measure_count_mismatch" for warning in warnings):
        return "incompatible"
    if not mappings:
        return "unavailable"
    result_counts: dict[str, int] = {}
    for mapping in mappings:
        result_counts[mapping.result] = result_counts.get(mapping.result, 0) + 1
    if result_counts.get("incompatible"):
        return "incompatible"
    if result_counts.get("ambiguous"):
        return "ambiguous"
    if result_counts.get("unavailable") == len(mappings):
        return "unavailable"
    if result_counts.get("unavailable"):
        return "partial"
    if result_counts.get("compatible") == ascii_candidate_count and musicxml_onset_group_count > 0:
        return "compatible"
    return "partial"


def _summary_counts(
    candidates: list[TabCandidate],
    musicxml: MusicXmlImport,
    mappings: list[AsciiMusicXmlCandidateMapping],
) -> dict[str, int]:
    part = musicxml.parts[0] if musicxml.parts else None
    measures = part.measures if part is not None else []
    result_counts = {"compatible": 0, "ambiguous": 0, "incompatible": 0, "unavailable": 0}
    for mapping in mappings:
        result_counts[mapping.result] = result_counts.get(mapping.result, 0) + 1
    return {
        "ascii_candidates": len(candidates),
        "musicxml_events": _pitched_note_count(measures),
        "musicxml_onset_groups": _pitched_event_count(measures),
        "compatible_mappings": result_counts.get("compatible", 0),
        "ambiguous_mappings": result_counts.get("ambiguous", 0),
        "incompatible_mappings": result_counts.get("incompatible", 0),
        "unavailable_mappings": result_counts.get("unavailable", 0),
    }


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
