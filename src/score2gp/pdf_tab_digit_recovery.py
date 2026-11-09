"""Read excluded digits only with a notation bar and six directly painted TAB rows.

This is additional evidence at a refused bar, not a relaxation of the legacy
system detector. Existing written bars, layout refusals and timing gates remain
outside this reader. It never supplies a position from a notation pitch.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Sequence

from .tabraw import TabCandidate, parse_fret_text
from .ir import BoundingBox

_ROW_ROUNDING_PT = 0.001  # Detected row coordinates are serialized to three decimal places.


def _chord_targets(candidates, words, reading, bar, notation, left, right, offset):
    """A caption above this bar must name a unique printed beat."""
    space = notation["staff_space"]
    word_lookup = {tuple(w[5:8]): w for w in words}
    records = [e for e in reading["events"] if e["bar_index"] == bar and e["kind"] != "rest" and not e.get("grace")]
    result = []
    names = {}
    for label in candidates:
        if (label.kind != "chord-symbol" or label.page_index != notation["page_index"] + 1
                or label.x is None or label.y is None or label.bbox is None
                or not left < label.x < right
                or not 0 < notation["staff"]["top"] - (label.y - offset) <= 5 * space
                or label.bbox.y1 - offset > notation["staff"]["top"]):
            continue
        word = word_lookup.get((label.raw.get("pdf_block_number"), label.raw.get("pdf_line_number"),
                                label.raw.get("pdf_word_number")))
        if word is None or word[4] != label.raw_text:
            return None
        ranked = sorted((abs((e["location"]["bbox"][0] + e["location"]["bbox"][2]) / 2 - label.x),
                         e["event_index"]) for e in records)
        if (not ranked or ranked[0][0] > max(space, (label.bbox.x1 - label.bbox.x0) / 2)
                or len(ranked) > 1 and ranked[1][0] - ranked[0][0] < 0.5 * space):
            return None
        event = ranked[0][1]
        if event in names and names[event] != label.raw_text:
            return None
        names[event] = label.raw_text
        result.append({"id": label.id, "event_index": event})
    return result


def apply_recovered_chord_labels(score, candidates, recovered):
    """Place witnessed captions on newly read bars, preserving every existing bar."""
    by_id = {c.id: c for c in candidates}
    bars = {bar.index: bar for bar in score.bars}
    targets = {(c.bar_index, t["event_index"], t["id"])
               for c in recovered for t in c.raw.get("recovered_chord_labels", [])}
    for bar_index, event_index, ident in sorted(targets):
        bar = bars.get(bar_index)
        if bar is None or event_index >= len(bar.events):
            continue  # A later located refusal withheld this bar.
        label = by_id[ident]
        event = bar.events[event_index]
        event.chord_symbol = label.raw_text
        if not any(p.raw_token_id == ident for p in event.provenance):
            provenance = label.to_provenance()
            provenance.bar_index = bar_index
            provenance.raw = {"derived_from": "notation_bar_chord_label"}
            event.provenance.append(provenance)


def _missing_numeric_words(words, known, page, offset):
    result = []
    for wi, word in enumerate(words):
        text = word[4]
        if (tuple(word[5:8]) in known or not re.fullmatch(r"[0-9]+", text)
                or (len(text) > 1 and text.startswith("0")) or parse_fret_text(text) is None):
            continue
        result.append(TabCandidate(
            id=f"pdf-p{page + 1:03d}-observed-word-{wi}", kind="candidate-text", page_index=page + 1,
            raw_text=text, x=(word[0] + word[2]) / 2, y=(word[1] + word[3]) / 2 + offset,
            bbox=BoundingBox(page=page + 1, x0=word[0], x1=word[2], y0=word[1] + offset, y1=word[3] + offset),
            raw={"pdf_word_index": wi, "pdf_block_number": word[5],
                 "pdf_line_number": word[6], "pdf_word_number": word[7]}))
    return result


def _unread_number_word(words, owner, left, right, space, census):
    from .pdf import _split_adjacent_fret_run
    for word in words:
        text = word[4]
        if (not left < (word[0] + word[2]) / 2 < right or not re.fullmatch(r"[0-9()]+", text)
                or not any(c.isdigit() for c in text)):
            continue
        y = (word[1] + word[3]) / 2
        if min(abs(y - row) for row in owner.line_ys) > 0.5 * space:
            continue
        if (not re.fullmatch(r"[0-9]+", text) or parse_fret_text(text) is None
                or (len(text) > 1 and text.startswith("0"))):
            return "tab_digit_run_or_parenthesis_unread"
        if sum(abs(y - row) <= 0.2 * space for row in owner.line_ys) != 1:
            return "tab_digit_string_owner_unread"
        record = dict(text=text, x0=word[0], x1=word[2], y0=word[1], y1=word[3])
        if _split_adjacent_fret_run(record, census, owner):
            return "tab_digit_run_or_parenthesis_unread"
    return None


def unread_new_chord_arrows(source_pdf, reading, bars, route, candidates, recovered_ids):
    """Withhold newly decoded chords with an unrepresented straight stroke arrow.

    A visible vertical shaft spans the printed chord; a filled tip contacts one
    end. No stroke direction, spread duration or playback value is guessed.
    """
    eligible = {b["source_bar_index"] for b in route["bars"] if b["status"] == "written" and any(
        m["match"].get("endpoint_rank_basis") or recovered_ids.intersection(m["match"].get("candidate_ids", []))
        for m in b["events"])}
    if not eligible:
        return {}
    verified = False
    if source_pdf and Path(source_pdf).is_file():
        with Path(source_pdf).open("rb") as stream:
            verified = hashlib.file_digest(stream, "sha256").hexdigest() == reading["source"].get("pdf_sha256")
    if not verified:
        return {bar: {"reason": "new_bar_mark_scan_unavailable", "event_index": 0,
                      "source": "printed_tab_stroke", "cause": "source_unavailable_for_new_bar_mark_scan"}
                for bar in eligible}
    import pymupdf
    from .pdf import _paints_ink

    by_id = {c.id: c for c in candidates}
    systems = {s["first_bar_index"] + i: s for s in reading["systems"] for i in range(s["bar_count"])}
    result = {}
    current_page = None
    with pymupdf.open(source_pdf) as document:
        for ir_bar, entry in zip(bars, route["bars"]):
            if entry["source_bar_index"] not in eligible:
                continue
            system = systems[entry["source_bar_index"]]
            page = system["page_index"]
            if page != current_page:
                current_page = page
                drawings = document[page].get_drawings()
                shafts = [(i, item[1], item[2]) for i, d in enumerate(drawings)
                          if d.get("type") in ("s", "fs") and _paints_ink(d.get("color"), d.get("stroke_opacity"))
                          for item in d["items"] if item[0] == "l" and abs(item[1].x - item[2].x) <= 0.1]
                tips = [(i, d["rect"]) for i, d in enumerate(drawings)
                        if d.get("type") in ("f", "fs") and _paints_ink(d.get("fill"), d.get("fill_opacity"))]
            offset = sum(reading["source"]["page_heights"][:page])
            space = system["staff_space"]
            for ei, event in enumerate(ir_bar.events):
                digits = [by_id[p.raw_token_id] for n in event.notes for p in n.provenance
                          if p.raw_token_id in by_id and by_id[p.raw_token_id].kind == "fret"]
                if len({c.string for c in digits}) < 2:
                    continue
                x = min(c.x for c in digits)
                low, high = min(c.y - offset for c in digits), max(c.y - offset for c in digits)
                for si, a, b in shafts:
                    y0, y1 = sorted((a.y, b.y))
                    if not (0 < x - a.x <= 2 * space and y0 <= low and high <= y1):
                        continue
                    matches = [(ti, r) for ti, r in tips
                               if 0.3 * space <= r.width <= space and 0.5 * space <= r.height <= 1.5 * space
                               and r.x0 < a.x < r.x1
                               and (abs(r.y0 - y0) <= 0.1 * space or abs(r.y1 - y1) <= 0.1 * space)]
                    if matches:
                        result[entry["source_bar_index"]] = {
                            "event_index": ei, "source": "printed_tab_stroke",
                            "cause": "straight_chord_arrow_unread", "stroke_indices": [si, *(ti for ti, _ in matches)],
                            "bbox": [a.x, y0, a.x, y1]}
                        break
                if entry["source_bar_index"] in result:
                    break
    return result


def _palm_spans(candidates, drawings, page_index, notation, owner, offset):
    """A printed P.M. label and its unique dashed stroke in this staff's band."""
    space = notation["staff_space"]
    labels = [c for c in candidates if c.kind == "technique-text" and c.page_index == page_index + 1
              and c.raw_text.strip().lower() in ("p.m.", "p.m", "pm", "palm mute", "palm-mute")
              and c.bbox is not None and c.y is not None
              and notation["staff"]["top"] - 2 * space <= c.y - offset < owner.line_ys[0]]
    result = []
    for label in labels:
        strokes = [(a.x, b.x) for drawing in drawings
                   if drawing.get("type") in ("s", "fs")
                   and any(float(n) > 0 for n in re.findall(r"[0-9.]+", drawing.get("dashes") or ""))
                   for item in drawing["items"] if item[0] == "l"
                   for a, b in [(item[1], item[2])]
                   if abs(a.y - b.y) <= 0.1 and b.x > a.x
                   and abs(a.y - (label.y - offset)) <= 0.5 * space
                   and 0 <= a.x - label.bbox.x1 <= space]
        if len(strokes) != 1:
            return None
        result.append((label.id, label.bbox.x0, strokes[0][1]))
    return result


