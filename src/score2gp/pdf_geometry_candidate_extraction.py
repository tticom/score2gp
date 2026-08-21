from score2gp.pdf_staff_geometry import NotationStaffDiagnostics
from score2gp.pdf_geometry_candidates import GeometryCandidateSet
from score2gp.tabraw import TabCandidate
import dataclasses
from score2gp.pdf_tab_duration_associator import (
    StemPrimitiveCandidate,
    BeamPrimitiveCandidate,
    FlagPrimitiveCandidate,
    StaffSystemContext,
    SpatialBBox,
    associate_stems_to_events,
    resolve_tab_duration_evidence_for_events,
    AmbiguityDiagnostic,
)

class MissingRhythmGeometry(Exception):
    pass

def extract_geometry_candidates(diagnostics: NotationStaffDiagnostics) -> GeometryCandidateSet:
    """
    Extract geometry-only candidates from notation staff diagnostics.

    Candidate semantics are intentionally limited to geometry provenance:
    this function transfers already-computed diagnostic candidates into the
    page-level export shape without assigning musical meaning.
    """
    return GeometryCandidateSet(
        left_margin_primitives=list(diagnostics.left_margin_candidates or []),
        x_aligned_clusters=list(diagnostics.x_aligned_cluster_candidates or []),
    )

def extract_rhythm_candidates(
    diagnostics: NotationStaffDiagnostics,
    tab_candidates: list[TabCandidate],
    is_tablature_only: bool = False,
) -> list[TabCandidate]:
    """
    Extract geometric rhythm from standard staff and attach to TabCandidate events.
    """
    if is_tablature_only:
        return tab_candidates

    events_x = sorted(list({c.x for c in tab_candidates if c.x is not None}))
    if not events_x:
        return tab_candidates

    context = StaffSystemContext(
        line_y_coords=diagnostics.staff.line_y_coords,
    )

    stems = []
    stem_to_cluster = {}

    if diagnostics.x_aligned_cluster_candidates:
        for cluster in diagnostics.x_aligned_cluster_candidates:
            for p in cluster.primitives:
                if p.kind == "vertical_stroke":
                    stem_bbox = SpatialBBox(p.x0, p.y0, p.x1, p.y1)
                    stem_cand = StemPrimitiveCandidate(bbox=stem_bbox)
                    stems.append(stem_cand)
                    stem_to_cluster[id(stem_cand)] = cluster

    beams = []
    flags = []
    if diagnostics.flag_beam_candidates:
        for b in diagnostics.flag_beam_candidates.beams:
            beams.append(BeamPrimitiveCandidate(bbox=SpatialBBox(b.bbox[0], b.bbox[1], b.bbox[2], b.bbox[3])))
        # Deduplicate tiny flags (like triplet "3" curves) so they don't count twice for TAB rhythm
        merged_flags = []
        for f in diagnostics.flag_beam_candidates.flags:
            w = abs(f.bbox[2] - f.bbox[0])
            h = abs(f.bbox[3] - f.bbox[1])
            merged = False
            if w < 4.0 and h < 4.0:
                for m in merged_flags:
                    mw = abs(m[2] - m[0])
                    mh = abs(m[3] - m[1])
                    if mw < 4.0 and mh < 4.0 and abs(f.bbox[0] - m[0]) < 5.0 and abs(f.bbox[1] - m[1]) < 10.0:
                        m[0] = min(m[0], f.bbox[0])
                        m[1] = min(m[1], f.bbox[1])
                        m[2] = max(m[2], f.bbox[2])
                        m[3] = max(m[3], f.bbox[3])
                        merged = True
                        break
            if not merged:
                merged_flags.append([f.bbox[0], f.bbox[1], f.bbox[2], f.bbox[3]])

        for mf in merged_flags:
            flags.append(FlagPrimitiveCandidate(bbox=SpatialBBox(mf[0], mf[1], mf[2], mf[3])))


    # Before resolving full durations, check for MissingRhythmGeometry
    stem_assignments = associate_stems_to_events(events_x, stems, context)
    for ev_x in events_x:
        assigned = stem_assignments.get(ev_x)
        if isinstance(assigned, StemPrimitiveCandidate):
            cluster = stem_to_cluster.get(id(assigned))
            if cluster:
                # Check if there are any noteheads (non-strokes that are curves, text_spans)
                has_notehead = False
                for p in cluster.primitives:
                    if p.kind in ("curve", "text_span", "rectangle"):
                        has_notehead = True
                        break
                if not has_notehead:
                    raise MissingRhythmGeometry(f"Missing notehead for chord at x={ev_x}")

    durations = resolve_tab_duration_evidence_for_events(
        events_x=events_x,
        stems=stems,
        beams=beams,
        flags=flags,
        context=context,
        fail_on_ambiguity=False
    )

    result = []
    for cand in tab_candidates:
        if cand.x is not None and cand.x in durations:
            new_raw = dict(cand.raw)
            new_raw["duration_evidence"] = dataclasses.asdict(durations[cand.x])
            result.append(cand.model_copy(update={"raw": new_raw}))
        else:
            result.append(cand)

    return result
