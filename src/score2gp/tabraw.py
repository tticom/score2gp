from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ir import BoundingBox, Provenance, SourceStage
from .pdf_tab_duration_types import TabDurationEvidence

TABRAW_SCHEMA_VERSION = "tabraw.v0.1"


class TabCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal[
        "fret",
        "chord-symbol",
        "technique-text",
        "candidate-text",
        "visual-vibrato",
        "visual-slide",
    ] = "candidate-text"
    page_index: int | None = Field(default=None, ge=1)
    system_index: int | None = Field(default=None, ge=1)
    staff_index: int | None = Field(default=None, ge=1)
    bar_index: int | None = Field(default=None, ge=1)
    line_index: int | None = Field(default=None, ge=1)
    string: int | None = Field(default=None, ge=1, le=12)
    raw_text: str
    parsed_fret: int | None = Field(default=None, ge=0, le=36)
    x: float | None = None
    y: float | None = None
    bbox: BoundingBox | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_stage: SourceStage = SourceStage.PDF_TEXT
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_evidence(self) -> TabDurationEvidence | None:
        data = self.raw.get("duration_evidence")
        if data is None:
            return None
        if isinstance(data, (TabDurationEvidence, dict)):
            return _parse_tab_duration_evidence(data)
        return None

    def to_provenance(self) -> Provenance:
        return Provenance(
            source_stage=self.source_stage,
            page=self.page_index,
            system_id=f"system-{self.system_index}" if self.system_index is not None else None,
            staff_id=f"staff-{self.staff_index}" if self.staff_index is not None else None,
            bar_index=self.bar_index,
            bbox=self.bbox,
            raw_token_id=self.id,
            raw={
                "kind": self.kind,
                "raw_text": self.raw_text,
                "parsed_fret": self.parsed_fret,
                "string": self.string,
                "x": self.x,
                "y": self.y,
                **self.raw,
            },
            confidence=self.confidence,
        )


