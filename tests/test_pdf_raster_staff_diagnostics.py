from __future__ import annotations

import pytest
import fitz  # type: ignore[import-not-found]
from pathlib import Path

from score2gp.pdf_raster_staff_diagnostics import build_raster_notation_diagnostics


@pytest.fixture
def treble_staff_paper_path() -> Path:
    return Path("fixtures/private/raster-treble-clef/treble-staff-paper.pdf")


@pytest.fixture
def flash_cards_path() -> Path:
    return Path("fixtures/private/raster-treble-clef/FlashCardsValues.pdf")


def test_build_raster_notation_diagnostics_on_treble_staff_paper(treble_staff_paper_path: Path):
    assert treble_staff_paper_path.exists(), f"Required fixture {treble_staff_paper_path} is missing."

    doc = fitz.open(treble_staff_paper_path)
    page = doc[0]

    diags = build_raster_notation_diagnostics(page, page_index=1, scale=2.0)

    assert diags["status"] == "success"
    staffs = diags["staffs"]
    assert len(staffs) >= 1

    # Check the first staff group has an opening symbol candidate
    first_staff = staffs[0]
    assert len(first_staff["y_coords"]) == 5
    assert first_staff["raster_opening_symbol_candidate"] is not None

    cand = first_staff["raster_opening_symbol_candidate"]
    assert cand["kind"] == "raster_opening_symbol_candidate"
    assert cand["width"] >= first_staff["spacing"] * 1.5
    
    staff_height = first_staff["y_coords"][4] - first_staff["y_coords"][0]
    # Verify the candidate is not just staff lines: a treble clef is taller than the staff itself.
    assert cand["height"] > staff_height
    assert cand["height"] >= first_staff["spacing"] * 3.5

    # The candidate should be near the left margin
    x0 = cand["bbox"][0]
    staff_x0 = first_staff["x0"]
    assert x0 >= staff_x0 - 20  # Roughly inside or slightly left of the left margin

    # Check classifier output
    assert "raster_opening_symbol_classification" in first_staff
    cls = first_staff["raster_opening_symbol_classification"]
    assert cls["kind"] == "treble_clef_candidate_classifier"
    assert cls["label"] in ("treble_clef_candidate", "unknown")
    assert "reason" in cls
    assert "features" in cls
    assert "score_ir" not in first_staff
    assert "clef" not in first_staff


def test_build_raster_notation_diagnostics_on_flash_cards(flash_cards_path: Path):
    assert flash_cards_path.exists(), f"Required fixture {flash_cards_path} is missing."

    doc = fitz.open(flash_cards_path)
    page = doc[0]

    diags = build_raster_notation_diagnostics(page, page_index=1, scale=2.0)

    assert diags["status"] == "success"
    staffs = diags["staffs"]
    assert len(staffs) >= 1

    first_staff = staffs[0]
    assert len(first_staff["y_coords"]) == 5
    assert first_staff["raster_opening_symbol_candidate"] is not None

    cand = first_staff["raster_opening_symbol_candidate"]
    assert cand["kind"] == "raster_opening_symbol_candidate"
    assert cand["width"] >= first_staff["spacing"] * 1.5
    
    staff_height = first_staff["y_coords"][4] - first_staff["y_coords"][0]
    # Verify the candidate is not just staff lines: a treble clef is taller than the staff itself.
    assert cand["height"] > staff_height
    assert cand["height"] >= first_staff["spacing"] * 3.5

    # Check classifier output
    assert "raster_opening_symbol_classification" in first_staff
    cls = first_staff["raster_opening_symbol_classification"]
    assert cls["kind"] == "treble_clef_candidate_classifier"
    assert cls["label"] in ("treble_clef_candidate", "unknown")
    assert "reason" in cls
    assert "features" in cls
    assert "score_ir" not in first_staff
    assert "clef" not in first_staff


