"""PARTIAL-01: which TAB systems of a refused layout can still be written, and which one is refused.

The PDF-only route refuses a whole file when any layout warning is present. This module decides,
from evidence already in TabRaw, whether the warnings come from exactly one TAB system whose every
other system stands on its own. The per-system rule, stated once:

A TAB system is *readable* only if every one of its playable digits has a system, a string, a bar and
an x; none of its digits or its system geometry carries an unsafe layout code; and its barlines make
at least two boxes. Any other system is *refused*: unboxed, boxes narrow/overlapping/outside the
system, a digit unassigned to a bar or a string, or any other unsafe code.

The file is written partially only if exactly one system is refused, at least one is readable, every
unsafe warning of the file is located in the refused system (or is a code that only candidate
evidence can raise, and the readable systems carry none), and the pairing with the notation staves is
unambiguous: each TAB system's digits sit under exactly one notation system, no two TAB systems share
one, the refused system's page has as many notation systems as TAB systems, and every notation bar of
the refused system is read in full and adds up to its time signature (its bar count numbers all later
bars). Anything else
returns ``None`` and the caller refuses the whole file, as before.

Nothing is guessed: the refused system's digits are not written, its notation bars are refused with a
located code, and the bar numbering is the notation's own, so the gap is explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .tabraw import TabCandidate, TabRaw

BOX_WARNING_CODES = frozenset({
    "pdf_bar_box_too_narrow",
    "pdf_bar_box_outside_system_bounds",
    "pdf_bar_box_overlaps_neighbor",
})

# Unsafe codes that a system's own candidates can raise. Every other unsafe code (no systems, system
# order or bounding box ambiguous, ...) concerns the page layout as a whole and refuses the whole file.
SYSTEM_ATTRIBUTABLE_CODES = frozenset({
    "pdf_string_lines_missing",
    "pdf_tab_staff_incomplete",
    "incomplete_tab_staff",
    "pdf_candidates_unassigned_to_string",
    "pdf_barlines_missing",
    "pdf_bar_boxes_missing",
    "missing_pdf_barlines",
    "pdf_bar_box_construction_not_enough_for_build_ir",
    "pdf_candidates_unassigned_to_bar",
    "pdf_string_assignment_ambiguous",
    "ambiguous_string_assignment",
    "pdf_barlines_ambiguous",
    "ambiguous_bar_assignment",
})

CODE_UNBOXED = "tab_system_unboxed"
CODE_BOXES_INVALID = "tab_system_bar_boxes_invalid"
CODE_UNASSIGNED_BAR = "tab_system_digit_unassigned_to_bar"
CODE_UNASSIGNED_STRING = "tab_system_digit_unassigned_to_string"
CODE_LAYOUT_WARNING = "tab_system_layout_warning"


@dataclass(frozen=True)
class RefusedTabSystem:
    page_index: int  # one-based, as TabRaw
    system_index: int  # one-based, as TabRaw
    code: str
    warning_codes: tuple[str, ...]
    digit_count: int
    notation_page_index: int  # zero-based, as the note-duration records
    notation_system_index: int  # zero-based, as the note-duration records

    def to_json(self) -> dict[str, Any]:
        return {
            "page_index": self.page_index - 1, "system_index": self.system_index - 1, "code": self.code,
            "warning_codes": list(self.warning_codes), "tab_digits": self.digit_count,
            "notation_page_index": self.notation_page_index,
            "notation_system_index": self.notation_system_index,
        }


def notation_system_of(digit: TabCandidate, note_durations: dict[str, Any]) -> dict[str, Any] | None:
    """The nearest notation staff above a TAB digit on its page (TabRaw y runs on down the document)."""
    heights = note_durations["source"]["page_heights"]
    page = (digit.page_index or 1) - 1
    y = digit.y - sum(heights[:page])
    above = [s for s in note_durations["systems"] if s["page_index"] == page and s["staff"]["bottom"] < y]
    return max(above, key=lambda s: s["staff"]["bottom"]) if above else None


def _raw(candidate: TabCandidate) -> dict[str, Any]:
    return candidate.raw or {}


def _system_verdict(candidates: Sequence[TabCandidate], unsafe: frozenset[str]) -> tuple[str, tuple[str, ...]] | None:
    """(code, warning codes) if the system is refused; ``None`` if it is readable."""
    found: set[str] = set()
    for candidate in candidates:
        raw = _raw(candidate)
        for warning in list(raw.get("grouping_warnings") or []) + list(raw.get("assignment_warnings") or []):
            if warning in unsafe or warning in BOX_WARNING_CODES:
                found.add(warning)
    barline_counts = {_raw(c).get("barline_count") for c in candidates}
    if any(count is None or count < 2 for count in barline_counts):
        return CODE_UNBOXED, tuple(sorted(found))
    if found & BOX_WARNING_CODES:
        return CODE_BOXES_INVALID, tuple(sorted(found))
    if any(c.bar_index is None for c in candidates):
        return CODE_UNASSIGNED_BAR, tuple(sorted(found))
    if any(c.string is None for c in candidates):
        return CODE_UNASSIGNED_STRING, tuple(sorted(found))
    if found:
        return CODE_LAYOUT_WARNING, tuple(sorted(found))
    return None


def partition_tab_systems(
    tabraw: TabRaw, digits: Sequence[TabCandidate], note_durations: dict[str, Any], unsafe: Iterable[str],
) -> tuple[RefusedTabSystem, list[TabCandidate]] | None:
    """The one refused system and the digits of the readable systems; ``None`` to refuse the whole file."""
    unsafe_codes = frozenset(unsafe)
    if not digits or not note_durations.get("systems") or "source" not in note_durations:
        return None
    if any(d.system_index is None or d.page_index is None or d.x is None or d.y is None for d in digits):
        return None

    by_system: dict[tuple[int, int], list[TabCandidate]] = {}
    for digit in digits:
        by_system.setdefault((digit.page_index, digit.system_index), []).append(digit)

    verdicts = {key: _system_verdict(group, unsafe_codes) for key, group in by_system.items()}
    refused_keys = [key for key, verdict in verdicts.items() if verdict is not None]
    if len(refused_keys) != 1 or len(refused_keys) == len(by_system):
        return None
    refused_key = refused_keys[0]

    # Every unsafe warning of the file must belong to the refused system.
    for warning in list(tabraw.warnings) + [{"code": code} for code in tabraw.pdf_layout_warnings]:
        code = warning.get("code")
        if code not in unsafe_codes:
            continue
        page, system = warning.get("page_index"), warning.get("system_index")
        if page is not None and system is not None:
            if (page, system) != refused_key:
                return None
        elif code not in SYSTEM_ATTRIBUTABLE_CODES:
            return None

    # Pairing with the notation staves.
    paired: dict[tuple[int, int], tuple[int, int]] = {}
    for key, group in by_system.items():
        owners = {(s["page_index"], s["system_index"]) if s else None for s in (notation_system_of(d, note_durations) for d in group)}
        if len(owners) != 1 or None in owners:
            return None
        paired[key] = next(iter(owners))
    if len(set(paired.values())) != len(paired):
        return None
    notation_page, notation_system = paired[refused_key]
    tab_systems_on_page = sum(1 for page, _ in by_system if page == refused_key[0])
    notation_systems_on_page = sum(1 for s in note_durations["systems"] if s["page_index"] == notation_page)
    if tab_systems_on_page != notation_systems_on_page:
        return None

    # The refused system's bar count comes from the notation alone, and it numbers every later bar: it is
    # trusted only if each of its notation bars is read in full and adds up to its time signature.
    system = next(s for s in note_durations["systems"] if (s["page_index"], s["system_index"]) == (notation_page, notation_system))
    checks = {c["bar_index"]: c for c in note_durations.get("bar_checks", [])}
    records: dict[int, list[dict[str, Any]]] = {}
    for record in note_durations.get("events", []):
        records.setdefault(record["bar_index"], []).append(record)
    first = system["first_bar_index"]
    if system["bar_count"] < 1:
        return None
    for bar in range(first, first + system["bar_count"]):
        check = checks.get(bar)
        if (check is None or check.get("status") != "match" or not check.get("time_signature")
                or not records.get(bar) or any(r.get("status") != "read" for r in records[bar])):
            return None

    code, warning_codes = verdicts[refused_key]  # type: ignore[misc]
    refused = RefusedTabSystem(
        page_index=refused_key[0], system_index=refused_key[1], code=code, warning_codes=warning_codes,
        digit_count=len(by_system[refused_key]), notation_page_index=notation_page,
        notation_system_index=notation_system,
    )
    readable = [d for d in digits if (d.page_index, d.system_index) != refused_key]
    return refused, readable