class TabRaw(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tabraw.v0.1"] = TABRAW_SCHEMA_VERSION
    source_pdf: str | None = None
    inspection_kind: str | None = None
    pdf_layout_class: str | None = None
    pdf_layout_warnings: list[str] = Field(default_factory=list)
    candidates: list[TabCandidate] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def candidate_ids_are_unique(self) -> "TabRaw":
        ids = [candidate.id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("TabRaw candidate IDs must be unique")
        return self

    @classmethod
    def from_json_file(cls, path: str | Path) -> "TabRaw":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(normalize_tabraw_payload(data))

    def to_json_file(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")


def parse_fret_text(text: str) -> int | None:
    stripped = text.strip()
    if stripped.isdigit():
        value = int(stripped)
        if 0 <= value <= 36:
            return value
    return None


VALID_DURATION_NAMES: set[str] = {
    "whole",
    "half",
    "quarter",
    "eighth",
    "16th",
    "32nd",
    "64th",
    "ambiguous",
}
VALID_SOURCES: set[str] = {
    "visual_morphology",
    "equal_spacing_fallback",
    "ambiguous_conflict",
}
TAB_DURATION_EVIDENCE_FIELDS: set[str] = {
    "duration_name",
    "duration_ticks",
    "stem_present",
    "beam_count",
    "flag_count",
    "confidence",
    "source",
    "is_ambiguous",
    "is_fallback_placeholder",
    "diagnostic_message",
}


def _parse_tab_duration_evidence(data: TabDurationEvidence | dict[str, Any]) -> TabDurationEvidence | None:
    if isinstance(data, TabDurationEvidence):
        data = asdict(data)
    if not isinstance(data, dict):
        return None

    if set(data.keys()) - TAB_DURATION_EVIDENCE_FIELDS:
        return None

    duration_name = data.get("duration_name")
    if duration_name not in VALID_DURATION_NAMES:
        return None

    duration_ticks = data.get("duration_ticks")
    if not isinstance(duration_ticks, int) or isinstance(duration_ticks, bool) or duration_ticks < 0:
        return None

    stem_present = data.get("stem_present", False)
    if not isinstance(stem_present, bool):
        return None

    beam_count = data.get("beam_count", 0)
    if not isinstance(beam_count, int) or isinstance(beam_count, bool) or beam_count < 0:
        return None

    flag_count = data.get("flag_count", 0)
    if not isinstance(flag_count, int) or isinstance(flag_count, bool) or flag_count < 0:
        return None

    confidence = data.get("confidence", 1.0)
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not (0.0 <= confidence <= 1.0):
        return None

    source = data.get("source", "visual_morphology")
    if source not in VALID_SOURCES:
        return None

    is_ambiguous = data.get("is_ambiguous", False)
    if not isinstance(is_ambiguous, bool):
        return None

    is_fallback_placeholder = data.get("is_fallback_placeholder", False)
    if not isinstance(is_fallback_placeholder, bool):
        return None

    diagnostic_message = data.get("diagnostic_message", "")
    if not isinstance(diagnostic_message, str):
        return None

    return TabDurationEvidence(
        duration_name=duration_name,  # type: ignore[arg-type]
        duration_ticks=duration_ticks,
        stem_present=stem_present,
        beam_count=beam_count,
        flag_count=flag_count,
        confidence=float(confidence),
        source=source,  # type: ignore[arg-type]
        is_ambiguous=is_ambiguous,
        is_fallback_placeholder=is_fallback_placeholder,
        diagnostic_message=diagnostic_message,
    )


def normalize_tabraw_payload(data: dict[str, Any]) -> dict[str, Any]:
    if "candidates" in data:
        # If already normalized to the format, still check for fields
        if "pdf_layout_class" not in data:
            data["pdf_layout_class"] = None
        if "pdf_layout_warnings" not in data:
            data["pdf_layout_warnings"] = []
        return data

    candidates = []
    for index, item in enumerate(data.get("items", []), start=1):
        page_index = item.get("page_index") or item.get("page")
        bbox = _normalize_bbox(item.get("bbox"), page_index)
        x, y = _bbox_center(bbox)
        raw_text = item.get("raw_text") or item.get("text") or ""
        parsed_fret = item.get("parsed_fret")
        if parsed_fret is None:
            parsed_fret = parse_fret_text(raw_text)

        raw_meta: dict[str, Any] = {"legacy_item": item}
        if isinstance(item.get("raw"), dict) and "duration_evidence" in item["raw"]:
            raw_meta["duration_evidence"] = item["raw"]["duration_evidence"]
        elif "duration_evidence" in item:
            raw_meta["duration_evidence"] = item["duration_evidence"]

        candidates.append(
            {
                "id": item.get("id") or f"legacy-candidate-{index:04d}",
                "kind": _candidate_kind(raw_text, parsed_fret),
                "page_index": page_index,
                "system_index": item.get("system_index"),
                "staff_index": item.get("staff_index"),
                "bar_index": item.get("bar_index"),
                "line_index": item.get("line_index"),
                "string": item.get("string"),
                "raw_text": raw_text,
                "parsed_fret": parsed_fret,
                "x": item.get("x", x),
                "y": item.get("y", y),
                "bbox": bbox,
                "confidence": item.get("confidence", 0.4),
                "source_stage": item.get("source_stage", SourceStage.PDF_TEXT),
                "raw": raw_meta,
            }
        )

    return {
        "schema_version": TABRAW_SCHEMA_VERSION,
        "source_pdf": data.get("source_pdf"),
        "inspection_kind": data.get("inspection_kind"),
        "pdf_layout_class": data.get("pdf_layout_class"),
        "pdf_layout_warnings": data.get("pdf_layout_warnings", []),
        "candidates": candidates,
        "warnings": data.get("warnings", []),
    }


def make_tab_candidate(
    *,
    candidate_id: str,
    raw_text: str,
    page_index: int | None,
    bbox_values: list[float] | tuple[float, float, float, float] | None,
    confidence: float,
    system_index: int | None = None,
    staff_index: int | None = None,
    bar_index: int | None = None,
    line_index: int | None = None,
    string: int | None = None,
    kind: str | None = None,
    raw: dict[str, Any] | None = None,
    duration_evidence: TabDurationEvidence | dict[str, Any] | None = None,
) -> TabCandidate:
    bbox = _normalize_bbox(bbox_values, page_index)
    x, y = _bbox_center(bbox)
    parsed_fret = parse_fret_text(raw_text)

    raw_dict = dict(raw) if raw else {}

    if duration_evidence is not None:
        if isinstance(duration_evidence, (TabDurationEvidence, dict)):
            parsed = _parse_tab_duration_evidence(duration_evidence)
            if parsed is None:
                raise ValueError(f"Invalid duration_evidence payload: {duration_evidence}")
            raw_dict["duration_evidence"] = asdict(parsed)
        else:
            raise TypeError(
                f"duration_evidence must be TabDurationEvidence or dict, got {type(duration_evidence).__name__}"
            )
    elif "duration_evidence" in raw_dict:
        existing = raw_dict["duration_evidence"]
        if isinstance(existing, (TabDurationEvidence, dict)):
            parsed = _parse_tab_duration_evidence(existing)
            if parsed is None:
                raise ValueError(f"Invalid duration_evidence in raw metadata: {existing}")
            raw_dict["duration_evidence"] = asdict(parsed)

    return TabCandidate(
        id=candidate_id,
        kind=kind or _candidate_kind(raw_text, parsed_fret),
        page_index=page_index,
        system_index=system_index,
        staff_index=staff_index,
        bar_index=bar_index,
        line_index=line_index,
        string=string,
        raw_text=raw_text,
        parsed_fret=parsed_fret,
        x=x,
        y=y,
        bbox=bbox,
        confidence=confidence,
        raw=raw_dict,
    )


def _candidate_kind(raw_text: str, parsed_fret: int | None) -> str:
    lower = raw_text.lower()
    if parsed_fret is not None:
        return "fret"
    stripped = raw_text.strip()
    technique_tokens = ("slide", "bend", "vib", "let", "ring", "hammer", "pull", "p.m.", "palm")
    if any(token in lower for token in technique_tokens):
        if "string" not in lower:
            return "technique-text"
    if stripped.lower().rstrip(".") in {"h", "p", "pm", "/", "\\", "~", "b", "r", "v", "s", "sl", "full"}:
        return "technique-text"
    if _looks_like_chord_symbol(stripped):
        return "chord-symbol"
    return "candidate-text"


def _looks_like_chord_symbol(text: str) -> bool:
    return bool(
        re.fullmatch(
            r"[A-G](?:#|b)?(?:maj|min|m|dim|aug|sus|add)?(?:2|4|5|6|7|9|11|13)?(?:/[A-G](?:#|b)?)?",
            text,
        )
    )


def _normalize_bbox(
    value: Any,
    page_index: int | None,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if page_index is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 4:
        x0, y0, x1, y1 = value
        return {"page": page_index, "x0": x0, "y0": y0, "x1": x1, "y1": y1}
    return None


def _bbox_center(bbox: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if bbox is None:
        return None, None
    return (
        (float(bbox["x0"]) + float(bbox["x1"])) / 2,
        (float(bbox["y0"]) + float(bbox["y1"])) / 2,
    )


def make_visual_vibrato_candidate(
    *,
    candidate_id: str,
    raw_text: str = "vibrato",
    page_index: int | None = None,
    system_index: int | None = None,
    staff_index: int | None = None,
    bar_index: int | None = None,
    bbox_values: list[float] | tuple[float, float, float, float] | None = None,
    confidence: float = 0.85,
    cycles: int = 2,
    amplitude: float = 1.0,
) -> TabCandidate:
    return make_tab_candidate(
        candidate_id=candidate_id,
        raw_text=raw_text,
        page_index=page_index,
        system_index=system_index,
        staff_index=staff_index,
        bar_index=bar_index,
        bbox_values=bbox_values,
        confidence=confidence,
        kind="visual-vibrato",
        raw={"cycles": cycles, "amplitude": amplitude},
    )


def make_visual_slide_candidate(
    *,
    candidate_id: str,
    raw_text: str = "slide",
    page_index: int | None = None,
    system_index: int | None = None,
    staff_index: int | None = None,
    bar_index: int | None = None,
    string: int | None = None,
    bbox_values: list[float] | tuple[float, float, float, float] | None = None,
    confidence: float = 0.85,
    slope: float = 1.0,
    direction: str = "up",
) -> TabCandidate:
    return make_tab_candidate(
        candidate_id=candidate_id,
        raw_text=raw_text,
        page_index=page_index,
        system_index=system_index,
        staff_index=staff_index,
        bar_index=bar_index,
        string=string,
        bbox_values=bbox_values,
        confidence=confidence,
        kind="visual-slide",
        raw={"slope": slope, "direction": direction},
    )