def test_classify_raster_opening_symbol_missing_candidate():
    from score2gp.pdf_raster_staff_diagnostics import classify_raster_opening_symbol_candidate
    staff = {
        "staff_index": 1,
        "y_coords": [10.0, 20.0, 30.0, 40.0, 50.0],
        "x0": 10.0,
        "spacing": 10.0,
        # missing candidate
    }
    result = classify_raster_opening_symbol_candidate(staff)
    assert result["kind"] == "treble_clef_candidate_classifier"
    assert result["label"] == "unknown"
    assert "reason" in result


def test_classify_raster_opening_symbol_insufficient_evidence():
    from score2gp.pdf_raster_staff_diagnostics import classify_raster_opening_symbol_candidate
    staff = {
        "staff_index": 1,
        "y_coords": [10.0, 20.0, 30.0, 40.0, 50.0],
        "x0": 10.0,
        "spacing": 10.0,
        "raster_opening_symbol_candidate": {
            "bbox": [10.0, 10.0, 20.0, 20.0],
            "width": 10.0,
            "height": 10.0 # Height is only 1x spacing, not a treble clef
        }
    }
    result = classify_raster_opening_symbol_candidate(staff)
    assert result["kind"] == "treble_clef_candidate_classifier"
    assert result["label"] == "unknown"
    assert "reason" in result
    assert result["features"]["height_to_spacing"] == 1.0


def test_classify_raster_opening_symbol_malformed_bbox():
    from score2gp.pdf_raster_staff_diagnostics import classify_raster_opening_symbol_candidate
    staff = {
        "staff_index": 1,
        "y_coords": [10.0, 20.0, 30.0, 40.0, 50.0],
        "x0": 10.0,
        "spacing": 10.0,
        "raster_opening_symbol_candidate": {
            "bbox": [10.0, 20.0],  # malformed bbox (only 2 elements)
            "width": 10.0,
            "height": 40.0
        }
    }
    result = classify_raster_opening_symbol_candidate(staff)
    assert result["kind"] == "treble_clef_candidate_classifier"
    assert result["label"] == "unknown"
    assert "Malformed candidate bbox" in result["reason"]


def test_classify_raster_opening_symbol_non_dict_candidate():
    from score2gp.pdf_raster_staff_diagnostics import classify_raster_opening_symbol_candidate
    staff = {
        "staff_index": 1,
        "y_coords": [10.0, 20.0, 30.0, 40.0, 50.0],
        "x0": 10.0,
        "spacing": 10.0,
        "raster_opening_symbol_candidate": "not a dict"
    }
    result = classify_raster_opening_symbol_candidate(staff)
    assert result["kind"] == "treble_clef_candidate_classifier"
    assert result["label"] == "unknown"
    assert "Malformed candidate: not a dict" in result["reason"]


def test_classify_raster_opening_symbol_non_numeric_dimensions():
    from score2gp.pdf_raster_staff_diagnostics import classify_raster_opening_symbol_candidate
    staff = {
        "staff_index": 1,
        "y_coords": [10.0, 20.0, 30.0, 40.0, 50.0],
        "x0": 10.0,
        "spacing": 10.0,
        "raster_opening_symbol_candidate": {
            "bbox": [10.0, 10.0, 20.0, 20.0],
            "width": "10.0", # not numeric
            "height": 40.0
        }
    }
    result = classify_raster_opening_symbol_candidate(staff)
    assert result["kind"] == "treble_clef_candidate_classifier"
    assert result["label"] == "unknown"
    assert "Malformed candidate dimensions" in result["reason"]


def test_classify_raster_opening_symbol_staff_lines_only():
    from score2gp.pdf_raster_staff_diagnostics import classify_raster_opening_symbol_candidate
    staff = {
        "staff_index": 1,
        "y_coords": [10.0, 20.0, 30.0, 40.0, 50.0],
        "x0": 10.0,
        "spacing": 10.0,
        "raster_opening_symbol_candidate": {
            "bbox": [10.0, 9.0, 30.0, 51.0],
            "width": 20.0,
            "height": 42.0 # Height is slightly more than staff_height (40.0) but not a full clef
        }
    }
    result = classify_raster_opening_symbol_candidate(staff)
    assert result["kind"] == "treble_clef_candidate_classifier"
    assert result["label"] == "unknown"
    assert result["features"]["height_to_staff_height"] == 1.05


