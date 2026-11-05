"""The PDF-only conversion route: durations from note types, positions from the TAB.

Every event's duration is its DUR-01 note-duration record (note type, dots, tuplet, tie); every
note's (string, fret) is the TAB digit column printed under it. Bars come from the notation staff.
Each TAB digit is placed in the notation bar above it by page, height and x, and matched to one
notation event by column; the match is recorded. A bar with an unread event, a notation/TAB
mismatch or a total that disagrees with its time signature is refused with a located reason code
and written empty: no duration is ever derived from a count, spacing, default or bar total, and no
rest is ever added to fill a bar.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Sequence

from .ir import Bar, Event, TimeSignature
from .notation_omr.note_duration import SCHEMA as NOTE_DURATION_SCHEMA
from .pdf_tab_event_factory import _STRING_TO_BASE_PITCH, build_note_type_event, unjoined_accidentals
from .pdf_tab_measure_timing import PdfTabBarAssemblerError, ticks_for_quarters
from .tabraw import TabCandidate

COLUMN_SPACES = 0.75  # TAB digits closer than this in x are one column (one chord)
MATCH_SPACES = 1.0  # a notation event and a TAB column further apart than this are not the same event
BAR_EDGE_SPACES = 0.5  # a TAB digit this close outside a notation bar's barlines still belongs to it
ENABLE_PARTIAL_TIE = True  # REFUSE-12 mutant switch: False refuses a chord whose one head is tied (the old behaviour)
ENABLE_HEAD_OWNED_TIES = True  # TIEOWN-01 mutant switch: False reads no per-head tie owner (the REFUSE-12 behaviour)
MAX_EVENTS_PER_BAR = 64 # more notation events or TAB columns than this in one bar is unsafe grouping


def empty_notation_source(note_durations: dict[str, Any] | None) -> bool:
    """Printed notation bars with no events, including no unread or out-of-bar events.

    This is a source-level decision. Callers must also exclude TAB digits; an empty bar in a
    source containing music retains the existing refusal rules.
    """
    if not note_durations or note_durations.get("schema") != NOTE_DURATION_SCHEMA:
        return False
    count = sum(s["bar_count"] for s in note_durations["systems"])
    diagnostics = note_durations.get("diagnostics", {})
    return (count > 0 and len(note_durations["bar_checks"]) == count
            and not note_durations["events"]
            and not diagnostics.get("located_unread_events")
            and not diagnostics.get("events_outside_bars")
            and not diagnostics.get("unread_symbols"))


def _refusal(reason: str, event_index: int | None = None, detail: str | None = None) -> dict[str, Any]:
    return {"reason": reason, "event_index": event_index, "detail": detail}


def _event_cx(record: dict[str, Any]) -> float:
    x0, _, x1, _ = record["location"]["bbox"]
    return (x0 + x1) / 2


def _columns(digits: Sequence[TabCandidate], space: float) -> list[list[TabCandidate]]:
    columns: list[list[TabCandidate]] = []
    for digit in sorted(digits, key=lambda c: c.x):
        if columns and digit.x - columns[-1][-1].x <= COLUMN_SPACES * space:
            columns[-1].append(digit)
        else:
            columns.append([digit])
    return columns


def _column_x(column: Sequence[TabCandidate]) -> float:
    return sum(c.x for c in column) / len(column)


def place_tab_digits(digits: Sequence[TabCandidate], note_durations: dict[str, Any]
                     ) -> tuple[dict[int, list[TabCandidate]], list[TabCandidate]]:
    """Each TAB digit's notation bar (global, zero-based): the nearest notation staff above it on its page,
    and the bar whose barlines enclose its x. Digits with no such bar are returned apart.

    TabRaw y runs on down the document (each page's height added); note-duration y is per page.
    """
    systems = note_durations["systems"]
    heights = note_durations["source"]["page_heights"]
    by_bar: dict[int, list[TabCandidate]] = {}
    unplaced: list[TabCandidate] = []
    for digit in digits:
        page = (digit.page_index or 1) - 1
        y = digit.y - sum(heights[:page])
        above = [s for s in systems if s["page_index"] == page and s["staff"]["bottom"] < y]
        if not above:
            unplaced.append(digit)
            continue
        system = max(above, key=lambda s: s["staff"]["bottom"])
        edge = BAR_EDGE_SPACES * system["staff_space"]
        bar = next((i for i, (a, b) in enumerate(system["bars"]) if a <= digit.x <= b), None)
        if bar is None:  # just outside a barline: the one bar it is within reach of, if only one
            near = [i for i, (a, b) in enumerate(system["bars"]) if a - edge <= digit.x <= b + edge]
            bar = near[0] if len(near) == 1 else None
        if bar is None:
            unplaced.append(digit)
            continue
        by_bar.setdefault(system["first_bar_index"] + bar, []).append(digit)
    return by_bar, unplaced


def _match_bar(records: list[dict[str, Any]], digits: list[TabCandidate], space: float,
               tied_from: dict[str, Any] | None, next_first: dict[str, Any] | None = None
               ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Per event: its match and TAB positions; or the first refusal, in event order."""
    columns = _columns(digits, space)
    column_x = [_column_x(c) for c in columns]
    used: set[int] = set()
    matched: list[dict[str, Any]] = []
    previous = tied_from
    for record in records:
        index = record["event_index"]
        cx = _event_cx(record)
        near = sorted((abs(x - cx), i) for i, x in enumerate(column_x) if abs(x - cx) <= MATCH_SPACES * space)
        if record["kind"] == "rest":
            if previous is not None and previous.get("pending_out") is not None:
                return matched, _refusal("tie_head_ownership_unconfirmed", index)
            if near:
                return matched, _refusal("rest_over_tab_digit", index)
            matched.append({"record": record, "match": {"kind": "rest"}, "positions": [], "candidates": []})
            previous = None
            continue
        heads = record["notehead"]["count"]
        cross_count = sum(h["kind"] == "cross" for h in record["notehead"].get("heads", []))
        tie = record.get("tie") or {}
        owed = previous.get("pending_out") if previous is not None else None
        if owed is not None and not _accounts_for(owed, previous, tie, heads):
            # The arc was read to leave only some heads of the chord before; this event must be where those
            # arcs end, else the narrowed tie has no destination and the bar stays refused.
            return matched, _refusal("tie_head_ownership_unconfirmed", index)
        owned_filled = False
        if cross_count and cross_count < heads and (tie.get("start") or tie.get("stop")):
            # Applying an event-level tie to every note would invent ties on strikes. The bar is written only
            # when the arc's own end is read on the chord's one filled head; otherwise it stays refused.
            owned_filled = _mixed_tie_owner(record, tie)
            if not owned_filled:
                return matched, _refusal("mixed_percussive_tie_ownership_unread", index)
        grace = record.get("grace")
        if grace:
            # A grace stands on its own TAB column and takes no tie; a later tie continues from the note before it.
            following = next((r for r in records[index + 1:] if not r.get("grace")), None)
            if following is None or grace["beat_event_index"] != following["event_index"]:
                return matched, _refusal("grace_note_beat_unattached", index)
            if not near:
                refusal = _refusal("notation_note_without_tab_digit", index)
                refusal["evidence"] = _disagreement_evidence(
                    records, columns, digits, "grace_note_without_tab_column", record)
                return matched, refusal
        if not near:
            tie = record.get("tie") or {}
            if _is_arriving_tie(tie, previous, heads):
                # REFUSE-11: the tie ran off the previous system's end on this very staff position and an arc
                # ends on this system's first note; a tied continuation prints no TAB digit.
                arrival = tie["arrives_from_previous_system"]
                record = {**record, "tie": {**tie, "stop": True, "sources": [*tie.get("sources", []), arrival["source"]]}}
                entry = {"record": record, "positions": list(previous["positions"]), "candidates": [],
                         "inherited": list(previous.get("candidates") or []),
                         "match": {"kind": "tie_continuation", "tied_from": previous["location"],
                                   "tie_from_previous_system": True}}
                matched.append(entry)
                previous = {"positions": entry["positions"], "location": _location(record),
                            "candidates": entry["inherited"], "tie": record["tie"]}
                continue
            if tie.get("stop") and previous is not None and len(previous["positions"]) == heads:
                entry = {"record": record, "positions": list(previous["positions"]), "candidates": [],
                         "inherited": list(previous.get("candidates") or []),
                         "match": {"kind": "tie_continuation", "tied_from": previous["location"]}}
                matched.append(entry)
                previous = {"positions": entry["positions"], "location": _location(record),
                            "candidates": entry["inherited"], "tie": record.get("tie")}
                continue
            owned = _owned_continuation(record, previous, heads, cross_count)
            if owned is not None:
                # TIEOWN-01: the arcs left ONE head (or some heads) of the chord before; this event's heads are
                # those the arcs end on, and it prints no digit. Only those positions are copied.
                _patch_previous_start(previous, owned)
                copied = owned["positions"]
                entry = {"record": record, "positions": list(copied), "candidates": [],
                         "inherited": [c for c in previous.get("candidates") or []
                                       if (c.string, c.parsed_fret) in copied],
                         "match": {"kind": "tie_continuation", "tied_from": previous["location"],
                                   "tie_owner": "head_owned"}}
                matched.append(entry)
                previous = {"positions": entry["positions"], "location": _location(record),
                            "candidates": entry["inherited"], "tie": record.get("tie"), "entry": entry}
                continue
            refusal = _refusal("notation_note_without_tab_digit", index)
            if tie.get("stop"):
                # A tied continuation prints no TAB digit; it is written only from the chord it continues.
                cause = ("tie_stop_without_written_predecessor" if previous is None
                         else "tie_stop_head_count_differs_from_predecessor")
            elif tie.get("arrives_from_previous_system") and previous is None:
                # An arc ends here from the system before, but no written note precedes it to continue.
                cause = "tie_stop_without_written_predecessor"
            else:
                cause = "no_tab_column_at_notation_event"
            refusal["evidence"] = _disagreement_evidence(records, columns, digits, cause, record)
            return matched, refusal
        if len(near) > 1 and near[1][0] - near[0][0] < COLUMN_SPACES * space:
            return matched, _refusal("notation_tab_column_ambiguous", index)
        column = near[0][1]
        if column in used:
            return matched, _refusal("notation_tab_column_ambiguous", index)
        used.add(column)
        cands = sorted(columns[column], key=lambda c: c.string)
        if len(cands) != heads and len({c.string for c in cands}) == len(cands):
            partial = _partial_tie_continuation(record, cands, previous, heads, cross_count)
            if partial is not None:
                # REFUSE-12: one head of this chord is the end of a tie from the single note before it and
                # prints no digit; the other heads print theirs. Only the tied head copies a position.
                positions = sorted([*partial["positions"], *((c.string, c.parsed_fret) for c in cands)])
                entry = {"record": record, "positions": positions, "candidates": cands,
                         "inherited": list(previous.get("candidates") or []),
                         "tied_positions": list(partial["positions"]),
                         "match": {"kind": "tab_column_with_tie_continuation",
                                   "candidate_ids": [c.id for c in cands],
                                   "tied_from": previous["location"],
                                   "dx_spaces": round(near[0][0] / space, 3)}}
                if partial.get("tie_states") is not None:
                    entry.pop("tied_positions")
                    entry["tie_states"] = partial["tie_states"]
                _patch_previous_start(previous, partial)
                matched.append(entry)
                previous = {"positions": positions, "location": _location(record),
                            "candidates": [*cands, *(previous.get("candidates") or [])], "tie": record.get("tie"),
                            "entry": entry}
                if partial.get("tie_out") is not None:
                    entry["tie_out"] = previous["tie_out"] = partial["tie_out"]
                    if len(partial["tie_out"]) < len(positions):
                        entry["pending_out"] = previous["pending_out"] = partial["tie_out"]
                continue
        if owed is not None and len(owed) != heads:
            # Every head of this event prints a digit, so no head is shown to be the one the arc ends on.
            return matched, _refusal("tie_head_ownership_unconfirmed", index)
        if len(cands) != heads or len({c.string for c in cands}) != len(cands):
            refusal = _refusal("notehead_digit_count_mismatch", index)
            # Keep the measured disagreement, rather than asking a caller to
            # reconstruct it from a partial match list. In particular, fewer
            # TAB digits never authorise copying positions from another chord.
            refusal["evidence"] = {
                "source": "notation_tab_column", "bbox": record["location"]["bbox"],
                "notation_head_count": heads, "tab_candidate_count": len(cands),
                "distinct_tab_strings": len({c.string for c in cands}),
                "tab_candidate_ids": [c.id for c in cands],
                "dx_spaces": round(near[0][0] / space, 3),
                "tab_side": _side(heads, len(cands)),
            }
            return matched, refusal
        positions = [(c.string, c.parsed_fret) for c in cands]
        if sum(c.kind == "percussive-strike" for c in cands) != cross_count:
            refusal = _refusal("percussive_strike_without_owning_head", index)
            refusal["candidate_ids"] = [c.id for c in cands if c.kind == "percussive-strike"]
            return matched, refusal
        entry = {"record": record, "positions": positions, "candidates": cands,
                 "match": {"kind": "tab_column", "candidate_ids": [c.id for c in cands],
                           "dx_spaces": round(near[0][0] / space, 3)}}
        tie_out = None
        if owned_filled:
            # TIEOWN-01: the arc leaves the chord's one filled head; the strikes carry no tie.
            tie_out = [(c.string, c.parsed_fret) for c in cands if c.kind != "percussive-strike"]
            entry["pending_out"] = tie_out
            entry["tie_states"] = {p: ("start" if p in tie_out else None) for p in positions}
            entry["tie_out"] = tie_out
        matched.append(entry)
        if not grace:
            previous = {"positions": positions, "location": _location(record), "candidates": cands,
                        "tie": record.get("tie"), "entry": entry}
            if tie_out is not None:
                previous["tie_out"] = tie_out
                previous["pending_out"] = tie_out
    if previous is not None and previous.get("pending_out") is not None:
        # The bar ends on a narrowed tie start: the first event of the next bar must be where it ends, with
        # exactly the tied heads (its digits are not known here, so it cannot have other heads).
        following = next_first
        if (following is None or following["kind"] == "rest" or not (following.get("tie") or {}).get("stop")
                or not _accounts_for(previous["pending_out"], previous, following["tie"],
                                     following["notehead"]["count"], exact=True)):
            return matched, _refusal("tie_head_ownership_unconfirmed", records[-1]["event_index"] if records else None)
    unused = [i for i in range(len(columns)) if i not in used]
    if unused:
        reason = ("percussive_strike_without_owning_note"
                  if any(c.kind == "percussive-strike" for c in columns[unused[0]])
                  else "tab_digit_without_notation_event")
        refusal = _refusal(reason)
        refusal["candidate_ids"] = [c.id for c in columns[unused[0]]]
        return matched, refusal
    return matched, None


def _pitch_order(positions: Sequence[tuple[int, int]]) -> list[tuple[int, int]] | None:
    """The positions lowest pitch first, or None when two share a pitch or a fret is unread (no order)."""
    if any(fret is None for _, fret in positions):
        return None
    ordered = sorted(positions, key=lambda p: _STRING_TO_BASE_PITCH[p[0]] + p[1])
    pitches = [_STRING_TO_BASE_PITCH[s] + f for s, f in ordered]
    return ordered if len(set(pitches)) == len(pitches) else None


def _mixed_tie_owner(record: dict[str, Any], tie: dict[str, Any]) -> bool:
    """True when the chord mixes strikes with one filled head and its tie is one arc starting on that head.

    The arc's start position is compared with each head's own staff position; it must equal the one
    filled head's. A stop, a chord with several filled heads or an arc on a strike stays unread.
    """
    if not ENABLE_HEAD_OWNED_TIES or tie.get("stop") or not tie.get("start") or tie.get("continues_beyond_system"):
        return False
    heads = record["notehead"].get("heads", [])
    filled = [h for h in heads if h["kind"] != "cross"]
    ranks = tie.get("start_head_ranks") or []
    indices = [h["staff_position_index"] for h in heads]
    if (len(filled) != 1 or len(heads) != record["notehead"]["count"] or len(set(indices)) != len(indices)
            or len(ranks) != 1 or len(tie.get("start_head_positions") or ()) != 1
            or len(tie.get("sources") or ()) != 1):
        return False
    # Head records count down from the top staff line; the arc end's rank counts up from the lowest head.
    return ranks[0] == sum(1 for i in indices if i > filled[0]["staff_position_index"])


def _accounts_for(owed: Sequence[tuple[int, int]], previous: dict[str, Any], tie: dict[str, Any],
                  heads: int, exact: bool = False) -> bool:
    """The event whose tie is ``tie`` is where the arcs that left ``owed`` heads end: it stops those arcs
    (as many as there are heads) and has at least that many heads, or exactly that many when ``exact``
    (an event whose digits are not yet known cannot be shown to leave the other heads untied)."""
    return bool(tie.get("stop") and (heads == len(owed) if exact else heads >= len(owed))
                and _shared_arcs(previous.get("tie") or {}, tie) == len(owed))


def _tie_out(previous: dict[str, Any]) -> tuple[list[tuple[int, int]], bool] | None:
    """The positions of the note or chord before whose tie arcs leave it, and whether its written event
    already ties exactly those (True) or ties its every head (False; patchable only in the same bar)."""
    if previous.get("tie_out") is not None:
        return list(previous["tie_out"]), True
    left = previous.get("tie") or {}
    positions = previous["positions"]
    if not left.get("start") or left.get("continues_beyond_system"):
        return None
    if len(positions) == 1:
        return list(positions), True
    ranks, starts = left.get("start_head_ranks") or [], left.get("start_head_positions") or []
    ordered = _pitch_order(positions)
    if ordered is None or not ranks or len(ranks) != len(starts) or len(set(ranks)) != len(ranks) \
            or max(ranks) >= len(ordered):
        return None
    out = [ordered[r] for r in sorted(ranks)]
    return out, len(out) == len(positions)


def _shared_arcs(a: dict[str, Any], b: dict[str, Any]) -> int:
    return len(set(a.get("sources") or ()) & set(b.get("sources") or ()))


def _patch_previous_start(previous: dict[str, Any], owned: dict[str, Any]) -> None:
    """Narrow the tie of the chord before to the heads its arcs leave, when it was matched in this bar."""
    if owned.get("patch_previous") is None:
        return
    entry = previous["entry"]
    out = list(owned["patch_previous"])
    entry["tie_states"] = {p: ("start" if p in out else None) for p in entry["positions"]}
    entry["tie_out"] = previous["tie_out"] = out


def _previous_out(previous: dict[str, Any] | None) -> tuple[list[tuple[int, int]], bool] | None:
    """(positions, applied) of the heads the previous event's arcs leave, or None when unreadable or
    when narrowing the written tie is impossible (the chord is in an earlier, written bar)."""
    if previous is None or not ENABLE_HEAD_OWNED_TIES:
        return None
    found = _tie_out(previous)
    if found is None:
        return None
    entry = previous.get("entry")
    patchable = bool(entry is not None and not (previous.get("tie") or {}).get("stop")
                     and entry.get("tie_states") is None)
    return found if found[1] or patchable else None


def _owned_continuation(record: dict[str, Any], previous: dict[str, Any] | None, heads: int,
                        cross_count: int) -> dict[str, Any] | None:
    """The positions an event with no digit of its own copies when the arcs ending on it leave exactly
    those heads of the note or chord before, else None (stay refused).

    The arcs are shared drawings, as many as the event has heads, and their end positions equal their
    start positions.
    """
    tie = record.get("tie") or {}
    found = _previous_out(previous)
    if found is None or cross_count or not tie.get("stop"):
        return None
    out, applied = found
    left = previous["tie"]
    if len(out) != heads or len(out) >= len(previous["positions"]) or _shared_arcs(left, tie) != heads:
        return None
    if heads > 1 and sorted(tie.get("stop_head_positions") or ()) != sorted(left.get("start_head_positions") or ()):
        return None
    return {"positions": list(out), "patch_previous": None if applied else list(out)}


def _partial_tie_continuation(record: dict[str, Any], cands: Sequence[TabCandidate], previous: dict[str, Any] | None,
                              heads: int, cross_count: int) -> dict[str, Any] | None:
    """The tied heads' positions when some heads of ``record`` are the ends of arcs that left the note or
    chord written just before it, and the chord's other heads each have a TAB digit; else None (stay refused).

    The arcs' two ends are one drawing shared by both records (a tie, not a slur: it joins the same staff
    position), and the tied heads are exactly the ones without a digit. REFUSE-12 read one head tied from a
    single note; TIEOWN-01 reads several heads tied from a chord, and a chord that also starts a tie.
    """
    tie = record.get("tie") or {}
    k = heads - len(cands)
    if (not ENABLE_PARTIAL_TIE or previous is None or cross_count or not tie.get("stop") or k < 1
            or len(tie.get("stop_head_positions") or ()) != k):
        return None
    left = previous.get("tie") or {}
    if len(previous["positions"]) == 1 and not tie.get("start") and k == 1:
        if (not left.get("start") or left.get("continues_beyond_system")
                or not set(left.get("sources") or ()) & set(tie.get("sources") or ())):
            return None
        string, fret = previous["positions"][0]
        if fret is None or string in {c.string for c in cands}:
            return None
        return {"positions": [(string, fret)]}
    found = _previous_out(previous)
    stops = tie.get("stop_head_ranks") or []
    if found is None or len(found[0]) != k or len(stops) != k or len(set(stops)) != k or _shared_arcs(left, tie) != k:
        return None
    copied, applied = found
    if any(string in {c.string for c in cands} for string, _ in copied):
        return None
    union = _pitch_order([*copied, *((c.string, c.parsed_fret) for c in cands)])
    if union is None or len(union) != heads or sorted(union.index(p) for p in copied) != sorted(stops):
        return None
    if sorted(tie.get("stop_head_positions") or ()) != sorted(left.get("start_head_positions") or ()) and len(copied) > 1:
        return None
    out = None
    if tie.get("start"):
        starts = tie.get("start_head_ranks") or []
        if (not starts or len(starts) != len(tie.get("start_head_positions") or ()) or len(set(starts)) != len(starts)
                or max(starts) >= heads or tie.get("continues_beyond_system")):
            return None
        out = [union[r] for r in sorted(starts)]
    states = {}
    for position in union:
        stops_here, starts_here = position in copied, out is not None and position in out
        states[position] = ("continue" if stops_here and starts_here else "stop" if stops_here
                            else "start" if starts_here else None)
    return {"positions": copied, "tie_states": states, "tie_out": out,
            "patch_previous": None if applied else list(copied)}


def _is_arriving_tie(tie: dict[str, Any], previous: dict[str, Any] | None, heads: int) -> bool:
    """An arc ends on this event from the system before, and the written note before it ran off its system
    end at the same staff position (both single heads). Same place on both sides is what makes it a tie."""
    arrival = tie.get("arrives_from_previous_system")
    if tie.get("stop") or not arrival or previous is None or heads != 1 or len(previous["positions"]) != 1:
        return False
    left = previous.get("tie") or {}
    return bool(left.get("start") and left.get("continues_beyond_system")
                and left.get("leaving_head_position") == arrival["head_position"])


def _side(notation: int, tab: int) -> str:
    """Which side of a notation/TAB count disagreement has the extra item."""
    if notation == tab:
        return "counts_equal"
    return "notation_has_extra" if notation > tab else "tab_has_extra"


def _disagreement_evidence(records: list[dict[str, Any]], columns: Sequence[Sequence[TabCandidate]],
                           digits: Sequence[TabCandidate], cause: str, record: dict[str, Any] | None = None,
                           **more: Any) -> dict[str, Any]:
    """Where and how the notation and the TAB of one bar disagree (REFUSE-04): counts and a cause, no content."""
    played = [r for r in records if r["kind"] != "rest"]
    evidence: dict[str, Any] = {
        "source": "notation_tab_bar_counts", "cause": cause,
        "notation_events": len(played), "tab_columns": len(columns), "tab_digits": len(digits),
        "tab_side": _side(len(played), len(columns)),
    }
    if record is not None:
        evidence["bbox"] = record["location"]["bbox"]
    evidence.update(more)
    return evidence


def _location(record: dict[str, Any]) -> dict[str, Any]:
    return {"page_index": record["page_index"], "bar_index": record["bar_index"], "event_index": record["event_index"]}


def _time_signature(check: dict[str, Any]) -> TimeSignature:
    numerator, denominator = (int(v) for v in check["time_signature"].split("/"))
    return TimeSignature(numerator=numerator, denominator=denominator)


def assemble_note_type_bars(digits: Sequence[TabCandidate], note_durations: dict[str, Any], *,
                            track_id: str, refused_tab_system: Any = None) -> tuple[list[Bar], dict[str, Any]]:
    """Bars for every notation bar, written from note types and TAB positions or refused and left empty.

    ``refused_tab_system`` (PARTIAL-01) is the one TAB system whose layout is refused; its digits are
    not among ``digits`` and every bar of its notation system is refused, located, and left empty.

    Returns the bars and the route record: per bar its status, reason, location and per-event match.
    """
    if note_durations.get("schema") != NOTE_DURATION_SCHEMA:
        raise PdfTabBarAssemblerError(
            category="pdf_only_tab_note_durations_incompatible",
            stage="note-type-route",
            message=f"Note-duration records are {note_durations.get('schema')!r}; the route reads {NOTE_DURATION_SCHEMA!r}.",
            details={"schema": str(note_durations.get("schema"))},
        )
    systems = note_durations["systems"]
    checks = {c["bar_index"]: c for c in note_durations["bar_checks"]}
    bar_bases = {int(bar): basis for bar, basis in note_durations.get("diagnostics", {}).get("bar_time_signatures", {}).items()}
    bar_keys = {int(bar): key for bar, key in note_durations.get("diagnostics", {}).get("bar_key_signatures", {}).items()}
    unsigned = sorted(bar for bar, check in checks.items() if not check.get("time_signature"))
    if unsigned:
        raise PdfTabBarAssemblerError(
            category="pdf_only_tab_time_signature_unread",
            stage="note-type-route",
            message=(f"No time signature is printed or readable for {len(unsigned)} bar(s), first bar index "
                     f"{unsigned[0]}; declare one with --time-signature."),
            details={"first_bar_index": str(unsigned[0]), "bars": str(len(unsigned)),
                     "remediation_hint": "Declare the printed time signature with --time-signature (e.g. 4/4)."},
        )
    by_bar: dict[int, list[dict[str, Any]]] = {}
    for record in note_durations["events"]:
        by_bar.setdefault(record["bar_index"], []).append(record)
    placed, unplaced = place_tab_digits(digits, note_durations)
    system_of = {s["first_bar_index"] + i: s for s in systems for i in range(s["bar_count"])}
    diagnostics = note_durations.get("diagnostics", {})
    empty_source = not digits and empty_notation_source(note_durations)
    overlaps: dict[int, list[dict[str, Any]]] = {}
    for symbol in diagnostics.get("unread_symbols", []):
        if symbol["class"] in ("unsupported_overlapping_form", "parenthesized_head_unrepresented"):
            overlaps.setdefault(symbol["location"]["bar_index"], []).append(symbol)
    base_written: set[tuple[Any, ...]] = set()
    baseline = diagnostics.get("base_equivalent_note_durations")
    if overlaps and baseline is not None:
        try:
            _, base_route = assemble_note_type_bars(
                digits, baseline, track_id=track_id, refused_tab_system=refused_tab_system)
        except PdfTabBarAssemblerError:
            # A base route that could not build a score wrote no bar.
            pass
        else:
            written = {b["source_bar_index"] for b in base_route["bars"] if b["status"] == "written"}
            base_written = {
                (s["page_index"], s["system_index"], *bounds)
                for s in baseline["systems"] for i, bounds in enumerate(s["bars"])
                if s["first_bar_index"] + i in written
            }

    bars: list[Bar] = []
    route_bars: list[dict[str, Any]] = []
    tied_from: dict[str, Any] | None = None
    for source_bar in sorted(checks):
        check = checks[source_bar]
        basis = bar_bases.get(source_bar)
        key = bar_keys.get(source_bar, {})
        system = system_of[source_bar]
        records = sorted(by_bar.get(source_bar, []), key=lambda r: r["event_index"])
        bar_digits = placed.get(source_bar, [])
        output_index = source_bar + 1
        entry: dict[str, Any] = {
            "source_bar_index": source_bar, "output_bar_index": output_index,
            "time_signature": check["time_signature"], "time_signature_source": check["time_signature_source"],
            "time_signature_basis": basis["basis"] if basis else None,
            "time_signature_origin": basis["origin"] if basis else None,
            "declared_time_signature": basis["declared"] if basis else None,
            "time_signature_unread": basis["unread"] if basis else None,
            "notation_events": len(records), "tab_digits": len(bar_digits), "events": [],
        }
        # Account for the entire bar, including events after its first refusal.
        # Refusing a bar withholds its strikes; it must not erase their locations.
        strikes = []
        for record in records:
            heads = [h for h in (record.get("notehead") or {}).get("heads", []) if h["kind"] == "cross"]
            if heads:
                strikes.append({"location": record["location"], "head_count": len(heads),
                                "head_sources": [h["source"] for h in heads]})
        entry["percussive_strikes"] = {
            "notation_head_count": sum(r["head_count"] for r in strikes),
            "notation_events": strikes,
            "tab_candidates": [
                {"candidate_id": c.id, "string": c.string,
                 "bbox": [c.bbox.x0, c.bbox.y0, c.bbox.x1, c.bbox.y1] if c.bbox else None}
                for c in sorted(bar_digits, key=lambda c: (c.x, c.string or 0, c.id))
                if c.kind == "percussive-strike"
            ],
        }
        crowded = max(len(records), len(_columns(bar_digits, system["staff_space"])))
        if crowded > MAX_EVENTS_PER_BAR:
            raise PdfTabBarAssemblerError(
                category="pdf_only_tab_grouping_unsafe",
                stage="layout-gating",
                message=f"PDF-only tab building refused: too many events ({crowded}) in bar {output_index}.",
            )
        unread = next((r for r in records if r["status"] != "read"), None)
        refusal = None
        matched: list[dict[str, Any]] = []
        if (refused_tab_system is not None
                and (system["page_index"], system["system_index"])
                == (refused_tab_system.notation_page_index, refused_tab_system.notation_system_index)):
            refusal = _refusal(refused_tab_system.code, None,
                               f"TAB page {refused_tab_system.page_index}, system {refused_tab_system.system_index}")
        elif key.get("status") == "refused" and key.get("refuse_bar"):
            refusal = _refusal(key["reason"])
            refusal["evidence"] = {
                "source": "bar_key_signature", "source_ids": key["sources"],
                "location": key["location"],
            }
        elif check["status"] == "signature_conflict":
            refusal = _refusal("time_signature_conflict", None,
                               f"printed {check['time_signature']}, declared {basis['declared']}")
        elif unread is not None:
            refusal = _refusal("note_duration_event_unread", unread["event_index"], unread["reason"])
            refusal["evidence"] = {
                "source": "note_duration_record", "cause": unread["reason"],
                "bbox": unread["location"]["bbox"],
            }
        elif not records:
            refusal = None if empty_source else _refusal("bar_without_notation_event")
            if refusal is not None:
                refusal["evidence"] = {
                    "source": "notation_tab_bar_counts",
                    "cause": ("tab_digits_without_notation_event" if bar_digits else "bar_without_notation_or_tab_item"),
                    "notation_events": 0, "tab_columns": len(_columns(bar_digits, system["staff_space"])),
                    "tab_digits": len(bar_digits), "tab_side": "tab_has_extra" if bar_digits else "counts_equal",
                    "rhythm_source": "tab_rhythm" if "tab_rhythm" in diagnostics else "notation_staff",
                }
        else:
            next_first = next((r for r in sorted(by_bar.get(source_bar + 1, []), key=lambda r: r["event_index"])
                               if not r.get("grace")), None)
            matched, refusal = _match_bar(records, bar_digits, system["staff_space"], tied_from, next_first)
            if refusal is None and check["status"] != "match":
                refusal = _refusal("bar_total_mismatch",
                                   detail=f"{check['total_quarters']} of {check['expected_quarters']} quarters")
                total, expected = Fraction(check["total_quarters"]), Fraction(check["expected_quarters"])
                refusal["evidence"] = _disagreement_evidence(
                    records, _columns(bar_digits, system["staff_space"]), bar_digits,
                    "notation_total_below_meter" if total < expected else "notation_total_above_meter",
                    status=check["status"], total_quarters=str(total), expected_quarters=str(expected))
        entry["events"] = [{"event_index": m["record"]["event_index"], "kind": m["record"]["kind"],
                            "match": m["match"]} for m in matched]
        if source_bar in overlaps:
            bounds = system["bars"][source_bar - system["first_bar_index"]]
            preserved = (system["page_index"], system["system_index"], *bounds) in base_written
            entry["unread_symbols"] = overlaps[source_bar]
            entry["overlap_preservation_basis"] = (
                "base_equivalent_written" if preserved else "base_equivalent_refused")
            ghost_only = all(sym["class"] == "parenthesized_head_unrepresented" for sym in overlaps[source_bar]) and all(
                r.get("ghost") for r in records if r.get("unread_symbols"))
            if preserved or not ghost_only:
                # REFUSE-14: a parenthesis is read as a ghost note only where it alone kept the bar refused.
                # A bar the base reader already wrote keeps its previous (un-ghosted) notes unchanged, and any
                # other overlapping form refuses the bar as before.
                for m in matched:
                    m["record"].pop("ghost", None)
            if refusal is None and not preserved and not ghost_only:
                symbol = overlaps[source_bar][0]
                refusal = _refusal("note_duration_event_unread",
                                   symbol["location"]["event_index"], symbol["class"])
                refusal["evidence"] = {
                    "source": "unread_symbol", "cause": symbol["class"],
                    "position": symbol["reason"], "source_id": symbol["source"],
                    "bbox": symbol["location"]["bbox"],
                }
                entry["events"] = []
        events: list[Event] = []
        if refusal is None:
            onset = Fraction(0)
            unjoined = [{"event_index": m["record"]["event_index"], "sources": [a["source"] for a in bad]}
                        for m in matched if m["record"]["kind"] != "rest"
                        for bad in [unjoined_accidentals(m["record"], m["positions"])] if bad]
            if unjoined:
                entry["unjoined_accidentals"] = unjoined
            for i, m in enumerate(matched):
                events.append(build_note_type_event(
                    m["record"], positions=m["positions"], candidates=m["candidates"], output_bar_idx=output_index,
                    event_idx=i, onset_ticks=ticks_for_quarters(onset) if onset else 0, track_id=track_id,
                    inherited=m.get("inherited") or (), tied_positions=m.get("tied_positions"),
                    tie_states=m.get("tie_states")))
                onset += Fraction(m["record"]["duration_quarters"])  # a grace adds none
            last = matched[-1] if matched else None
            tied_from = ({"positions": last["positions"], "location": _location(last["record"]),
                          "candidates": last["candidates"] or last.get("inherited") or [],
                          "tie": last["record"].get("tie"), "tie_out": last.get("tie_out"),
                          "pending_out": last.get("pending_out"), "entry": None}
                         if last is not None and last["record"]["kind"] != "rest" else None)
            entry.update(status="written", reason=None, detail=None, location=None)
            implied = sum(1 for m in matched if (m["record"].get("rest") or {}).get("implied"))
            if implied:
                # TABRHY-01: a rest the printed marks do not show, written to fill the bar's end; never a printed rest.
                entry["implied_rests"] = implied
                entry["rhythm_basis"] = "printed_marks_with_implied_rest"
            elif any(m["record"].get("tab_rhythm") for m in matched):
                entry["rhythm_basis"] = "printed_marks"
        else:
            tied_from = None
            location = {"page_index": system["page_index"], "system_index": system["system_index"],
                        "bar_index": source_bar}
            if refusal["event_index"] is not None:
                location["event_index"] = refusal["event_index"]
            if refusal.get("candidate_ids"):
                location["tab_candidate_ids"] = refusal["candidate_ids"]
            entry.update(status="refused", reason=refusal["reason"], detail=refusal["detail"], location=location)
            if "evidence" in refusal:
                entry["refusal_evidence"] = refusal["evidence"]
        route_bars.append(entry)
        bars.append(Bar(index=output_index, time_signature=_time_signature(check), events=events))

    reasons: dict[str, int] = {}
    for entry in route_bars:
        if entry["reason"]:
            reasons[entry["reason"]] = reasons.get(entry["reason"], 0) + 1
    match_kinds: dict[str, int] = {}
    for entry in route_bars:
        for event in entry["events"] if entry["status"] == "written" else []:
            match_kinds[event["match"]["kind"]] = match_kinds.get(event["match"]["kind"], 0) + 1
    route: dict[str, Any] = {
        "schema": "note-type-route.v0.1",
        "note_durations_schema": note_durations["schema"],
        "bars": route_bars,
        "unplaced_tab_digits": [{"candidate_id": c.id, "page_index": (c.page_index or 1) - 1} for c in unplaced],
        "summary": {
            "source_bars": len(route_bars),
            "written_bars": sum(1 for e in route_bars if e["status"] == "written"),
            "refused_bars": sum(1 for e in route_bars if e["status"] == "refused"),
            "refusal_reasons": dict(sorted(reasons.items())),
            "match_kinds": dict(sorted(match_kinds.items())),
            "tab_digits": len(digits),
            "unplaced_tab_digits": len(unplaced),
        },
    }
    written = [e for e in route_bars if e["status"] == "written"]
    if any("rhythm_basis" in e for e in route_bars):
        route["summary"]["written_bars_printed_marks"] = sum(1 for e in written if e.get("rhythm_basis") == "printed_marks")
        route["summary"]["written_bars_with_implied_rest"] = sum(1 for e in written if e.get("implied_rests"))
        route["summary"]["implied_rests"] = sum(e.get("implied_rests", 0) for e in written)
    unowned_strikes = [c for c in unplaced if c.kind == "percussive-strike"]
    if unowned_strikes:
        route["located_refusals"] = [
            {"class": "percussive_strike", "reason": "percussive_strike_without_owning_note",
             "candidate_id": c.id, "location": {"page_index": (c.page_index or 1) - 1,
             "system_index": c.system_index, "bar_index": c.bar_index, "string": c.string,
             "bbox": c.bbox.model_dump() if c.bbox else None}}
            for c in unowned_strikes]
    if refused_tab_system is not None:
        route["refused_tab_systems"] = [refused_tab_system.to_json()]
        route["summary"]["refused_tab_systems"] = 1
    return bars, route
