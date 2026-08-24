from __future__ import annotations

import warnings
from collections import defaultdict

class IrregularStaffBoundsWarning(Warning):
    pass

from pydantic import BaseModel, Field

from .pdf_staff_timing import PdfStaffTimingEvent
from .pdf_only_chord_event_grouper import CandidateXGroupDiagnostics

PDF_STAFF_TAB_ALIGNMENT_X_TOLERANCE_PT = 15.0


PDF_SEVERELY_TRUNCATED_SYSTEM_WIDTH_PT = 50.0

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

        # Group staff events by system key: (page_index, system_index, staff_pair_index)
        staff_by_system = defaultdict(list)
        for ev in staff_events:
            pair_idx = self._alignment_bar_key(ev.page_index, ev.system_index, ev.staff_index, ev.local_bar_index)[2]
            key = (ev.page_index, ev.system_index, pair_idx)
            staff_by_system[key].append(ev)

        # Group tab groups by system key
        tab_groups_by_system = defaultdict(list)
        tab_bar_keys_by_system = defaultdict(set)
        for original_key, groups in tab_groups_by_bar.items():
            p_idx, sys_idx, st_idx, bar_idx = original_key
            norm_key = self._alignment_bar_key(p_idx, sys_idx, st_idx, bar_idx)
            sys_key = (norm_key[0], norm_key[1], norm_key[2])
            tab_groups_by_system[sys_key].extend(groups)
            tab_bar_keys_by_system[sys_key].add(norm_key)

        all_system_keys = set(staff_by_system.keys()) | set(tab_groups_by_system.keys())

        for sys_key in all_system_keys:
            sys_staff_events = staff_by_system[sys_key]
            sys_tab_groups = tab_groups_by_system.get(sys_key, [])
            
            # Detect severely truncated bounds (e.g. max_x - min_x < 50.0)
            if sys_tab_groups:
                xs = [g.x for g in sys_tab_groups]
                if len(xs) > 1 and max(xs) - min(xs) < PDF_SEVERELY_TRUNCATED_SYSTEM_WIDTH_PT:
                    warnings.warn("Severely truncated staff bounds detected.", IrregularStaffBoundsWarning)

            if not sys_staff_events:
                # No staff timing for this system -> fallback timing
                result.bars_using_fallback_timing.extend(list(tab_bar_keys_by_system.get(sys_key, set())))
                result.unmatched_tab_groups.extend(sys_tab_groups)
                continue

            # Extract bar keys
            staff_bar_keys = {self._alignment_bar_key(ev.page_index, ev.system_index, ev.staff_index, ev.local_bar_index) for ev in sys_staff_events}
            tab_bar_keys = tab_bar_keys_by_system.get(sys_key, set())
            
            # Determine if evidence implies irregular groupings (differing local_bar_indexes)
            staff_bar_indices = {k[3] for k in staff_bar_keys}
            tab_bar_indices = {k[3] for k in tab_bar_keys}
            is_irregular = False
            if staff_bar_indices and tab_bar_indices:
                if len(staff_bar_indices) > 1 or len(tab_bar_indices) > 1:
                    if staff_bar_indices != tab_bar_indices:
                        is_irregular = True
                elif len(staff_bar_indices) != len(tab_bar_indices):
                    is_irregular = True
                elif len(staff_bar_indices) != len(tab_bar_indices):
                    is_irregular = True

            result.bars_using_staff_timing.extend(list(staff_bar_keys | tab_bar_keys))

            # Map staff events to candidate TAB groups within tolerance
            staff_to_candidates: dict[PdfStaffTimingEvent, list[CandidateXGroupDiagnostics]] = {}
            for staff_ev in sys_staff_events:
                if staff_ev.is_rest:
                    staff_to_candidates[staff_ev] = []
                    continue

                candidates = []
                for tab_grp in sys_tab_groups:
                    # If not irregular, enforce local_bar_index matching (bar identity)
                    if not is_irregular:
                        # We need to find the local_bar_index of this tab_grp
                        # tab_grp itself doesn't have local_bar_index, we must find it from tab_groups_by_bar
                        # But wait, tab_grp is just an object. We can check which bar it came from!
                        # The easiest way is to re-fetch from tab_groups_by_bar.
                        matched_bar = False
                        for original_key, groups in tab_groups_by_bar.items():
                            if tab_grp in groups:
                                p_idx, sys_idx, st_idx, bar_idx = original_key
                                norm_key = self._alignment_bar_key(p_idx, sys_idx, st_idx, bar_idx)
                                if norm_key[3] == staff_ev.local_bar_index:
                                    matched_bar = True
                                    break
                        if not matched_bar:
                            continue
                            
                    if abs(staff_ev.x - tab_grp.x) <= self.tolerance:
                        candidates.append(tab_grp)
                staff_to_candidates[staff_ev] = candidates

            # Identify ambiguous staff events
            ambiguous_staff = set()
            for staff_ev, candidates in staff_to_candidates.items():
                if len(candidates) > 1:
                    ambiguous_staff.add(staff_ev)
                    result.ambiguous_staff_events.append(staff_ev)

            # Map TAB groups back to staff events to check reverse ambiguity
            tab_to_staff: dict[int, list[PdfStaffTimingEvent]] = defaultdict(list)
            for staff_ev, candidates in staff_to_candidates.items():
                if staff_ev in ambiguous_staff:
                    continue
                for tab_grp in candidates:
                    tab_to_staff[id(tab_grp)].append(staff_ev)

            for tab_grp_id, mapped_staff in tab_to_staff.items():
                if len(mapped_staff) > 1:
                    for staff_ev in mapped_staff:
                        if staff_ev not in ambiguous_staff:
                            ambiguous_staff.add(staff_ev)
                            result.ambiguous_staff_events.append(staff_ev)

            # Build aligned pairs and unmatched lists
            aligned_tab_groups = set()
            for staff_ev in sys_staff_events:
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
                    if id(tab_grp) not in tab_to_staff or len(tab_to_staff[id(tab_grp)]) == 1:
                        result.aligned_pairs.append((staff_ev, tab_grp))
                        aligned_tab_groups.add(id(tab_grp))
                    else:
                        result.unmatched_staff_events.append(staff_ev)

            # Collect unmatched TAB groups
            for tab_grp in sys_tab_groups:
                if id(tab_grp) not in aligned_tab_groups:
                    result.unmatched_tab_groups.append(tab_grp)

        return result