def test_summarize_raster_treble_clef_diagnostics_on_treble_staff_paper(treble_staff_paper_path: Path):
    from score2gp.pdf_raster_staff_diagnostics import summarize_raster_treble_clef_diagnostics
    assert treble_staff_paper_path.exists(), f"Required fixture {treble_staff_paper_path} is missing."

    doc = fitz.open(treble_staff_paper_path)
    page = doc[0]

    diags = build_raster_notation_diagnostics(page, page_index=1, scale=2.0)
    summary = summarize_raster_treble_clef_diagnostics(diags)

    assert summary["kind"] == "raster_treble_clef_diagnostics_summary"
    assert summary["status"] == "success"
    assert summary["page_index"] == 1
    assert summary["staff_count"] == len(diags["staffs"])
    assert "treble_clef_candidate" in summary["label_counts"]
    assert "unknown" in summary["label_counts"]
    
    # Check that staff summaries preserve staff index and label, and no ScoreIR fields leaked
    assert len(summary["staffs"]) == summary["staff_count"]
    for s in summary["staffs"]:
        assert "staff_index" in s
        assert s["label"] in ("treble_clef_candidate", "unknown")
        assert "has_opening_symbol_candidate" in s
        assert "score_ir" not in s
        assert "clef" not in s
        assert "pitch" not in s
        assert "rhythm" not in s
        assert "key_signature" not in s
        assert "time_signature" not in s
        assert "notes" not in s
        assert "rests" not in s
        assert "voices" not in s


def test_summarize_raster_treble_clef_diagnostics_on_flash_cards(flash_cards_path: Path):
    from score2gp.pdf_raster_staff_diagnostics import summarize_raster_treble_clef_diagnostics
    assert flash_cards_path.exists(), f"Required fixture {flash_cards_path} is missing."

    doc = fitz.open(flash_cards_path)
    page = doc[0]

    diags = build_raster_notation_diagnostics(page, page_index=1, scale=2.0)
    summary = summarize_raster_treble_clef_diagnostics(diags)

    assert summary["kind"] == "raster_treble_clef_diagnostics_summary"
    assert summary["status"] == "success"
    assert summary["page_index"] == 1
    assert summary["staff_count"] == len(diags["staffs"])
    assert "treble_clef_candidate" in summary["label_counts"]
    assert "unknown" in summary["label_counts"]


def test_summarize_raster_treble_clef_diagnostics_missing_classification():
    from score2gp.pdf_raster_staff_diagnostics import summarize_raster_treble_clef_diagnostics
    diags = {
        "status": "success",
        "page_index": 2,
        "staffs": [
            {
                "staff_index": 0,
                "raster_opening_symbol_candidate": {},
                # missing classification
            }
        ]
    }
    summary = summarize_raster_treble_clef_diagnostics(diags)
    assert summary["status"] == "success"
    assert summary["label_counts"]["unknown"] == 1
    assert summary["staffs"][0]["label"] == "unknown"


def test_summarize_raster_treble_clef_diagnostics_malformed_top_level():
    from score2gp.pdf_raster_staff_diagnostics import summarize_raster_treble_clef_diagnostics
    for malformed in [None, "malformed", 123, []]:
        summary = summarize_raster_treble_clef_diagnostics(malformed)
        assert summary["kind"] == "raster_treble_clef_diagnostics_summary"
        assert summary["status"] == "unknown"
        assert summary["page_index"] == -1
        assert summary["staff_count"] == 0
        assert "treble_clef_candidate" in summary["label_counts"]
        assert "unknown" in summary["label_counts"]
        assert len(summary["staffs"]) == 0


def test_summarize_raster_treble_clef_diagnostics_malformed_staffs():
    from score2gp.pdf_raster_staff_diagnostics import summarize_raster_treble_clef_diagnostics
    diags = {
        "status": "success",
        "page_index": 1,
        # staffs is not a list
        "staffs": "malformed"
    }
    summary = summarize_raster_treble_clef_diagnostics(diags)
    assert summary["status"] == "unknown"
    assert summary["staff_count"] == 0
    assert len(summary["staffs"]) == 0


