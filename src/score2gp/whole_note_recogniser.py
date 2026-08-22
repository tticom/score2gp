from .notation_omr.evidence import shape_candidate_evidence
from .notation_omr.staff_geometry import (
    _associate_staves,
    map_ledger_line_candidates_to_read_only_outcomes,
    map_ledger_lines_to_note_candidates,
    map_staff_geometry_to_read_only_report,
    shape_ledger_line_candidate_evidence,
)
from .notation_omr.clef import (
    build_clef_resolved_pitch_coverage_report,
    extract_treble_clef_candidate_evidence,
    map_treble_clef_candidates_to_read_only_outcomes,
)
from .notation_omr.pitch import (
    map_assumed_treble_pitch_to_read_only_outcomes,
    map_clef_resolved_staff_pitch,
    map_staff_position_to_read_only_outcomes,
)
from .notation_omr.notehead import (
    map_half_note_candidates_to_read_only_outcomes,
    map_left_margin_candidates_to_read_only_outcomes,
    map_quarter_note_candidates_to_read_only_outcomes,
    map_whole_note_candidates_to_intermediate_notes,
    map_whole_note_candidates_to_read_only_outcomes,
    map_x_aligned_cluster_candidates_to_read_only_outcomes,
    shape_half_note_candidate_evidence,
    shape_left_margin_candidate_evidence,
    shape_quarter_note_candidate_evidence,
    shape_whole_note_candidate_evidence,
    shape_x_aligned_cluster_candidate_evidence,
)
from .notation_omr.duration import (
    compose_filled_duration_candidates,
    map_beam_candidates_to_read_only_outcomes,
    map_flag_candidates_to_read_only_outcomes,
    shape_beam_candidate_evidence,
    shape_flag_candidate_evidence,
)
from .notation_omr.timeline import build_staff_timeline_preview
from .notation_omr.pipeline import run_recognition_on_file

from typing import Any, Iterable
