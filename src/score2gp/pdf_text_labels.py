"""Read printed beat annotations from PDF text spans, without reference GP data."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re
from typing import Any

import pymupdf

from .ir import Bar, Provenance, ScoreIR, SourceStage, WarningItem


_ANNOTATION_BAND_STAFF_SPACES = 5
_STAFF_LEFT_ALLOWANCE_PT = 5
_BAR_BOUNDARY_INSET_PT = 1
_BEAT_DISTANCE_MARGIN_PT = 2
_LABEL_MIN_FONT_SIZE_PT = 7
_LABEL_MAX_FONT_SIZE_PT = 15
_TITLE_MIN_FONT_SIZE_PT = 16

_TECHNIQUE = re.compile(r"(?i)^(?:h|p|sl\.?|s|b|r|tr|p\.?m\.?|let ring|vib\.?|t|tap|rit\.?|ppp?|mp|mf|fff?)$")
_CHORD = re.compile(r"(?i)^[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add|ø)?\d*(?:alt)?(?:[/()][A-G#b0-9mø]+\)?)?$")
_TEMPO = re.compile(r"(?i)^(?:(?:[♩♪♫\s.]*|[A-GQqEe])=\s*\d+|(?:largo|andante|moderato|allegro|presto)\b.*)$")
_FURNITURE = re.compile(r"(?i)^(?:standard tuning|tuning\s*:.*|(?:music|words|lyrics|transcribed|arranged) by\b.*|copyright\b.*|©.*|all rights reserved.*)$")
_BARE_TIMESTAMP = re.compile(r"^\[\d+:[0-5]\d\]$")


def _classify(text: str, font: str, size: float, above_system: bool, *,
              direction: tuple[float, float] = (1.0, 0.0)) -> str:
    if _TEMPO.fullmatch(text):
        return "pdf_text_tempo"
    timestamp = bool(_BARE_TIMESTAMP.fullmatch(text))
    if not text or (not timestamp and not any(ch.isalpha() for ch in text)):
        return "pdf_text_non_label_glyph"
    if any("\ue000" <= ch <= "\uf8ff" for ch in text):
        return "pdf_text_music_symbol"
    if any(token in font.lower() for token in ("bravura", "maestro", "musical", "symbol")):
        return "pdf_text_music_symbol"
    if _TECHNIQUE.fullmatch(text):
        return "pdf_text_technique"
    if _CHORD.fullmatch(text.replace(" ", "")):
        return "pdf_text_chord"
    if _FURNITURE.fullmatch(text):
        return "pdf_text_page_furniture"
    if size >= _TITLE_MIN_FONT_SIZE_PT:
        return "pdf_text_title_or_subtitle"
    # Staff furniture can be rotated beside a clef. Its text direction is a
    # source role signal, independent of the horizontal annotation band.
    if direction != (1.0, 0.0):
        return "pdf_text_rotated_text"
    if not above_system:
        return "pdf_text_outside_annotation_band"
    if size < _LABEL_MIN_FONT_SIZE_PT or size > _LABEL_MAX_FONT_SIZE_PT:
        return "pdf_text_font_size_unsupported"
    return "pdf_text_label"


def _nearby_systems(x0: float, y1: float, page_systems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    near = []
    for system in page_systems:
        top = float(system["staff"]["top"])
        spacing = float(system["staff_space"])
        gap = top - y1
        if (0 <= gap <= _ANNOTATION_BAND_STAFF_SPACES * spacing
                and x0 >= float(system["staff"]["x0"]) - _STAFF_LEFT_ALLOWANCE_PT
                and x0 <= float(system["staff"]["x1"])):
            near.append(system)
    return near


def _locate_bar(x0: float, near: list[dict[str, Any]]) -> tuple[int | None, str]:
    """Refuse system overlap and anchors within the bar boundary inset."""
    if len(near) != 1:
        return None, "pdf_text_system_ambiguous"
    system = near[0]
    matching = [int(system["first_bar_index"]) + local
                for local, (left, right) in enumerate(system["bars"])
                if float(left) + _BAR_BOUNDARY_INSET_PT < x0 < float(right) - _BAR_BOUNDARY_INSET_PT]
    if len(matching) != 1:
        return None, "pdf_text_bar_ambiguous"
    return matching[0], "pdf_text_label"


def _choose_beat(x0: float, target_bar: Bar | None,
                 source_events: list[dict[str, Any]]) -> tuple[int | None, str]:
    """Choose the nearest source beat only when its target is available."""
    if target_bar is None or not target_bar.events or len(target_bar.events) != len(source_events):
        return None, "pdf_text_beat_unavailable"
    ranked = sorted((abs((float(event["location"]["bbox"][0]) +
                         float(event["location"]["bbox"][2])) / 2 - x0), index)
                    for index, event in enumerate(source_events))
    if not ranked or (len(ranked) > 1 and ranked[1][0] - ranked[0][0] < _BEAT_DISTANCE_MARGIN_PT):
        return None, "pdf_text_beat_ambiguous"
    beat_index = ranked[0][1]
    if target_bar.events[beat_index].text:
        return None, "pdf_text_beat_occupied"
    return beat_index, "pdf_text_label"


def _attach_line_label(line: dict[str, Any], location: dict[str, Any],
                       page_systems: list[dict[str, Any]], bars: dict[int, Bar],
                       events_by_bar: dict[int, list[dict[str, Any]]]) -> dict[str, Any] | None:
    spans = line.get("spans", [])
    value = "".join(span["text"] for span in spans).strip()
    if not value:
        return None
    x0, y0, x1, y1 = (float(part) for part in line["bbox"])
    location["bbox"] = [x0, y0, x1, y1]
    near = _nearby_systems(x0, y1, page_systems)
    reason = _classify(value, spans[0].get("font", "") if spans else "",
                       max((float(span["size"]) for span in spans), default=0), bool(near),
                       direction=tuple(line["dir"]))
    if reason == "pdf_text_label":
        source_bar, reason = _locate_bar(x0, near)
        if source_bar is not None:
            target_bar = bars.get(source_bar + 1)
            beat_index, reason = _choose_beat(x0, target_bar, events_by_bar[source_bar])
            if beat_index is not None:
                beat = target_bar.events[beat_index]
                beat.text = value
                page_index = location["page_index"]
                block_index = location["block_index"]
                line_index = location["line_index"]
                beat.provenance.append(Provenance(
                    source_stage=SourceStage.PDF_TEXT,
                    page=page_index + 1,
                    system_id=f"system-{near[0]['system_index'] + 1}",
                    bar_index=source_bar + 1,
                    raw_token_id=f"pdf-p{page_index + 1}-b{block_index}-l{line_index}",
                    raw={"bbox": location["bbox"], "block_index": block_index,
                         "line_index": line_index},
                ))
                location.update({"bar_index": source_bar + 1, "beat_index": beat_index + 1})
    location["code"] = reason
    if reason == "pdf_text_label":
        location["text"] = value
    return location


def attach_pdf_text_labels(pdf: Path, note_durations: dict[str, Any], score: ScoreIR) -> dict[str, Any]:
    """Attach a source line to its unique bar and nearest source beat.

    The line's left edge is its musical anchor. Bar-boundary anchors and
    nearest-beat ties inside the named margins are refused. Rests participate
    as beats. A source bar that the compiler refused cannot receive a label.
    """
    systems = note_durations.get("systems", [])
    events_by_bar: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in note_durations.get("events", []):
        if event.get("status") == "read":
            events_by_bar[int(event["bar_index"])].append(event)
    bars = {bar.index: bar for bar in score.bars}
    counts: Counter[str] = Counter()
    decisions: list[dict[str, Any]] = []
    with pymupdf.open(pdf) as document:
        for page_index, page in enumerate(document):
            page_systems = [system for system in systems if system["page_index"] == page_index]
            for block_index, block in enumerate(page.get_text("dict")["blocks"]):
                for line_index, line in enumerate(block.get("lines", [])):
                    location = _attach_line_label(
                        line, {"page_index": page_index, "block_index": block_index,
                               "line_index": line_index}, page_systems, bars, events_by_bar,
                    )
                    if location is None:
                        continue
                    reason = location["code"]
                    counts[reason] += 1
                    decisions.append(location)
                    if reason in {"pdf_text_system_ambiguous", "pdf_text_bar_ambiguous",
                                  "pdf_text_beat_unavailable", "pdf_text_beat_ambiguous",
                                  "pdf_text_beat_occupied"}:
                        score.warnings.append(WarningItem(
                            code=reason, message=f"Printed text cannot be attached at page {page_index + 1}, block {block_index}, line {line_index}.",
                            provenance=[Provenance(source_stage=SourceStage.PDF_TEXT, page=page_index + 1,
                                                   raw={"bbox": location["bbox"], "block_index": block_index,
                                                        "line_index": line_index})],
                        ))
    return {"counts_by_reason": dict(sorted(counts.items())), "decisions": decisions}
