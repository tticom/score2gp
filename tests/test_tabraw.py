from __future__ import annotations

from score2gp.ir import SourceStage
from score2gp.tabraw import TabRaw, normalize_tabraw_payload


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