def _continuous_rows(segments, words, rows, left, right, space):
    """Every gap is covered by printed numeric text centred on this string."""
    numbers = [w for w in words if re.fullmatch(r"[0-9()]+", w[4])
               and any(c.isdigit() for c in w[4])]
    for y in rows:
        spans = sorted((min(s.x0, s.x1), max(s.x0, s.x1)) for s in segments
                       if abs(s.y1 - s.y0) <= 0.3
                       and abs((s.y0 + s.y1) / 2 - y) <= 0.5
                       and abs(s.x1 - s.x0) >= 1.0)
        boxes = [(w[0], w[2]) for w in numbers if abs((w[1] + w[3]) / 2 - y) <= 0.5 * space]
        cursor = left
        for a, b in spans:
            if b <= cursor:
                continue
            if a >= right:
                break
            if a > cursor + 1.0 and not any(x0 - 2.0 <= cursor and a <= x1 + 2.0 for x0, x1 in boxes):
                return False
            cursor = max(cursor, b)
        if cursor < right - 1.0:
            return False
    return True


def _unread_technique(candidates, page, notation, owner, left, right, offset):
    """A new bar cannot silently drop an annotation whose owner is still unread."""
    space = notation["staff_space"]
    palms = {"p.m.", "p.m", "pm", "palm mute", "palm-mute"}
    labels = {"h", "p", "sl", "sl.", "b", "r", "tr", "vib", "vib.", "t", "tap", "let ring"}
    return any(c.page_index == page + 1 and c.x is not None and c.y is not None
               and left - space <= c.x <= right + space
               and notation["staff"]["top"] - 2 * space <= c.y - offset < owner.line_ys[0]
               and c.raw_text.strip().lower() not in palms
               and (c.raw_text.strip().lower() in labels
                    or (c.kind == "technique-text" and parse_fret_text(c.raw_text) is None))
               for c in candidates)


