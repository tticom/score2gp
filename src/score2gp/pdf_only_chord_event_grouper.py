from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .tabraw import TabCandidate


class CandidateXGroupDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    x_min: float
    x_max: float
    candidate_count: int
    candidate_ids: list[str] = Field(default_factory=list)
    strings: list[int] = Field(default_factory=list)
    is_chord_stack: bool = False


PDF_ONLY_CHORD_X_TOLERANCE_PT = 10.0


class PdfOnlyChordEventGrouper:
    """Groups TabRaw fret candidates within a source bar into sequential event subgroups.

    Handles x-tolerance grouping and duplicate-string splitting.
    """

    def __init__(self, tolerance: float = 10.0) -> None:
        self.tolerance = tolerance

    def group_bar_candidates(self, candidates: list[TabCandidate]) -> list[list[TabCandidate]]:
        """Groups candidate frets in a single source bar into event subgroups,
        preserving horizontal order and duplicate-string split safety.
        """
        # Group by x-position
        x_groups = self.candidate_x_groups(candidates)

        # Split duplicate strings to prevent false stacking
        id_to_cand = {c.id: c for c in candidates}
        event_subgroups = []
        for group_diag in x_groups:
            group_candidates = [id_to_cand[cid] for cid in group_diag.candidate_ids if cid in id_to_cand]
            if not group_candidates:
                continue
            split_groups = self.split_duplicate_strings(group_candidates)
            event_subgroups.extend(split_groups)

        return event_subgroups

    def candidate_x_groups(self, candidates: list[TabCandidate]) -> list[CandidateXGroupDiagnostics]:
        """Groups candidates by horizontal position within the given tolerance."""
        groups: list[list[TabCandidate]] = []
        for candidate in sorted(candidates, key=lambda item: (float("inf") if item.x is None else item.x, item.id)):
            if candidate.x is None:
                continue
            if groups and abs(float(candidate.x) - self._mean_x(groups[-1])) <= self.tolerance:
                groups[-1].append(candidate)
            else:
                groups.append([candidate])

        diagnostics = []
        for group in groups:
            xs = [float(candidate.x) for candidate in group if candidate.x is not None]
            strings = sorted({candidate.string for candidate in group if candidate.string is not None})
            diagnostics.append(
                CandidateXGroupDiagnostics(
                    x=round(sum(xs) / len(xs), 3),
                    x_min=round(min(xs), 3),
                    x_max=round(max(xs), 3),
                    candidate_count=len(group),
                    candidate_ids=[candidate.id for candidate in group],
                    strings=strings,
                    is_chord_stack=len(group) > 1 and len(strings) > 1,
                )
            )
        return diagnostics

    def split_duplicate_strings(self, candidates: list[TabCandidate]) -> list[list[TabCandidate]]:
        """Splits a list of candidates into subgroups to avoid duplicate string conflicts."""
        sorted_cands = sorted(candidates, key=lambda c: (c.x or 0.0, c.string or 0, c.id))
        subgroups = []
        current_subgroup = []
        current_strings = set()
        for c in sorted_cands:
            if c.string in current_strings:
                subgroups.append(current_subgroup)
                current_subgroup = [c]
                current_strings = {c.string} if c.string is not None else set()
            else:
                current_subgroup.append(c)
                if c.string is not None:
                    current_strings.add(c.string)
        if current_subgroup:
            subgroups.append(current_subgroup)
        return subgroups

    def _mean_x(self, group: list[TabCandidate]) -> float:
        xs = [float(c.x) for c in group if c.x is not None]
        return sum(xs) / len(xs) if xs else 0.0
