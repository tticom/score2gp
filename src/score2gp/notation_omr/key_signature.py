"""Read key signatures in a notation staff header from painted PDF contours.

The clef and accidentals are vector contours in the real source. Text glyphs are
also accepted for public generated PDFs. A missing or partial header is refused.
"""

from __future__ import annotations

import re
from itertools import groupby
from typing import Any

from .note_duration import Glyph, PageSymbols, Staff, _column_counts, _is_notehead, _row_counts


SHARP_TOPS = (-1.4, 0.1, -1.9, -0.4, 1.1, -0.9, 0.6)
FLAT_TOPS = (0.2, -1.3, 0.7, -0.8, 1.2, -0.3, 1.7)
KEY_NAME = re.compile(r"^([A-G])([#b]?)\s+(Major|Minor)$", re.IGNORECASE)
MAJOR_FIFTHS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5,
                "F#": 6, "C#": 7, "F": -1, "Bb": -2, "Eb": -3,
                "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
MINOR_FIFTHS = {"A": 0, "E": 1, "B": 2, "F#": 3, "C#": 4, "G#": 5,
                "D#": 6, "A#": 7, "D": -1, "G": -2, "C": -3,
                "F": -4, "Bb": -5, "Eb": -6, "Ab": -7}


def _kind(glyph: Glyph, space: float) -> str | None:
    """Classify the painted accidental outline, not an accidental near a note."""
    w, h = glyph.w / space, glyph.h / space
    if not glyph.filled or not (0.65 <= w <= 1.35 and 2.1 <= h <= 3.2):
        return None
    rows = _row_counts(glyph)
    double_rows = sum(n >= 2 for n in rows)
    double_bands = [sum(1 for _ in run) for doubled, run in groupby(n >= 2 for n in rows) if doubled]
    if h >= 2.6 and double_rows >= 8 and sum(length >= 2 for length in double_bands) >= 2:
        return "sharp"
    # A flat's upper stem and lower bowl give several vertical paint runs on
    # its left edge. A natural has two upright strokes but no bowl there.
    left_runs, right_runs = _column_counts(glyph, (0.2, 0.8))
    if double_rows <= 7 and left_runs >= 2 and right_runs <= 1:
        return "flat"
    return None


def read_system_key_signature(staff: Staff, symbols: PageSymbols) -> dict[str, Any]:
    """Read the clef-adjacent signature, returning source IDs or a located refusal."""
    space = staff.space
    location = {"page_index": staff.page_index, "staff_top": round(staff.top, 3),
                "staff_x0": round(staff.x0, 3)}
    clefs = [g for g in symbols.glyphs if g.bbox[0] <= staff.x0 + 1.5 * space
             and g.bbox[2] <= staff.x0 + 4 * space
             and g.h >= 5 * space and abs(g.cy - (staff.top + 2 * space)) <= 2 * space]
    if len(clefs) != 1:
        return {"status": "refused", "fifths": None, "mode": None, "sources": [],
                "reason": "key_clef_unread", "location": location}
    clef = clefs[0]
    heads = [g for g in symbols.glyphs if _is_notehead(g, space)
             and staff.top - 2 * space <= g.cy <= staff.bottom + 2 * space
             and g.bbox[0] > clef.bbox[2]]
    first_note_x = min((g.bbox[0] for g in heads), default=staff.x1)
    # A signature is directly after the clef and before the first note. The cap
    # also excludes later accidentals when a staff has no recognised notehead.
    right = min(first_note_x, clef.bbox[2] + 8 * space)
    candidates: list[tuple[float, float, str | None, str, float]] = []
    for g in symbols.glyphs:
        if not (clef.bbox[2] + 0.25 * space <= g.bbox[0] < right
                and staff.top - 3 * space <= g.cy <= staff.bottom + space):
            continue
        # Stacked time-signature numbers are wider and shorter than accidentals.
        if 1.4 <= g.w / space <= 2.2 and 1.6 <= g.h / space <= 2.3:
            continue
        candidates.append((g.bbox[0], g.bbox[1], _kind(g, space), g.ident, g.bbox[2]))
    for t in symbols.texts:
        if not (clef.bbox[2] + 0.25 * space <= t.bbox[0] < right
                and staff.top - 3 * space <= t.cy <= staff.bottom + space):
            continue
        if t.text in ("#", "♯"):
            kind = "sharp"
        elif t.text in ("b", "♭"):
            kind = "flat"
        elif t.text.isdigit():
            continue  # printed time signature or bar number
        else:
            kind = None
        candidates.append((t.bbox[0], t.bbox[1], kind, t.ident, t.bbox[2]))
    candidates.sort()
    # Only the contiguous run after the clef belongs to the signature. A
    # later note, beam, label or accidental belongs to the bar, even if it
    # happens to lie before the first successfully recognised notehead.
    adjacent: list[tuple[float, float, str | None, str, float]] = []
    edge = clef.bbox[2]
    for candidate in candidates:
        if candidate[0] - edge > 1.5 * space:
            break
        adjacent.append(candidate)
        edge = candidate[0] + space
    candidates = adjacent
    # An accidental printed immediately against the first note is an event
    # accidental, including a chord with several accidentals at different
    # heights. It is not a key signature merely because it follows the clef.
    candidates = [c for c in candidates if first_note_x - c[4] > 1.5 * space]
    reasons = None
    kinds = {c[2] for c in candidates}
    if None in kinds or len(kinds) > 1 or len(candidates) > 7:
        reasons = "key_signature_partial_or_ambiguous"
    elif candidates:
        kind = candidates[0][2]
        expected = SHARP_TOPS if kind == "sharp" else FLAT_TOPS
        # Font bboxes and contours have different ascenders. Their successive
        # staff positions must nevertheless follow the conventional order.
        observed = [(c[1] - staff.top) / space for c in candidates]
        if abs(observed[0] - expected[0]) > 0.85 or any(
            abs((observed[i] - observed[0]) - (expected[i] - expected[0])) > 0.45
            for i in range(1, len(observed))
        ):
            reasons = "key_signature_partial_or_ambiguous"
        if any((candidates[i][0] - candidates[i - 1][0]) / space > 1.8
               for i in range(1, len(candidates))):
            reasons = "key_signature_partial_or_ambiguous"
    if reasons:
        return {"status": "refused", "fifths": None, "mode": None,
                "sources": [c[3] for c in candidates], "reason": reasons,
                "location": location}
    fifths = len(candidates) * (1 if candidates and candidates[0][2] == "sharp" else -1)
    # No accidental after a read clef is an explicit C/A signature at this
    # system start. It still does not identify mode.
    if not candidates:
        fifths = 0
    mode = None
    mode_sources: list[str] = []
    for t in symbols.texts:
        if not (staff.top - 5 * space <= t.cy <= staff.top - space
                and staff.x0 <= t.cx <= right):
            continue
        match = KEY_NAME.fullmatch(t.text.strip())
        if match:
            name = match.group(1).upper() + match.group(2).replace("B", "b")
            candidate_mode = match.group(3).lower()
            expected_count = (MAJOR_FIFTHS if candidate_mode == "major" else MINOR_FIFTHS).get(name)
            if expected_count != fifths or mode is not None:
                return {"status": "refused", "fifths": None, "mode": None,
                        "sources": [c[3] for c in candidates] + [t.ident],
                        "reason": "key_name_signature_conflict", "location": location}
            mode = candidate_mode
            mode_sources.append(t.ident)
    return {"status": "read", "fifths": fifths, "mode": mode,
            "sources": [c[3] for c in candidates], "clef_source": clef.ident,
            "mode_sources": mode_sources, "mode_diagnostic": None if mode else "key_mode_unresolved",
            "reason": None, "location": location}


