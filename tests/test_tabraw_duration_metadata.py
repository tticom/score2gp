from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import pytest

from score2gp.pdf_tab_duration_types import TabDurationEvidence
from score2gp.tabraw import TabCandidate, TabRaw, make_tab_candidate, normalize_tabraw_payload


def test_direct_construction_with_dataclass_and_helper_access():
    evidence = TabDurationEvidence(
        duration_name="eighth",
        duration_ticks=480,
        stem_present=True,
        beam_count=1,
        flag_count=0,
        confidence=1.0,
        source="visual_morphology",
        is_ambiguous=False,
        is_fallback_placeholder=False,
        diagnostic_message="",
    )

    candidate = make_tab_candidate(
        candidate_id="cand-001",
        raw_text="5",
        page_index=1,
        bbox_values=[10.0, 20.0, 30.0, 40.0],
        confidence=0.9,
        duration_evidence=evidence,
    )

    assert candidate.raw["duration_evidence"] == asdict(evidence)
    assert candidate.duration_evidence == evidence
    assert candidate.duration_evidence.duration_name == "eighth"
    assert candidate.duration_evidence.duration_ticks == 480
    assert candidate.duration_evidence.stem_present is True
    assert candidate.duration_evidence.beam_count == 1


def test_direct_construction_with_valid_dict():
    evidence_dict = {
        "duration_name": "16th",
        "duration_ticks": 240,
        "stem_present": True,
        "beam_count": 2,
        "flag_count": 0,
        "confidence": 0.8,
        "source": "visual_morphology",
        "is_ambiguous": False,
        "is_fallback_placeholder": False,
        "diagnostic_message": "2 beams detected",
    }

    candidate = make_tab_candidate(
        candidate_id="cand-002",
        raw_text="3",
        page_index=1,
        bbox_values=[10.0, 20.0, 30.0, 40.0],
        confidence=0.9,
        duration_evidence=evidence_dict,
    )

    assert candidate.duration_evidence is not None
    assert candidate.duration_evidence.duration_name == "16th"
    assert candidate.duration_evidence.duration_ticks == 240
    assert candidate.duration_evidence.beam_count == 2
    assert candidate.duration_evidence.diagnostic_message == "2 beams detected"


def test_direct_construction_with_raw_dict_containing_duration_evidence():
    evidence = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        stem_present=True,
    )
    raw_dict = {"custom_field": "val", "duration_evidence": evidence}

    candidate = make_tab_candidate(
        candidate_id="cand-003",
        raw_text="0",
        page_index=1,
        bbox_values=[5.0, 5.0, 15.0, 15.0],
        confidence=1.0,
        raw=raw_dict,
    )

    assert candidate.raw["custom_field"] == "val"
    assert candidate.duration_evidence == evidence


def test_json_serialization_and_deserialization(tmp_path: Path):
    ev1 = TabDurationEvidence(duration_name="quarter", duration_ticks=960, stem_present=True)
    ev2 = TabDurationEvidence(
        duration_name="quarter",
        duration_ticks=960,
        source="equal_spacing_fallback",
        is_fallback_placeholder=True,
    )

    cand1 = make_tab_candidate(
        candidate_id="c1",
        raw_text="7",
        page_index=1,
        bbox_values=[10.0, 10.0, 20.0, 20.0],
        confidence=0.9,
        duration_evidence=ev1,
    )
    cand2 = make_tab_candidate(
        candidate_id="c2",
        raw_text="8",
        page_index=1,
        bbox_values=[30.0, 10.0, 40.0, 20.0],
        confidence=0.8,
        duration_evidence=ev2,
    )

    tabraw = TabRaw(source_pdf="test.pdf", candidates=[cand1, cand2])

    json_file = tmp_path / "tabraw_test.json"
    tabraw.to_json_file(json_file)

    loaded_tabraw = TabRaw.from_json_file(json_file)

    assert len(loaded_tabraw.candidates) == 2
    assert loaded_tabraw.candidates[0].duration_evidence == ev1
    assert loaded_tabraw.candidates[1].duration_evidence == ev2

    # Verify model_dump_json round-trip
    json_str = tabraw.model_dump_json()
    reloaded = TabRaw.model_validate_json(json_str)
    assert reloaded.candidates[0].duration_evidence == ev1
    assert reloaded.candidates[1].duration_evidence == ev2


def test_legacy_and_dict_payload_normalization():
    legacy_payload = {
        "source_pdf": "legacy.pdf",
        "items": [
            {
                "id": "leg-1",
                "page": 1,
                "text": "5",
                "bbox": [10.0, 10.0, 20.0, 20.0],
                "duration_evidence": {
                    "duration_name": "eighth",
                    "duration_ticks": 480,
                    "stem_present": True,
                    "beam_count": 1,
                },
            },
            {
                "id": "leg-2",
                "page": 1,
                "text": "7",
                "bbox": [30.0, 10.0, 40.0, 20.0],
                "raw": {
                    "duration_evidence": {
                        "duration_name": "32nd",
                        "duration_ticks": 120,
                        "stem_present": True,
                        "beam_count": 3,
                    }
                },
            },
        ],
    }

    normalized = normalize_tabraw_payload(legacy_payload)
    tabraw = TabRaw.model_validate(normalized)

    assert len(tabraw.candidates) == 2
    assert tabraw.candidates[0].duration_evidence is not None
    assert tabraw.candidates[0].duration_evidence.duration_name == "eighth"
    assert tabraw.candidates[0].duration_evidence.duration_ticks == 480

    assert tabraw.candidates[1].duration_evidence is not None
    assert tabraw.candidates[1].duration_evidence.duration_name == "32nd"
    assert tabraw.candidates[1].duration_evidence.beam_count == 3


