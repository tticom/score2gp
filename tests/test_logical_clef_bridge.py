def test_logical_clef_candidate_bridge():
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence

    # Staff spacing = 10 (height 40)
    # Clef height needs to be >= 35, width >= 15, and height > staff_height * 1.2
    # So height 50, width 20 matches.
    staves_diags = [
        {
            "staff": {
                "system_index": 1,
                "staff_index": 1,
                "y0": 200.0,
                "y1": 240.0,
                "x0": 50.0,
                "line_y_coords": [200.0, 210.0, 220.0, 230.0, 240.0]
            },
            "left_margin_candidates": [
                {
                    "page_index": 1,
                    "system_index": 1,
                    "staff_index": 1,
                    "x0": 50.0,
                    "y0": 190.0,
                    "x1": 70.0,
                    "y1": 240.0,
                    "kind": "curve",
                    "source": "left_margin"
                }
            ]
        }
    ]

    class DummyPage: pass

    # Call with a dummy page (so raster might fail or return nothing mocked)
    # We don't mock raster here, so if it fails, it returns empty raster staffs
    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())

    assert len(cands) == 1
    assert cands[0]["source"] == "logical_diagnostic_candidate_evidence"
    assert cands[0]["bbox"] == [50.0, 190.0, 70.0, 240.0]
    assert cands[0]["candidate_id"] == "treble_001"

def test_unified_clef_candidate_bridge(monkeypatch):
    import score2gp.whole_note_recogniser as wnr
    from score2gp.whole_note_recogniser import extract_treble_clef_candidate_evidence

    def mock_build_raster_notation_diagnostics(page, page_index, scale):
        return {
            "status": "success",
            "render_scale": 1.0,
            "staffs": [
                {
                    "y_coords": [200.0, 210.0, 220.0, 230.0, 240.0],
                    "raster_opening_symbol_candidate": {"bbox": [50.0, 190.0, 70.0, 240.0]},
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
        {
            "staff": {
                "system_index": 1,
                "staff_index": 1,
                "y0": 200.0,
                "y1": 240.0,
                "x0": 50.0,
                "line_y_coords": [200.0, 210.0, 220.0, 230.0, 240.0]
            },
            "left_margin_candidates": [
                {
                    "page_index": 1,
                    "system_index": 1,
                    "staff_index": 1,
                    "x0": 50.0,
                    "y0": 190.0,
                    "x1": 70.0,
                    "y1": 240.0,
                    "kind": "curve",
                    "source": "left_margin"
                }
            ]
        }
    ]

    class DummyPage: pass

    cands = extract_treble_clef_candidate_evidence(staves_diags, page_index=1, start_index=1, page=DummyPage())

    assert len(cands) == 1
    assert cands[0]["source"] == "unified_diagnostic_candidate_evidence"
    # Raster bbox and logical bbox are same here
    assert cands[0]["bbox"] == [50.0, 190.0, 70.0, 240.0]
