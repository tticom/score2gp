"""Read printed beat annotations from PDF text spans, without reference GP data."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re
from typing import Any

import pymupdf

from .ir import Provenance, ScoreIR, SourceStage, WarningItem


_TECHNIQUE = re.compile(r"(?i)^(?:h|p|sl\.?|s|b|r|tr|pm|let ring|vib\.?|t|tap)$")
_CHORD = re.compile(r"(?i)^[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add|ø)?\d*(?:alt)?(?:[/()][A-G#b0-9mø]+\)?)?$")
_TEMPO = re.compile(r"(?i)^(?:(?:[♩♪♫\s.]*|[A-GQqEe])=\s*\d+|(?:largo|andante|moderato|allegro|presto)\b.*)$")
_FURNITURE = re.compile(r"(?i)^(?:standard tuning|tuning\s*:.*|(?:music|words|lyrics|transcribed|arranged) by\b.*|copyright\b.*|©.*|all rights reserved.*)$")


def _classify(text: str, font: str, size: float, above_system: bool) -> str:
    if _TEMPO.fullmatch(text):
        return "pdf_text_tempo"
    if not text or not any(ch.isalpha() for ch in text):
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
    if size >= 16:
        return "pdf_text_title_or_subtitle"
    if not above_system:
        return "pdf_text_outside_annotation_band"
    if size < 7 or size > 15:
        return "pdf_text_font_size_unsupported"
    return "pdf_text_label"


def attach_pdf_text_labels(pdf: Path, note_durations: dict[str, Any], score: ScoreIR) -> dict[str, Any]:
    """Attach a source line to its unique bar and nearest source beat.

    The line's left edge is its musical anchor. A boundary or nearest-beat tie
    within two PDF points is refused. Rests participate as beats. A source bar
    that the compiler refused cannot receive a label.
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
                    spans = line.get("spans", [])
                    value = "".join(span["text"] for span in spans).strip()
                    if not value:
                        continue
                    x0, y0, x1, y1 = (float(part) for part in line["bbox"])
                    near = []
                    for system in page_systems:
                        top = float(system["staff"]["top"])
                        spacing = float(system["staff_space"])
                        gap = top - y1
                        if 0 <= gap <= 5 * spacing and x0 >= float(system["staff"]["x0"]) - 5 and x0 <= float(system["staff"]["x1"]):
                            near.append(system)
                    reason = _classify(value, spans[0].get("font", "") if spans else "",
                                       max((float(span["size"]) for span in spans), default=0), bool(near))
                    location = {"page_index": page_index, "block_index": block_index,
                                "line_index": line_index, "bbox": [x0, y0, x1, y1]}
                    if reason == "pdf_text_label":
                        if len(near) != 1:
                            reason = "pdf_text_system_ambiguous"
                        else:
                            system = near[0]
                            matching = [int(system["first_bar_index"]) + local for local, (left, right) in enumerate(system["bars"])
                                        if float(left) + 1 < x0 < float(right) - 1]
                            if len(matching) != 1:
                                reason = "pdf_text_bar_ambiguous"
                            else:
                                source_bar = matching[0]
                                target_bar = bars.get(source_bar + 1)
                                source_events = events_by_bar[source_bar]
                                if target_bar is None or not target_bar.events or len(target_bar.events) != len(source_events):
                                    reason = "pdf_text_beat_unavailable"
                                else:
                                    ranked = sorted((abs((float(event["location"]["bbox"][0]) +
                                                         float(event["location"]["bbox"][2])) / 2 - x0), index)
                                                    for index, event in enumerate(source_events))
                                    if not ranked or (len(ranked) > 1 and ranked[1][0] - ranked[0][0] < 2):
                                        reason = "pdf_text_beat_ambiguous"
                                    else:
                                        beat_index = ranked[0][1]
                                        beat = target_bar.events[beat_index]
                                        if beat.text:
                                            reason = "pdf_text_beat_occupied"
                                        else:
                                            beat.text = value
                                            beat.provenance.append(Provenance(
                                                source_stage=SourceStage.PDF_TEXT,
                                                page=page_index + 1,
                                                system_id=f"system-{system['system_index'] + 1}",
                                                bar_index=source_bar + 1,
                                                raw_token_id=f"pdf-p{page_index + 1}-b{block_index}-l{line_index}",
                                                raw={"bbox": location["bbox"], "block_index": block_index,
                                                     "line_index": line_index},
                                            ))
                                            location.update({"bar_index": source_bar + 1,
                                                             "beat_index": beat_index + 1})
                    counts[reason] += 1
                    location["code"] = reason
                    if reason == "pdf_text_label":
                        location["text"] = value
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
