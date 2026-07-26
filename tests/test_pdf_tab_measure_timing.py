from __future__ import annotations

import pytest

from score2gp.build_ir import BuildIrInputRiskError
from score2gp.pdf_tab_measure_timing import (
    RestDurationDescriptor,
    decompose_pdf_tab_measure_remainder_to_rests,
    select_pdf_tab_grid_spacing_and_duration_name,
    validate_pdf_tab_measure_capacity,
)


def test_select_pdf_tab_grid_spacing_and_duration_name() -> None:
    # Editable draft mode defaults to 960 quarter
    assert select_pdf_tab_grid_spacing_and_duration_name(0, editable_draft=True) == (960, "quarter")
    assert select_pdf_tab_grid_spacing_and_duration_name(4, editable_draft=True) == (960, "quarter")

    # Standard mode based on N candidate subgroups
    assert select_pdf_tab_grid_spacing_and_duration_name(0) == (480, "eighth")
    assert select_pdf_tab_grid_spacing_and_duration_name(4) == (480, "eighth")
    assert select_pdf_tab_grid_spacing_and_duration_name(8) == (480, "eighth")
    assert select_pdf_tab_grid_spacing_and_duration_name(9) == (240, "16th")
    assert select_pdf_tab_grid_spacing_and_duration_name(16) == (240, "16th")
    assert select_pdf_tab_grid_spacing_and_duration_name(17) == (120, "32nd")
    assert select_pdf_tab_grid_spacing_and_duration_name(32) == (120, "32nd")
    assert select_pdf_tab_grid_spacing_and_duration_name(33) == (60, "64th")


def test_validate_pdf_tab_measure_capacity_valid() -> None:
    # Valid onsets and event durations (0, 60, 480, 960, 3840)
    validate_pdf_tab_measure_capacity(0, 60, output_bar_idx=1)
    validate_pdf_tab_measure_capacity(0, 480, output_bar_idx=1)
    validate_pdf_tab_measure_capacity(0, 960, output_bar_idx=1)
    validate_pdf_tab_measure_capacity(0, 3840, output_bar_idx=1)
    validate_pdf_tab_measure_capacity(3360, 480, output_bar_idx=1)
    validate_pdf_tab_measure_capacity(2880, 960, output_bar_idx=1)


def test_validate_pdf_tab_measure_capacity_overcapacity_refusal() -> None:
    # Over-capacity cases (3840 + 60 = 3900)
    with pytest.raises(BuildIrInputRiskError) as exc_info:
        validate_pdf_tab_measure_capacity(3840, 60, output_bar_idx=1)

    assert exc_info.value.category == "pdf_only_tab_measure_overcapacity"
    assert exc_info.value.details.get("accumulated_ticks") == "3900"
    assert exc_info.value.details.get("bar_index") == "1"

    # Mixed note/rest refusal at 4320 ticks (5 eighth notes at 2400 + 2 quarter rests at 1920)
    with pytest.raises(BuildIrInputRiskError) as exc_info_mixed:
        validate_pdf_tab_measure_capacity(3360, 960, output_bar_idx=2)

    assert exc_info_mixed.value.category == "pdf_only_tab_measure_overcapacity"
    assert exc_info_mixed.value.details.get("accumulated_ticks") == "4320"
    assert exc_info_mixed.value.details.get("bar_index") == "2"


def test_decompose_pdf_tab_measure_remainder_to_rests() -> None:
    # Remainder 0
    assert decompose_pdf_tab_measure_remainder_to_rests(0) == []

    # Remainder 60 -> 64th
    r60 = decompose_pdf_tab_measure_remainder_to_rests(60)
    assert r60 == [RestDurationDescriptor(name="64th", ticks=60)]
    assert sum(r.ticks for r in r60) == 60

    # Remainder 480 -> eighth
    r480 = decompose_pdf_tab_measure_remainder_to_rests(480)
    assert r480 == [RestDurationDescriptor(name="eighth", ticks=480)]
    assert sum(r.ticks for r in r480) == 480

    # Remainder 960 -> quarter
    r960 = decompose_pdf_tab_measure_remainder_to_rests(960)
    assert r960 == [RestDurationDescriptor(name="quarter", ticks=960)]
    assert sum(r.ticks for r in r960) == 960

    # Remainder 1920 -> half
    r1920 = decompose_pdf_tab_measure_remainder_to_rests(1920)
    assert r1920 == [RestDurationDescriptor(name="half", ticks=1920)]
    assert sum(r.ticks for r in r1920) == 1920

    # Remainder 2400 -> half + eighth
    r2400 = decompose_pdf_tab_measure_remainder_to_rests(2400)
    assert r2400 == [
        RestDurationDescriptor(name="half", ticks=1920),
        RestDurationDescriptor(name="eighth", ticks=480),
    ]
    assert sum(r.ticks for r in r2400) == 2400

    # Remainder 3360 -> half + quarter + eighth
    r3360 = decompose_pdf_tab_measure_remainder_to_rests(3360)
    assert r3360 == [
        RestDurationDescriptor(name="half", ticks=1920),
        RestDurationDescriptor(name="quarter", ticks=960),
        RestDurationDescriptor(name="eighth", ticks=480),
    ]
    assert sum(r.ticks for r in r3360) == 3360

    # Remainder 3840 -> whole
    r3840 = decompose_pdf_tab_measure_remainder_to_rests(3840)
    assert r3840 == [RestDurationDescriptor(name="whole", ticks=3840)]
    assert sum(r.ticks for r in r3840) == 3840


def test_decompose_pdf_tab_measure_remainder_invalid_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        decompose_pdf_tab_measure_remainder_to_rests(-10)
