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
from .pdf_tab_event_factory import build_note_type_event, unjoined_accidentals
from .pdf_tab_measure_timing import PdfTabBarAssemblerError, ticks_for_quarters
from .tabraw import TabCandidate

COLUMN_SPACES = 0.75  # TAB digits closer than this in x are one column (one chord)
MATCH_SPACES = 1.0  # a notation event and a TAB column further apart than this are not the same event
BAR_EDGE_SPACES = 0.5  # a TAB digit this close outside a notation bar's barlines still belongs to it
MAX_EVENTS_PER_BAR = 64  # more notation events or TAB columns than this in one bar is unsafe grouping


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
               tied_from: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
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
            if near:
                return matched, _refusal("rest_over_tab_digit", index)
            matched.append({"record": record, "match": {"kind": "rest"}, "positions": [], "candidates": []})
            previous = None
            continue
        heads = record["notehead"]["count"]
        grace = record.get("grace")
        if grace:
            # A grace stands on its own TAB column and takes no tie; a later tie continues from the note before it.
            following = next((r for r in records[index + 1:] if not r.get("grace")), None)
            if following is None or grace["beat_event_index"] != following["event_index"]:
                return matched, _refusal("grace_note_beat_unattached", index)
            if not near:
                return matched, _refusal("notation_note_without_tab_digit", index)
        if not near:
            tie = record.get("tie") or {}
            if tie.get("stop") and previous is not None and len(previous["positions"]) == heads:
                entry = {"record": record, "positions": list(previous["positions"]), "candidates": [],
                         "match": {"kind": "tie_continuation", "tied_from": previous["location"]}}
                matched.append(entry)
                previous = {"positions": entry["positions"], "location": _location(record)}
                continue
            return matched, _refusal("notation_note_without_tab_digit", index)
        if len(near) > 1 and near[1][0] - near[0][0] < COLUMN_SPACES * space:
            return matched, _refusal("notation_tab_column_ambiguous", index)
        column = near[0][1]
        if column in used:
            return matched, _refusal("notation_tab_column_ambiguous", index)
        used.add(column)
        cands = sorted(columns[column], key=lambda c: c.string)
        if len(cands) != heads or len({c.string for c in cands}) != len(cands):
            return matched, _refusal("notehead_digit_count_mismatch", index)
        positions = [(c.string, c.parsed_fret) for c in cands]
        matched.append({"record": record, "positions": positions, "candidates": cands,
                        "match": {"kind": "tab_column", "candidate_ids": [c.id for c in cands],
                                  "dx_spaces": round(near[0][0] / space, 3)}})
        if not grace:
            previous = {"positions": positions, "location": _location(record)}
    unused = [i for i in range(len(columns)) if i not in used]
    if unused:
        refusal = _refusal("tab_digit_without_notation_event")
        refusal["candidate_ids"] = [c.id for c in columns[unused[0]]]
        return matched, refusal
    return matched, None


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

    bars: list[Bar] = []
    route_bars: list[dict[str, Any]] = []
    tied_from: dict[str, Any] | None = None
    for source_bar in sorted(checks):
        check = checks[source_bar]
        basis = bar_bases.get(source_bar)
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
        elif check["status"] == "signature_conflict":
            refusal = _refusal("time_signature_conflict", None,
                               f"printed {check['time_signature']}, declared {basis['declared']}")
        elif unread is not None:
            refusal = _refusal("note_duration_event_unread", unread["event_index"], unread["reason"])
        elif not records:
            refusal = _refusal("bar_without_notation_event")
        else:
            matched, refusal = _match_bar(records, bar_digits, system["staff_space"], tied_from)
            if refusal is None and check["status"] != "match":
                refusal = _refusal("bar_total_mismatch",
                                   detail=f"{check['total_quarters']} of {check['expected_quarters']} quarters")
        entry["events"] = [{"event_index": m["record"]["event_index"], "kind": m["record"]["kind"],
                            "match": m["match"]} for m in matched]
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
                    event_idx=i, onset_ticks=ticks_for_quarters(onset) if onset else 0, track_id=track_id))
                onset += Fraction(m["record"]["duration_quarters"])  # a grace adds none
            last = matched[-1]
            tied_from = ({"positions": last["positions"], "location": _location(last["record"])}
                         if last["record"]["kind"] != "rest" else None)
            entry.update(status="written", reason=None, detail=None, location=None)
        else:
            tied_from = None
            location = {"page_index": system["page_index"], "system_index": system["system_index"],
                        "bar_index": source_bar}
            if refusal["event_index"] is not None:
                location["event_index"] = refusal["event_index"]
            if refusal.get("candidate_ids"):
                location["tab_candidate_ids"] = refusal["candidate_ids"]
            entry.update(status="refused", reason=refusal["reason"], detail=refusal["detail"], location=location)
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
    if refused_tab_system is not None:
        route["refused_tab_systems"] = [refused_tab_system.to_json()]
        route["summary"]["refused_tab_systems"] = 1
    return bars, route
