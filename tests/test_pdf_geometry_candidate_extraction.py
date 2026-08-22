import re
from score2gp.pdf_staff_geometry import (
    LocalPrimitivesSummary,
    NotationStaffDiagnostics,
    NotationStaffGeometry,
)
from score2gp.pdf_geometry_candidate_extraction import extract_geometry_candidates
from score2gp.pdf_geometry_candidates import (
    GeometryCandidateSet,
    LeftMarginPrimitiveCandidate,
    PrimitiveEvidenceCandidate,
    XAlignedPrimitiveClusterCandidate,
)

def _diagnostics(
    *,
    left_margin_candidates: list[LeftMarginPrimitiveCandidate] | None = None,
    x_aligned_cluster_candidates: list[XAlignedPrimitiveClusterCandidate] | None = None,
) -> NotationStaffDiagnostics:
    return NotationStaffDiagnostics(
        staff=NotationStaffGeometry(
            page_index=1,
            system_index=1,
            staff_index=1,
            x0=50.0,
            y0=100.0,
            x1=500.0,
            y1=132.0,
            line_y_coords=[100.0, 108.0, 116.0, 124.0, 132.0],
        ),
        primitives=LocalPrimitivesSummary(
            line_count=5,
            curve_count=0,
            rect_count=0,
            text_span_count_by_font={},
        ),
        left_margin_candidates=left_margin_candidates,
        x_aligned_cluster_candidates=x_aligned_cluster_candidates,
    )

def test_extract_geometry_candidates_returns_empty_set_when_diagnostics_have_no_candidates():
    diagnostics = _diagnostics()
    result = extract_geometry_candidates(diagnostics)
    assert isinstance(result, GeometryCandidateSet)
    assert len(result.left_margin_primitives) == 0
    assert len(result.x_aligned_clusters) == 0

def test_extract_geometry_candidates_transfers_populated_diagnostic_candidates():
    left_margin_candidate = LeftMarginPrimitiveCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=55.0,
        y0=101.0,
        x1=62.0,
        y1=129.0,
        kind="vertical_stroke",
        source="left_margin",
    )
    cluster_primitive = PrimitiveEvidenceCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=200.0,
        y0=104.0,
        x1=204.0,
        y1=114.0,
        kind="rectangle",
        source="x_aligned_cluster",
    )
    cluster_candidate = XAlignedPrimitiveClusterCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=198.0,
        x1=204.0,
        primitive_count=1,
        primitives=[cluster_primitive],
    )

    result = extract_geometry_candidates(
        _diagnostics(
            left_margin_candidates=[left_margin_candidate],
            x_aligned_cluster_candidates=[cluster_candidate],
        )
    )

    assert result.left_margin_primitives == [left_margin_candidate]
    assert result.x_aligned_clusters == [cluster_candidate]
    assert result.model_dump(mode="json") == {
        "left_margin_primitives": [
            {
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "x0": 55.0,
                "y0": 101.0,
                "x1": 62.0,
                "y1": 129.0,
                "kind": "vertical_stroke",
                "source": "left_margin",
                "font_name": None,
                "font_size": None,
            }
        ],
        "sections": [],
        "repeats": [],
        "lyrics": [],
        "x_aligned_clusters": [
            {
                "page_index": 1,
                "system_index": 1,
                "staff_index": 1,
                "x0": 198.0,
                "x1": 204.0,
                "primitive_count": 1,
                "primitives": [
                    {
                        "page_index": 1,
                        "system_index": 1,
                        "staff_index": 1,
                        "x0": 200.0,
                        "y0": 104.0,
                        "x1": 204.0,
                        "y1": 114.0,
                        "kind": "rectangle",
                        "source": "x_aligned_cluster",
                        "font_name": None,
                        "font_size": None,
                    }
                ],
            }
        ],
    }

def test_geometry_candidate_set_schema_has_no_semantic_leakage():
    schema = GeometryCandidateSet.model_json_schema()
    schema_str = str(schema).lower()

    forbidden_words = [
        "notehead", "stem", "clef", "pitch", "duration",
        "voice", "chord", "key_signature", "time_signature",
        "beat", "rhythm"
    ]

    for word in forbidden_words:
        # use word boundaries to avoid matching "system" for "stem"
        pattern = r'\b' + word + r'\b'
        assert not re.search(pattern, schema_str), f"Semantic leakage detected: {word} found in GeometryCandidateSet schema"

import pytest
from score2gp.pdf_geometry_candidate_extraction import extract_rhythm_candidates, MissingRhythmGeometry
from score2gp.tabraw import TabCandidate
from score2gp.pdf_staff_geometry import StaffFlagBeamCandidateDiagnostics

def test_extract_rhythm_candidates_tablature_only():
    tab_candidates = [
        TabCandidate(id="t1", raw_text="0", x=100.0, y=110.0)
    ]
    diagnostics = _diagnostics()
    # It should return the candidates unmodified
    result = extract_rhythm_candidates(diagnostics, tab_candidates, is_tablature_only=True)
    assert result == tab_candidates
    assert "duration_evidence" not in result[0].raw