def _unread_tab_ink(drawings, words, rows, left, right, space):
    """Account for rows, barlines and printed numbers; other TAB ink stays unread."""
    boxes = [w[:4] for w in words if re.fullmatch(r"[0-9()]+", w[4])]
    top, bottom = rows[0], rows[-1]

    def contained(points):
        return any(all(x0 - 0.1 * space <= p.x <= x1 + 0.1 * space
                       and y0 - 0.1 * space <= p.y <= y1 + 0.1 * space for p in points)
                   for x0, y0, x1, y1 in boxes)

    for drawing in drawings:
        for item in drawing["items"]:
            if item[0] == "re":
                r = item[1]
                if r.x1 < left or r.x0 > right or r.y1 <= top + _ROW_ROUNDING_PT or r.y0 >= bottom - _ROW_ROUNDING_PT:
                    continue
                if (r.height <= 0.3 * space and any(abs((r.y0 + r.y1) / 2 - y) <= 0.15 * space for y in rows)
                        or r.width <= 0.3 * space and min(abs(r.x0 - left), abs(r.x1 - right)) <= 0.2 * space):
                    continue
                points = [r.tl, r.br]
            elif item[0] in ("l", "c"):
                points = list(item[1:])
                if (max(p.x for p in points) < left or min(p.x for p in points) > right
                        or max(p.y for p in points) <= top + _ROW_ROUNDING_PT
                        or min(p.y for p in points) >= bottom - _ROW_ROUNDING_PT):
                    continue
                if item[0] == "l":
                    a, b = points
                    if (abs(a.y - b.y) <= 0.1 and any(abs(a.y - y) <= 0.15 * space for y in rows)
                            or abs(a.x - b.x) <= 0.1 and min(abs(a.x - left), abs(a.x - right)) <= 0.2 * space):
                        continue
            else:
                r = drawing["rect"]
                if r.x1 > left and r.x0 < right and r.y1 > top + _ROW_ROUNDING_PT and r.y0 < bottom - _ROW_ROUNDING_PT:
                    return True
                continue
            if not contained(points):
                return True
    return False


