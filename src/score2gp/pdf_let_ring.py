"""Read centred let-ring text and its optional dashed, terminated extension.

The source notehead columns determine targets. Text width is never interpreted
as a musical span, and a refused source bar never receives a technique.
"""
from collections import Counter, defaultdict
from pathlib import Path
import re
from typing import Any

import pymupdf

from .ir import LetRingTechnique, Provenance, ScoreIR, SourceStage, WarningItem


def _dashed(drawing: dict[str, Any]) -> bool:
    pattern = str(drawing.get("dashes", ""))
    values = re.search(r"\[([^]]*)\]", pattern)
    return bool(values and any(float(v) > 0 for v in values[1].split()))


def _extension(page, box, spacing):
    """Require one horizontal dashed stroke and a vertical end cap.

    None means a single centred label. A nearby but incomplete extension is
    explicitly refused, rather than silently reduced to one note.
    """
    strokes = [d for d in page.get_drawings() if _dashed(d)]
    horizontal = [d for d in strokes
                  if abs(d["rect"].height) < 0.1 * spacing
                  and d["rect"].width >= spacing
                  and 0 <= d["rect"].x0 - box[2] <= spacing
                  and box[1] <= d["rect"].y0 <= box[3]]
    if not horizontal:
        return None, None
    if len(horizontal) != 1:
        return None, "pdf_let_ring_extension_ambiguous"
    line = horizontal[0]["rect"]
    caps = [d["rect"] for d in strokes
            if abs(d["rect"].width) < 0.1 * spacing
            and abs(d["rect"].x0 - line.x1) < 0.1 * spacing
            and d["rect"].y0 <= line.y0 <= d["rect"].y1]
    if not caps or min(c.y0 for c in caps) >= line.y0 or max(c.y1 for c in caps) <= line.y0:
        return None, "pdf_let_ring_endpoint_unreadable"
    return float(line.x1), None


def attach_pdf_let_ring(pdf: Path, note_durations: dict[str, Any], score: ScoreIR | None) -> dict[str, Any]:
    # This reader owns let ring on the PDF-only route. The older generic text
    # attachment may have treated a text bbox as a span; retain no such guess
    # when this page reader cannot bind the mark.
    if score is not None:
        for bar in score.bars:
            for event in bar.events:
                for note in event.notes:
                    note.techniques = [t for t in note.techniques if t.kind != "let-ring"]
    source_events = defaultdict(list)
    for event in note_durations.get("events", []):
        source_events[int(event["bar_index"])].append(event)
    bars = {b.index: b for b in score.bars} if score is not None else {}
    decisions = []
    warnings = []
    counts = Counter()
    with pymupdf.open(pdf) as document:
        for page_index, page in enumerate(document):
            for block_index, block in enumerate(page.get_text("dict")["blocks"]):
                for line_index, line in enumerate(block.get("lines", [])):
                    text = " ".join("".join(s["text"] for s in line["spans"]).split()).lower()
                    throughout = text == "let ring throughout"
                    if text not in {"let ring", "l.r.", "l.r"} and not throughout:
                        continue
                    box = list(line["bbox"])
                    anchor = (box[0] + box[2]) / 2
                    location = {"page_index": page_index, "bbox": box}
                    nearby = [s for s in note_durations.get("systems", [])
                              if s["page_index"] == page_index
                              and float(s["staff"]["x0"]) <= anchor <= float(s["staff"]["x1"])
                              and 0 <= box[1] - float(s["staff"]["bottom"]) <= 10 * float(s["staff_space"])]
                    reason = "pdf_let_ring_system_ambiguous"
                    if throughout:
                        # The reference writes this as a track-wide property
                        # (LetRingThroughout), not as per-note techniques; ScoreIR has
                        # no track-level field, so the mark is located and refused.
                        nearby = []
                        reason = "pdf_let_ring_throughout_track_scope_unsupported"
                    provenance = Provenance(source_stage=SourceStage.PDF_TEXT, page=page_index + 1,
                                            raw_token_id=f"pdf-p{page_index + 1}-b{block_index}-l{line_index}",
                                            raw={"bbox": box})
                    if len(nearby) == 1:
                        system = nearby[0]
                        spacing = float(system["staff_space"])
                        provenance.system_id = f"system-{system['system_index'] + 1}"
                        matching = [(int(system["first_bar_index"]) + i, float(left), float(right))
                                    for i, (left, right) in enumerate(system["bars"])
                                    if float(left) + 1 < anchor < float(right) - 1]
                        reason = "pdf_let_ring_bar_ambiguous"
                        if len(matching) == 1:
                            source_bar, left, right = matching[0]
                            provenance.bar_index = source_bar + 1
                            location["bar_index"] = source_bar + 1
                            events = source_events[source_bar]
                            centres = [(float(e["location"]["bbox"][0]) + float(e["location"]["bbox"][2])) / 2
                                       for e in events]
                            starts = [i for i, x in enumerate(centres) if abs(x - anchor) <= spacing]
                            end, extension_reason = _extension(page, box, spacing)
                            location["span"] = "dashed" if end is not None else "single"
                            reason = extension_reason or "pdf_let_ring_start_ambiguous"
                            if extension_reason is None and len(starts) == 1:
                                start = starts[0]
                                indices = [start]
                                reason = "pdf_let_ring_endpoint_ambiguous"
                                if end is None or left < end < right:
                                    if end is not None:
                                        indices = [i for i in range(start, len(events)) if centres[i] <= end]
                                    location["beat_indices"] = [i + 1 for i in indices]
                                    # A terminated line must end at the last source column, not in
                                    # an unmeasured gap or beyond a bar boundary.
                                    if end is None or (indices and abs(end - float(events[indices[-1]]["location"]["bbox"][2])) <= spacing):
                                        target = bars.get(source_bar + 1)
                                        reason = "pdf_let_ring_bar_unavailable"
                                        if (target is not None and target.events
                                                and len(target.events) == len(events)
                                                and all(events[i]["status"] == "read" and target.events[i].notes
                                                        for i in indices)):
                                            for i in indices:
                                                for note in target.events[i].notes:
                                                    if not any(t.kind == "let-ring" for t in note.techniques):
                                                        note.techniques.append(LetRingTechnique())
                                                        note.provenance.append(provenance)
                                            reason = "pdf_let_ring_attached"
                    location["code"] = reason
                    counts[reason] += 1
                    decisions.append(location)
                    if reason != "pdf_let_ring_attached":
                        warnings.append(WarningItem(code=reason,
                            message=f"Let ring not written: {reason}.", provenance=[provenance]))
    if score is not None:
        score.warnings.extend(warnings)
    return {"counts_by_reason": dict(sorted(counts.items())), "decisions": decisions,
            "warnings": [w.model_dump(mode="json", exclude_none=True) for w in warnings]}