def test_extract_rhythm_candidates_refuses_when_noteheads_absent():
    tab_candidates = [
        TabCandidate(id="t1", raw_text="2", x=200.0, y=110.0)
    ]
    # Create a cluster with ONLY a stem (vertical stroke)
    stem_primitive = PrimitiveEvidenceCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=200.0,
        y0=100.0,
        x1=201.0,
        y1=120.0,
        kind="vertical_stroke",
        source="x_aligned_cluster",
    )
    cluster = XAlignedPrimitiveClusterCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=200.0,
        x1=201.0,
        primitive_count=1,
        primitives=[stem_primitive],
    )
    diagnostics = _diagnostics(x_aligned_cluster_candidates=[cluster])

    with pytest.raises(MissingRhythmGeometry):
        extract_rhythm_candidates(diagnostics, tab_candidates, is_tablature_only=False)

def test_extract_rhythm_candidates_assigns_duration():
    tab_candidates = [
        TabCandidate(id="t1", raw_text="3", x=300.0, y=110.0)
    ]
    # Cluster with stem and notehead (curve)
    stem_primitive = PrimitiveEvidenceCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=300.0,
        y0=100.0,
        x1=301.0,
        y1=120.0,
        kind="vertical_stroke",
        source="x_aligned_cluster",
    )
    notehead_primitive = PrimitiveEvidenceCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=296.0,
        y0=116.0,
        x1=300.0,
        y1=120.0,
        kind="curve",
        source="x_aligned_cluster",
    )
    cluster = XAlignedPrimitiveClusterCandidate(
        page_index=1,
        system_index=1,
        staff_index=1,
        x0=296.0,
        x1=301.0,
        primitive_count=2,
        primitives=[stem_primitive, notehead_primitive],
    )
    diagnostics = _diagnostics(x_aligned_cluster_candidates=[cluster])
    # Give it a flag to make it an eighth note
    diagnostics = diagnostics.model_copy(update={
            "flag_beam_candidates": StaffFlagBeamCandidateDiagnostics(
                flags=[
                    {"bbox": [301.0, 115.0, 305.0, 120.0], "primitive_kind": "curve", "width": 4.0, "height": 5.0}
                ],
                beams=[]
            )  })

    result = extract_rhythm_candidates(diagnostics, tab_candidates, is_tablature_only=False)
    assert len(result) == 1
    assert "duration_evidence" in result[0].raw
    assert result[0].raw["duration_evidence"]["duration_name"] == "eighth"

def test_extract_geometry_candidates_extracts_repeats_and_sections():
    # Thick left, thin right -> start repeat
    stroke_thick = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=100.0, y0=100.0, x1=103.0, y1=132.0, kind="vertical_stroke", source="x_aligned_cluster"
    )
    stroke_thin = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=105.0, y0=100.0, x1=105.5, y1=132.0, kind="vertical_stroke", source="x_aligned_cluster"
    )
    cluster = XAlignedPrimitiveClusterCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=100.0, x1=105.5, primitive_count=2, primitives=[stroke_thick, stroke_thin]
    )


    # End repeat
    stroke_thin_end = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=120.0, y0=100.0, x1=120.5, y1=132.0, kind="vertical_stroke", source="x_aligned_cluster"
    )
    stroke_thick_end = PrimitiveEvidenceCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=125.0, y0=100.0, x1=128.0, y1=132.0, kind="vertical_stroke", source="x_aligned_cluster"
    )
    cluster2 = XAlignedPrimitiveClusterCandidate(
        page_index=1, system_index=1, staff_index=1,
        x0=120.0, x1=128.0, primitive_count=2, primitives=[stroke_thin_end, stroke_thick_end]
    )

    # Section that falls back to lyric
    diag = _diagnostics(x_aligned_cluster_candidates=[cluster, cluster2])

    diag = diag.model_copy(update={
        "sections": [{
            "page_index": 1, "system_index": 1, "staff_index": 1,
            "x0": 50.0, "y0": 50.0, "x1": 80.0, "y1": 60.0,
            "text": "UnknownBold", "y_offset": 10.0, "is_bold": True
        }, {
            "page_index": 1, "system_index": 1, "staff_index": 1,
            "x0": 150.0, "y0": 50.0, "x1": 180.0, "y1": 60.0,
            "text": "Chorus", "y_offset": 10.0, "is_bold": True
        }]
    })

    result = extract_geometry_candidates(diag)
    assert len(result.repeats) == 2
    assert result.repeats[0].direction == "start"
    assert result.repeats[1].direction == "end"

    # One valid section (Chorus)
    assert len(result.sections) == 1
    assert result.sections[0].text == "Chorus"

    # One fallback lyric (UnknownBold)
    assert len(result.lyrics) == 1
    assert result.lyrics[0].text == "UnknownBold"