def test_summarize_raster_treble_clef_diagnostics_no_mutation():
    from score2gp.pdf_raster_staff_diagnostics import summarize_raster_treble_clef_diagnostics
    import copy
    
    diags = {
        "status": "success",
        "page_index": 1,
        "staffs": [
            {
                "staff_index": 0,
                "raster_opening_symbol_candidate": {"bbox": [1, 2, 3, 4]},
                "raster_opening_symbol_classification": {
                    "kind": "treble_clef_candidate_classifier",
                    "label": "treble_clef_candidate",
                    "reason": "Test",
                    "features": {"height_to_spacing": 4.0}
                }
            }
        ]
    }
    diags_copy = copy.deepcopy(diags)
    
    summary = summarize_raster_treble_clef_diagnostics(diags)
    
    # Mutate the returned summary to prove it doesn't affect diags
    summary["staffs"][0]["features"]["height_to_spacing"] = 9.9
    summary["label_counts"]["unknown"] = 99
    
    assert diags == diags_copy


@pytest.fixture
def negative_blank_path() -> Path:
    return Path("tests/fixtures/pdf/generated_standard_staff_negative_blank.pdf")


@pytest.fixture
def negative_tab_path() -> Path:
    return Path("tests/fixtures/pdf/generated_standard_staff_negative_tab.pdf")


@pytest.fixture
def negative_noise_path() -> Path:
    return Path("tests/fixtures/pdf/generated_standard_staff_negative_noise.pdf")


def test_raster_treble_clef_diagnostics_reject_blank_staff(negative_blank_path: Path):
    from score2gp.pdf_raster_staff_diagnostics import summarize_raster_treble_clef_diagnostics
    assert negative_blank_path.exists()
    doc = fitz.open(negative_blank_path)
    
    diags = build_raster_notation_diagnostics(doc[0], page_index=1, scale=2.0)
    summary = summarize_raster_treble_clef_diagnostics(diags)

    assert summary["status"] == "success"
    # Blank standard staff is detected as 1 staff, but lacking a clef candidate it must be 'unknown'
    assert summary["staff_count"] == 1
    assert summary["label_counts"].get("treble_clef_candidate", 0) == 0
    assert summary["label_counts"].get("unknown", 0) == 1
    
    s = summary["staffs"][0]
    assert s["label"] == "unknown"
    assert "score_ir" not in s
    assert "clef" not in s
    for forbidden in ["pitch", "rhythm", "key_signature", "time_signature", "notes", "rests", "voices"]:
        assert forbidden not in s


def test_raster_treble_clef_diagnostics_reject_tab_staff(negative_tab_path: Path):
    from score2gp.pdf_raster_staff_diagnostics import summarize_raster_treble_clef_diagnostics
    assert negative_tab_path.exists()
    doc = fitz.open(negative_tab_path)
    
    diags = build_raster_notation_diagnostics(doc[0], page_index=1, scale=2.0)
    summary = summarize_raster_treble_clef_diagnostics(diags)

    assert summary["status"] == "success"
    # A TAB staff (6 lines) does not yield a valid 5-line notation staff for this diagnostic pass
    assert summary["staff_count"] == 0
    assert summary["label_counts"].get("treble_clef_candidate", 0) == 0


def test_raster_treble_clef_diagnostics_reject_noise(negative_noise_path: Path):
    from score2gp.pdf_raster_staff_diagnostics import summarize_raster_treble_clef_diagnostics
    assert negative_noise_path.exists()
    doc = fitz.open(negative_noise_path)
    
    diags = build_raster_notation_diagnostics(doc[0], page_index=1, scale=2.0)
    summary = summarize_raster_treble_clef_diagnostics(diags)

    assert summary["status"] == "success"
    # Random noise / text without lines does not yield any staves
    assert summary["staff_count"] == 0
    assert summary["label_counts"].get("treble_clef_candidate", 0) == 0