def recover_printed_bar_digits(source_pdf: str | None, reading: dict[str, Any], route: dict[str, Any],
                              candidates: Sequence[TabCandidate]
                              ) -> tuple[list[TabCandidate], dict[int, str]]:
    """Return newly owned literal digits and bars whose unprinted completion stays unread.

    Geometry is retained for one page only. The PDF must be the very input whose
    hash the duration reader recorded. A failed proof leaves the bar refused.
    """
    wanted = {b["source_bar_index"] for b in route["bars"]
              if b.get("reason") in ("notation_note_without_tab_digit", "notehead_digit_count_mismatch")}
    if not wanted or not source_pdf or not Path(source_pdf).is_file():
        return [], {}
    with Path(source_pdf).open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != reading["source"].get("pdf_sha256"):
            return [], {}

    import pymupdf
    from .pdf import (_detect_tab_systems, _drawing_segments, _paints_ink,
                      _page_digit_glyph_census, _split_adjacent_fret_run)

    by_page: dict[int, list[TabCandidate]] = {}
    for candidate in candidates:
        literal = candidate.raw_text.strip()
        if (candidate.kind not in ("candidate-text", "fret") or not re.fullmatch(r"[0-9]+", literal)
                or (len(literal) > 1 and literal.startswith("0"))
                or parse_fret_text(literal) is None or candidate.bbox is None
                or candidate.x is None or candidate.y is None or candidate.page_index is None):
            continue
        by_page.setdefault(candidate.page_index - 1, []).append(candidate)
    system_of = {s["first_bar_index"] + i: s for s in reading["systems"] for i in range(s["bar_count"])}
    checks = {c["bar_index"]: c for c in reading["bar_checks"]}
    recovered: list[TabCandidate] = []
    withheld: dict[int, str] = {}
    page_index = None
    with pymupdf.open(source_pdf) as document:
        for bar in sorted(wanted):
            notation = system_of[bar]
            p = notation["page_index"]
            if p != page_index:
                page_index = p
                page = document[p]
                systems = _detect_tab_systems(page, p + 1, _recover_paint=True)
                drawings = [d for d in page.get_drawings()
                            if _paints_ink(d.get("color"), d.get("stroke_opacity"))
                            or _paints_ink(d.get("fill"), d.get("fill_opacity"))]
                segments = list(_drawing_segments(drawings))
                words = page.get_text("words")
                census = _page_digit_glyph_census(page)
                offset = sum(reading["source"]["page_heights"][:p])
                word_lookup = {tuple(w[5:8]): (wi, w) for wi, w in enumerate(words)}
                observed = []
                for candidate in by_page.get(p, []):
                    key = (candidate.raw.get("pdf_block_number"), candidate.raw.get("pdf_line_number"),
                           candidate.raw.get("pdf_word_number"))
                    match = word_lookup.get(key)
                    if match is None or match[1][4] != candidate.raw_text.strip():
                        continue
                    wi, word = match
                    observed.append(candidate.model_copy(update={
                        "x": (word[0] + word[2]) / 2, "y": (word[1] + word[3]) / 2 + offset,
                        "bbox": BoundingBox(page=p + 1, x0=word[0], x1=word[2], y0=word[1] + offset, y1=word[3] + offset),
                        "raw": {**candidate.raw, "pdf_word_index": wi}}))
                by_page[p] = observed
                known = {(c.raw.get("pdf_block_number"), c.raw.get("pdf_line_number"), c.raw.get("pdf_word_number"))
                         for c in by_page.get(p, [])}
                by_page.setdefault(p, []).extend(_missing_numeric_words(words, known, p, offset))
            staff = notation["staff"]
            next_top = min((s["staff"]["top"] for s in reading["systems"]
                            if s["page_index"] == p and s["staff"]["top"] > staff["bottom"]),
                           default=page.rect.height)
            owners = [s for s in systems if len(s.line_ys) == 6 and not s.grouping_warnings
                      and (abs(s.line_ys[0] - staff["top"]) <= 0.1 * notation["staff_space"]
                           if staff["top"] == staff["bottom"]
                           else staff["bottom"] < s.line_ys[0] < s.line_ys[-1] < next_top)]
            if len(owners) != 1:
                continue
            owner = owners[0]
            space = (owner.line_ys[-1] - owner.line_ys[0]) / 5
            left, right = notation["bars"][bar - notation["first_bar_index"]]
            if not _continuous_rows(segments, words, owner.line_ys, left, right, space):
                continue
            offset = sum(reading["source"]["page_heights"][:p])
            unread_word = _unread_number_word(words, owner, left, right, space, census)
            if unread_word:
                withheld[bar] = unread_word
                continue
            if _unread_technique(candidates, p, notation, owner, left, right, offset):
                withheld[bar] = "printed_technique_owner_unread"
                continue
            if _unread_tab_ink(drawings, words, owner.line_ys, left, right, space):
                withheld[bar] = "printed_tab_mark_unread"
                continue
            chords = _chord_targets(candidates, words, reading, bar, notation, left, right, offset)
            if chords is None:
                withheld[bar] = "printed_chord_label_owner_unread"
                continue
            palms = _palm_spans(candidates, drawings, p, notation, owner, offset)
            if palms is None:
                withheld[bar] = "palm_mute_span_unread"
                continue
            found = []
            for candidate in by_page.get(p, []):
                if not left < candidate.x < right:
                    continue
                rows = [i for i, y in enumerate(owner.line_ys) if abs(candidate.y - offset - y) <= 0.2 * space]
                if len(rows) != 1:
                    continue
                bbox = candidate.bbox
                word = {"text": candidate.raw_text.strip(),
                        "x0": bbox.x0, "x1": bbox.x1, "y0": bbox.y0 - offset, "y1": bbox.y1 - offset}
                if _split_adjacent_fret_run(word, census, owner):
                    continue  # A multi-fret word is not one literal fret.
                found.append(candidate.model_copy(update={
                    "kind": "fret", "parsed_fret": parse_fret_text(word["text"]),
                    "string": rows[0] + 1, "line_index": rows[0] + 1,
                    "system_index": notation["system_index"] + 1, "staff_index": 1, "bar_index": bar + 1,
                    "raw": {**candidate.raw, "position_basis": "six_painted_tab_rows_at_notation_bar",
                            "recovered_chord_labels": chords,
                            "recovered_palm_mute_sources": [ident for ident, a, b in palms if a <= candidate.x <= b]}}))
            if found and checks[bar].get("implied_rest_quarters"):
                withheld[bar] = "printed_rhythm_completion_unread"
            else:
                recovered.extend(found)
    return recovered, withheld
