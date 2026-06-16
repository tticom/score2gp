def test_extract_treble_clef_evidence_with_mocked_raster_diags(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence

    def mock_build_raster_notation_diagnostics(page, page_index, scale):
        return {
            "status": "success",
            "render_scale": 2.0,
            "staffs": [
                {
                    "staff_index": 1,
                    "raster_opening_symbol_candidate": {"bbox": [10.0, 20.0, 30.0, 40.0]},
                    "raster_opening_symbol_classification": {
                        "label": "treble_clef_candidate"
                    }
                },
                {
                    "staff_index": 2,
                    "raster_opening_symbol_candidate": {"bbox": [10.0, 120.0, 30.0, 140.0]},
                    "raster_opening_symbol_classification": {
                        "label": "unknown"
                    }
                }
            ]
        }

    monkeypatch.setattr(wnr, "build_raster_notation_diagnostics", mock_build_raster_notation_diagnostics, raising=False)
    import score2gp.pdf_raster_staff_diagnostics as rsd
    monkeypatch.setattr(rsd, "build_raster_notation_diagnostics", mock_build_raster_notation_diagnostics, raising=False)

    staves_diags = [
        {"staff": {"system_index": 1, "staff_index": 1}},
        {"staff": {"system_index": 1, "staff_index": 2}}
    ]

    # Providing a dummy page object to trigger the raster logic
    class DummyPage:
        pass

    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())

    assert len(cands) == 1
    assert cands[0]["candidate_id"] == "treble_001"
    assert cands[0]["staff_index"] == 1
    assert cands[0]["system_index"] == 1
    assert cands[0]["page_index"] == 1
    assert cands[0]["bbox"] == [5.0, 10.0, 15.0, 20.0]
    assert cands[0]["source"] == "raster_diagnostic_candidate_evidence"


def test_extract_treble_clef_evidence_missing_page():
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence
    staves_diags = [{"staff": {"system_index": 1, "staff_index": 1}}]
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1)
    assert cands == []

def test_extract_treble_clef_evidence_missing_staff_association(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence

    def mock_build_raster_notation_diagnostics(page, page_index, scale):
        return {
            "status": "success",
            "render_scale": 2.0,
            "staffs": [
                {
                    "staff_index": 2, # No geom staff with index 2
                    "raster_opening_symbol_candidate": {"bbox": [10.0, 20.0, 30.0, 40.0]},
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
        {"staff": {"system_index": 1, "staff_index": 1}},
    ]

    class DummyPage:
        pass

    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())

    assert cands == []
