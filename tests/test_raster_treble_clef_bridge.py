def test_extract_treble_clef_evidence_deterministic(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence

    def mock_build_raster_notation_diagnostics(page, page_index, scale):
        return {
            "status": "success",
            "render_scale": 2.0,
            "staffs": [
                {
                    "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                    "raster_opening_symbol_candidate": {"bbox": [10.0, 400.0, 30.0, 440.0]},
                    "raster_opening_symbol_classification": {
                        "label": "treble_clef_candidate"
                    }
                }
            ]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build_raster_notation_diagnostics, raising=False)
    import score2gp.pdf_raster_staff_diagnostics as rsd
    monkeypatch.setattr(rsd, "build_raster_notation_diagnostics", mock_build_raster_notation_diagnostics, raising=False)

    staves_diags = [
        {"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}
    ]

    class DummyPage: pass

    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert len(cands) == 1
    assert cands[0]["bbox"] == [5.0, 200.0, 15.0, 220.0]

def test_extract_treble_clef_evidence_missing_page():
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}]
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1)
    assert cands == []

def test_extract_treble_clef_evidence_raster_failure(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale): return {"status": "failed"}
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_missing_raster_staff(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale): return {"status": "success", "render_scale": 2.0}
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_missing_geom_association(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale):
        return {
            "status": "success", "render_scale": 2.0,
            "staffs": [{
                "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                "raster_opening_symbol_candidate": {"bbox": [10.0, 400.0, 30.0, 440.0]},
                "raster_opening_symbol_classification": {"label": "treble_clef_candidate"}
            }]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [] # No geom staves
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_ambiguous_geom_association(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale):
        return {
            "status": "success", "render_scale": 2.0,
            "staffs": [{
                "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                "raster_opening_symbol_candidate": {"bbox": [10.0, 400.0, 30.0, 440.0]},
                "raster_opening_symbol_classification": {"label": "treble_clef_candidate"}
            }]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [
        {"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}},
        {"staff": {"system_index": 1, "staff_index": 2, "y0": 205.0, "y1": 225.0}} # Both match within 10 pts
    ]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_ambiguous_raster_association(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale):
        return {
            "status": "success", "render_scale": 2.0,
            "staffs": [
                {
                    "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                    "raster_opening_symbol_candidate": {"bbox": [10.0, 400.0, 30.0, 440.0]},
                    "raster_opening_symbol_classification": {"label": "treble_clef_candidate"}
                },
                {
                    "y_coords": [405.0, 415.0, 425.0, 435.0, 445.0],
                    "raster_opening_symbol_candidate": {"bbox": [15.0, 405.0, 35.0, 445.0]},
                    "raster_opening_symbol_classification": {"label": "treble_clef_candidate"}
                }
            ]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [
        {"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}
    ]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_malformed_bbox(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale):
        return {
            "status": "success", "render_scale": 2.0,
            "staffs": [{
                "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                "raster_opening_symbol_candidate": {"bbox": "malformed"},
                "raster_opening_symbol_classification": {"label": "treble_clef_candidate"}
            }]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_wrong_length_bbox(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale):
        return {
            "status": "success", "render_scale": 2.0,
            "staffs": [{
                "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                "raster_opening_symbol_candidate": {"bbox": [10.0, 400.0, 30.0]},
                "raster_opening_symbol_classification": {"label": "treble_clef_candidate"}
            }]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_non_numeric_bbox(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale):
        return {
            "status": "success", "render_scale": 2.0,
            "staffs": [{
                "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                "raster_opening_symbol_candidate": {"bbox": [10.0, "forty", 30.0, 440.0]},
                "raster_opening_symbol_classification": {"label": "treble_clef_candidate"}
            }]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_missing_render_scale(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale):
        return {
            "status": "success",
            "staffs": [{
                "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                "raster_opening_symbol_candidate": {"bbox": [10.0, 400.0, 30.0, 440.0]},
                "raster_opening_symbol_classification": {"label": "treble_clef_candidate"}
            }]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_zero_render_scale(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale):
        return {
            "status": "success", "render_scale": 0.0,
            "staffs": [{
                "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                "raster_opening_symbol_candidate": {"bbox": [10.0, 400.0, 30.0, 440.0]},
                "raster_opening_symbol_classification": {"label": "treble_clef_candidate"}
            }]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []

def test_extract_treble_clef_evidence_non_treble_classification(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    def mock_build(p, pi, scale):
        return {
            "status": "success", "render_scale": 2.0,
            "staffs": [{
                "y_coords": [400.0, 410.0, 420.0, 430.0, 440.0],
                "raster_opening_symbol_candidate": {"bbox": [10.0, 400.0, 30.0, 440.0]},
                "raster_opening_symbol_classification": {"label": "unknown"}
            }]
        }
    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build, raising=False)
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1, "y0": 200.0, "y1": 220.0}}]
    class DummyPage: pass
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())
    assert cands == []
