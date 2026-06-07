from __future__ import annotations

from collections import defaultdict
from pydantic import BaseModel, Field

from .pdf_staff_timing import PdfStaffTimingEvent
from .pdf_only_chord_event_grouper import CandidateXGroupDiagnostics

PDF_STAFF_TAB_ALIGNMENT_X_TOLERANCE_PT = 15.0


class PdfStaffTabAlignmentResult(BaseModel):
    aligned_pairs: list[tuple[PdfStaffTimingEvent, CandidateXGroupDiagnostics | None]] = Field(default_factory=list)
    unmatched_staff_events: list[PdfStaffTimingEvent] = Field(default_factory=list)
    unmatched_tab_groups: list[CandidateXGroupDiagnostics] = Field(default_factory=list)
    ambiguous_staff_events: list[PdfStaffTimingEvent] = Field(default_factory=list)
    bars_using_staff_timing: list[tuple[int, int, int, int]] = Field(default_factory=list)
    bars_using_fallback_timing: list[tuple[int, int, int, int]] = Field(default_factory=list)


class PdfStaffTabTimingAligner:
    """Aligns standard staff timing events with TAB visual x-groups within each bar.

    Alignment is tolerance-bound and restricted by source bar identity.
    """

    def __init__(self, tolerance: float = PDF_STAFF_TAB_ALIGNMENT_X_TOLERANCE_PT) -> None:
        self.tolerance = tolerance

    def _alignment_bar_key(
        self,
        page_index: int,
        system_index: int,
        staff_index: int | None,
        local_bar_index: int,
    ) -> tuple[int, int, int, int]:
        """Normalize the bar key, mapping absolute staff index to a staff-pair index.

        For the MVP:
        - Notation staff (odd absolute index, e.g. 1) and TAB staff (even absolute index, e.g. 2)
          map to staff_pair_index = 1.
        - Notation staff index 3 and TAB staff index 4 map to staff_pair_index = 2.
        """
        if staff_index is None:
            staff_pair_index = 1
        elif staff_index % 2 == 1:
            staff_pair_index = (staff_index + 1) // 2
        else:
            staff_pair_index = staff_index // 2

        return (page_index, system_index, staff_pair_index, local_bar_index)

    def align(
        self,
        staff_events: list[PdfStaffTimingEvent],
        tab_groups_by_bar: dict[tuple[int, int, int, int], list[CandidateXGroupDiagnostics]],
    ) -> PdfStaffTabAlignmentResult:
        result = PdfStaffTabAlignmentResult()

        # Group staff events by normalized bar key (using staff_pair_index as the third element)
        staff_by_bar = defaultdict(list)
        for ev in staff_events:
            key = self._alignment_bar_key(ev.page_index, ev.system_index, ev.staff_index, ev.local_bar_index)
            staff_by_bar[key].append(ev)

        # Group tab groups by normalized bar key (using staff_pair_index as the third element)
        normalized_tab_groups_by_bar = defaultdict(list)
        for original_key, groups in tab_groups_by_bar.items():
            p_idx, sys_idx, st_idx, bar_idx = original_key
            norm_key = self._alignment_bar_key(p_idx, sys_idx, st_idx, bar_idx)
            normalized_tab_groups_by_bar[norm_key].extend(groups)

        # Collect all unique bar keys
        all_bar_keys = set(staff_by_bar.keys()) | set(normalized_tab_groups_by_bar.keys())

        for bar_key in all_bar_keys:
            bar_staff_events = staff_by_bar[bar_key]
            bar_tab_groups = normalized_tab_groups_by_bar.get(bar_key, [])

            if not bar_staff_events:
                # No staff timing for this bar -> fallback timing
                result.bars_using_fallback_timing.append(bar_key)
                result.unmatched_tab_groups.extend(bar_tab_groups)
                continue

            result.bars_using_staff_timing.append(bar_key)

            # Map staff events to candidate TAB groups within tolerance
            staff_to_candidates: dict[PdfStaffTimingEvent, list[CandidateXGroupDiagnostics]] = {}
            for staff_ev in bar_staff_events:
                if staff_ev.is_rest:
                    # Rest events do not consume TAB groups
                    staff_to_candidates[staff_ev] = []
                    continue

                candidates = []
                for tab_grp in bar_tab_groups:
                    if abs(staff_ev.x - tab_grp.x) <= self.tolerance:
                        candidates.append(tab_grp)
                staff_to_candidates[staff_ev] = candidates

            # Identify ambiguous staff events (mapping to multiple TAB groups)
            ambiguous_staff = set()
            for staff_ev, candidates in staff_to_candidates.items():
                if len(candidates) > 1:
                    ambiguous_staff.add(staff_ev)
                    result.ambiguous_staff_events.append(staff_ev)

            # Map TAB groups back to staff events to check for reverse ambiguity (multiple staff events mapping to same TAB group)
            tab_to_staff: dict[int, list[PdfStaffTimingEvent]] = defaultdict(list)
            for staff_ev, candidates in staff_to_candidates.items():
                if staff_ev in ambiguous_staff:
                    continue
                for tab_grp in candidates:
                    tab_to_staff[id(tab_grp)].append(staff_ev)

            for tab_grp_id, mapped_staff in tab_to_staff.items():
                if len(mapped_staff) > 1:
                    # Multiple staff events map to the same TAB group -> all of them are ambiguous
                    for staff_ev in mapped_staff:
                        if staff_ev not in ambiguous_staff:
                            ambiguous_staff.add(staff_ev)
                            result.ambiguous_staff_events.append(staff_ev)

            # Build aligned pairs and unmatched lists
            aligned_tab_groups = set()
            for staff_ev in bar_staff_events:
                if staff_ev in ambiguous_staff:
                    continue

                if staff_ev.is_rest:
                    # Rests align as timing-only without consuming any TAB group
                    # We represent this in the aligned pairs as None or we just don't pair it.
                    # The test says: "rest appears in alignment result as timing-only/rest evidence".
                    # Let's include it in aligned_pairs with None for CandidateXGroupDiagnostics,
                    # or list it separately. Let's list it in aligned_pairs with a placeholder or None.
                    # Wait, to support tuple, we can define a special representation. Pydantic list of tuples
                    # allows None values in Tuple if we type it as tuple[PdfStaffTimingEvent, CandidateXGroupDiagnostics | None]
                    # Let's check: Pydantic type can be `list[tuple[PdfStaffTimingEvent, CandidateXGroupDiagnostics | None]]` or we can just pair it with a dummy group.
                    # But Python's `tuple[PdfStaffTimingEvent, CandidateXGroupDiagnostics]` can also accept a None-like representation.
                    # Let's type it as: `aligned_pairs: list[tuple[PdfStaffTimingEvent, CandidateXGroupDiagnostics | None]]`.
                    pass

            # Let's update `aligned_pairs` definition to allow None
            # Wait, let's look at CandidateXGroupDiagnostics | None. Pydantic fully supports this.
            # Let's construct aligned pairs.
            for staff_ev in bar_staff_events:
                if staff_ev in ambiguous_staff:
                    continue

                if staff_ev.is_rest:
                    result.aligned_pairs.append((staff_ev, None))
                    continue

                candidates = staff_to_candidates[staff_ev]
                if not candidates:
                    result.unmatched_staff_events.append(staff_ev)
                else:
                    tab_grp = candidates[0]
                    # Verify this tab_grp is not part of any ambiguity
                    if id(tab_grp) not in tab_to_staff or len(tab_to_staff[id(tab_grp)]) == 1:
                        result.aligned_pairs.append((staff_ev, tab_grp))
                        aligned_tab_groups.add(id(tab_grp))
                    else:
                        # Tab group is ambiguous, so staff_ev is also unmatched/ambiguous
                        result.unmatched_staff_events.append(staff_ev)

            # Collect unmatched TAB groups
            for tab_grp in bar_tab_groups:
                if id(tab_grp) not in aligned_tab_groups:
                    result.unmatched_tab_groups.append(tab_grp)

        return result