def read_bar_key_signatures(staff: Staff, symbols: PageSymbols,
                            bars: list[tuple[float, float]],
                            header: dict[str, Any]) -> list[dict[str, Any]]:
    """Carry a read key by bar, inspecting each barline for a new signature."""
    if not bars:
        return []
    space = staff.space
    current = header
    result = [current]
    for bar_index, (left, right) in enumerate(bars[1:], start=1):
        candidates: list[tuple[float, float, str | None, str, float]] = []
        for glyph in symbols.glyphs:
            if not (left + 0.25 * space <= glyph.bbox[0] < right
                    and staff.top - 3 * space <= glyph.cy <= staff.bottom + space):
                continue
            if glyph.filled and 0.6 <= glyph.w / space <= 1.4 and 2.0 <= glyph.h / space <= 3.3:
                candidates.append((glyph.bbox[0], glyph.bbox[1], _kind(glyph, space),
                                   glyph.ident, glyph.bbox[2]))
        for label in symbols.texts:
            if not (left + 0.25 * space <= label.bbox[0] < right
                    and staff.top - 3 * space <= label.cy <= staff.bottom + space):
                continue
            if label.text in ("#", "♯", "b", "♭", "♮"):
                kind = "sharp" if label.text in ("#", "♯") else "flat" if label.text in ("b", "♭") else None
                candidates.append((label.bbox[0], label.bbox[1], kind,
                                   label.ident, label.bbox[2]))
        candidates.sort()
        # A signature begins just after the barline and continues at roughly
        # one staff-space intervals. Stop at a later isolated event accidental.
        adjacent = []
        edge = left
        for candidate in candidates:
            if candidate[0] - edge > 1.5 * space:
                break
            adjacent.append(candidate)
            edge = candidate[0] + space
        candidates = adjacent
        if not candidates:
            result.append(current)
            continue
        next_note = min((g.bbox[0] for g in symbols.glyphs
                         if _is_notehead(g, space) and g.bbox[0] > candidates[-1][4]
                         and staff.top - 4 * space <= g.cy <= staff.bottom + 4 * space),
                        default=staff.x1)
        if next_note - candidates[-1][4] <= 1.5 * space:
            result.append(current)  # an accidental attached to the first note
            continue
        kind_set = {c[2] for c in candidates}
        expected = SHARP_TOPS if kind_set == {"sharp"} else FLAT_TOPS if kind_set == {"flat"} else ()
        observed = [(c[1] - staff.top) / space for c in candidates]
        valid = bool(expected) and len(candidates) <= 7 and abs(observed[0] - expected[0]) <= 0.85
        valid = valid and all(abs((observed[i] - observed[0]) - (expected[i] - expected[0])) <= 0.45
                              for i in range(1, len(observed)))
        valid = valid and all((candidates[i][0] - candidates[i - 1][0]) / space <= 1.8
                              for i in range(1, len(candidates)))
        location = {"page_index": staff.page_index, "staff_top": round(staff.top, 3),
                    "staff_x0": round(staff.x0, 3), "bar_index": bar_index,
                    "bar_x0": round(left, 3)}
        if valid:
            current = {"status": "read", "fifths": len(candidates) * (1 if expected is SHARP_TOPS else -1),
                       "mode": None, "sources": [c[3] for c in candidates],
                       "mode_sources": [], "mode_diagnostic": "key_mode_unresolved",
                       "reason": None, "location": location}
        else:
            current = {"status": "refused", "fifths": None, "mode": None,
                       "sources": [c[3] for c in candidates],
                       "reason": "key_signature_partial_or_ambiguous", "location": location}
        result.append(current)
    return result
