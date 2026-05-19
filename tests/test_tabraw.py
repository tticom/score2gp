from __future__ import annotations

import pytest
from pydantic import ValidationError

from score2gp.ir import SourceStage
from score2gp.tabraw import TabRaw, normalize_tabraw_payload, parse_fret_text


def test_tabraw_fixture_has_stable_candidate_ids_and_provenance() -> None:
    tabraw = TabRaw.from_json_file("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")

    assert [candidate.id for candidate in tabraw.candidates] == ["tab-001", "tab-002"]
    assert tabraw.candidates[0].string == 1
    assert tabraw.candidates[0].parsed_fret == 0

    provenance = tabraw.candidates[0].to_provenance()
    assert provenance.source_stage is SourceStage.PDF_TEXT
    assert provenance.page == 1
    assert provenance.bbox is not None
    assert provenance.bbox.x0 == 98.0
    assert provenance.raw_token_id == "tab-001"


def test_legacy_tabraw_items_are_normalized() -> None:
    normalized = normalize_tabraw_payload(
        {
            "source_pdf": "legacy.pdf",
            "inspection_kind": "born-digital",
            "items": [
                {
                    "page": 1,
                    "text": "12",
                    "bbox": [10, 20, 18, 28],
                    "confidence": 0.4,
                }
            ],
        }
    )
    tabraw = TabRaw.model_validate(normalized)

    assert tabraw.schema_version == "tabraw.v0.1"
    assert tabraw.candidates[0].id == "legacy-candidate-0001"
    assert tabraw.candidates[0].parsed_fret == 12
    assert tabraw.candidates[0].bbox is not None
    assert tabraw.candidates[0].x == 14.0


def test_tabraw_classifies_chord_and_technique_text_without_treating_them_as_frets() -> None:
    normalized = normalize_tabraw_payload(
        {
            "items": [
                {"id": "candidate-chord", "page": 1, "text": "E7", "bbox": [10, 20, 20, 30]},
                {"id": "candidate-tech", "page": 1, "text": "slide", "bbox": [30, 20, 50, 30]},
                {"id": "candidate-hammer", "page": 1, "text": "H", "bbox": [60, 20, 70, 30]},
            ]
        }
    )
    tabraw = TabRaw.model_validate(normalized)

    assert parse_fret_text("E7") is None
    assert [candidate.kind for candidate in tabraw.candidates] == ["chord-symbol", "technique-text", "technique-text"]
    assert [candidate.parsed_fret for candidate in tabraw.candidates] == [None, None, None]


def test_tabraw_rejects_duplicate_candidate_ids() -> None:
    with pytest.raises(ValidationError, match="candidate IDs must be unique"):
        TabRaw.model_validate(
            {
                "schema_version": "tabraw.v0.1",
                "candidates": [
                    {"id": "dup", "raw_text": "0", "parsed_fret": 0, "string": 1},
                    {"id": "dup", "raw_text": "2", "parsed_fret": 2, "string": 1},
                ],
            }
        )