def test_malformed_evidence_boundary():
    # 1. Invalid duration_name
    with pytest.raises(ValueError, match="Invalid duration_evidence"):
        make_tab_candidate(
            candidate_id="err-1",
            raw_text="1",
            page_index=1,
            bbox_values=[0, 0, 10, 10],
            confidence=0.5,
            duration_evidence={"duration_name": "invalid_name", "duration_ticks": 480},
        )

    # 2. Negative duration_ticks
    with pytest.raises(ValueError, match="Invalid duration_evidence"):
        make_tab_candidate(
            candidate_id="err-2",
            raw_text="1",
            page_index=1,
            bbox_values=[0, 0, 10, 10],
            confidence=0.5,
            duration_evidence={"duration_name": "eighth", "duration_ticks": -100},
        )

    # 3. Invalid type for duration_evidence
    with pytest.raises(TypeError, match="duration_evidence must be TabDurationEvidence or dict"):
        make_tab_candidate(
            candidate_id="err-3",
            raw_text="1",
            page_index=1,
            bbox_values=[0, 0, 10, 10],
            confidence=0.5,
            duration_evidence=12345,  # type: ignore[arg-type]
        )

    # 4. Property returns None gracefully when TabCandidate holds malformed raw metadata
    malformed_candidate = TabCandidate(
        id="mal-1",
        raw_text="1",
        raw={"duration_evidence": {"duration_name": "quarter", "duration_ticks": -50}},
    )
    assert malformed_candidate.duration_evidence is None

    malformed_candidate_unknown_field = TabCandidate(
        id="mal-2",
        raw_text="1",
        raw={"duration_evidence": {"duration_name": "quarter", "duration_ticks": 960, "unexpected": True}},
    )
    assert malformed_candidate_unknown_field.duration_evidence is None

    malformed_candidate_bad_type = TabCandidate(
        id="mal-3",
        raw_text="1",
        raw={"duration_evidence": "not_a_dict_or_dataclass"},
    )
    assert malformed_candidate_bad_type.duration_evidence is None


def test_malformed_dataclass_evidence_boundary():
    # Invalid duration_name in dataclass instance
    bad_name_ev = TabDurationEvidence(duration_name="bogus", duration_ticks=480)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Invalid duration_evidence"):
        make_tab_candidate(
            candidate_id="dc-err-1",
            raw_text="1",
            page_index=1,
            bbox_values=[0, 0, 10, 10],
            confidence=0.5,
            duration_evidence=bad_name_ev,
        )

    # Negative duration_ticks in dataclass instance
    neg_ticks_ev = TabDurationEvidence(duration_name="eighth", duration_ticks=-1)
    with pytest.raises(ValueError, match="Invalid duration_evidence"):
        make_tab_candidate(
            candidate_id="dc-err-2",
            raw_text="1",
            page_index=1,
            bbox_values=[0, 0, 10, 10],
            confidence=0.5,
            duration_evidence=neg_ticks_ev,
        )

    # Out-of-range confidence (> 1.0) in dataclass instance
    bad_conf_ev = TabDurationEvidence(duration_name="quarter", duration_ticks=960, confidence=2.0)
    with pytest.raises(ValueError, match="Invalid duration_evidence"):
        make_tab_candidate(
            candidate_id="dc-err-3",
            raw_text="1",
            page_index=1,
            bbox_values=[0, 0, 10, 10],
            confidence=0.5,
            duration_evidence=bad_conf_ev,
        )

    # Invalid source in dataclass instance
    bad_src_ev = TabDurationEvidence(duration_name="quarter", duration_ticks=960, source="unknown_source")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Invalid duration_evidence"):
        make_tab_candidate(
            candidate_id="dc-err-4",
            raw_text="1",
            page_index=1,
            bbox_values=[0, 0, 10, 10],
            confidence=0.5,
            duration_evidence=bad_src_ev,
        )

    # Dataclass instance in raw dict parameter fails validation in make_tab_candidate
    with pytest.raises(ValueError, match="Invalid duration_evidence in raw metadata"):
        make_tab_candidate(
            candidate_id="dc-err-5",
            raw_text="1",
            page_index=1,
            bbox_values=[0, 0, 10, 10],
            confidence=0.5,
            raw={"duration_evidence": neg_ticks_ev},
        )

    # Direct TabCandidate construction holding invalid dataclass instance returns None via duration_evidence property
    cand_with_bad_dc = TabCandidate(
        id="dc-mal-1",
        raw_text="1",
        raw={"duration_evidence": bad_name_ev},
    )
    assert cand_with_bad_dc.duration_evidence is None


def test_absent_duration_evidence():
    candidate = make_tab_candidate(
        candidate_id="plain-1",
        raw_text="2",
        page_index=1,
        bbox_values=[0, 0, 10, 10],
        confidence=0.5,
    )
    assert candidate.duration_evidence is None

