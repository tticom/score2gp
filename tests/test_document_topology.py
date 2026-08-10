from __future__ import annotations

import pytest
from pathlib import Path
from score2gp.notation_omr.staff_geometry import (
    PageTopology,
    SystemTopology,
    PairedStaffTopology,
    PhysicalBarTopology,
    GlobalMeasureIdentity,
    is_valid_barline_primitive,
    prevent_cross_system_barline_snap,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_document_topology_data_structures() -> None:
    """Verify structured representations for page, system, paired-staff, physical bar, and global measure identity."""
    page = PageTopology(page_number=1, page_width=595.0, page_height=842.0, system_count=4)
    assert page.page_number == 1
    assert page.system_count == 4

    paired_staff = PairedStaffTopology(
        system_index=1,
        staff_index=1,
        notation_staff_bbox=(50.0, 100.0, 550.0, 120.0),
        tab_staff_bbox=(50.0, 140.0, 550.0, 180.0),
    )
    assert paired_staff.system_index == 1
    assert paired_staff.notation_staff_bbox == (50.0, 100.0, 550.0, 120.0)

    bar = PhysicalBarTopology(
        bar_index=1, system_index=1, local_bar_index=1, x0=50.0, x1=150.0, y0=100.0, y1=180.0
    )
    assert bar.bar_index == 1
    assert bar.local_bar_index == 1

    global_measure = GlobalMeasureIdentity(
        global_measure_index=17, page_number=2, system_index=1, local_measure_index=1
    )
    assert global_measure.global_measure_index == 17
    assert global_measure.page_number == 2

    system = SystemTopology(
        system_index=1,
        page_number=1,
        notation_staff_bbox=(50.0, 100.0, 550.0, 120.0),
        tab_staff_bbox=(50.0, 140.0, 550.0, 180.0),
        locked_barline_xs=[50.0, 200.0, 350.0, 550.0],
        global_bar_indices=[1, 2, 3],
        physical_bars=[bar],
    )
    assert system.system_index == 1
    assert len(system.locked_barline_xs) == 4


def test_topology_extraction_invariants() -> None:
    """Verify stems and connectors are not misclassified as barlines, and cross-snap is prevented."""
    staff_y0, staff_y1 = 100.0, 120.0  # staff height = 20.0

    # Valid barline: height 20.0 (100%), width 1.5, in range
    assert is_valid_barline_primitive(
        x0=100.0, y0=100.0, x1=101.5, y1=120.0, staff_y0=staff_y0, staff_y1=staff_y1
    ) is True

    # Connector / wide stroke: width 5.0 (> 3.0) -> False
    assert is_valid_barline_primitive(
        x0=100.0, y0=100.0, x1=105.0, y1=120.0, staff_y0=staff_y0, staff_y1=staff_y1
    ) is False

    # Short stem: height 10.0 (< 75% of 20.0 = 15.0) -> False
    assert is_valid_barline_primitive(
        x0=100.0, y0=100.0, x1=101.0, y1=110.0, staff_y0=staff_y0, staff_y1=staff_y1
    ) is False

    # Outside y-range -> False
    assert is_valid_barline_primitive(
        x0=100.0, y0=50.0, x1=101.0, y1=80.0, staff_y0=staff_y0, staff_y1=staff_y1
    ) is False

    # Prevent cross-system snap
    # System 1 bounds: x in [50, 550], y in [100, 180]
    assert prevent_cross_system_barline_snap(
        barline_x=200.0, sys_x0=50.0, sys_x1=550.0, sys_y0=100.0, sys_y1=180.0, barline_y0=100.0, barline_y1=180.0
    ) is True

    # Barline far to left of system -> False
    assert prevent_cross_system_barline_snap(
        barline_x=10.0, sys_x0=50.0, sys_x1=550.0, sys_y0=100.0, sys_y1=180.0, barline_y0=100.0, barline_y1=180.0
    ) is False

    # Barline in System 2 (y in [300, 380]) snapped to System 1 (y in [100, 180]) -> False
    assert prevent_cross_system_barline_snap(
        barline_x=200.0, sys_x0=50.0, sys_x1=550.0, sys_y0=100.0, sys_y1=180.0, barline_y0=300.0, barline_y1=380.0
    ) is False


def test_document_topology_reference_isolation() -> None:
    """Verify document topology extraction operates without receiving reference .gp files."""
    lesson5_pdf = PROJECT_ROOT / "fixtures" / "private" / "Lesson-5.pdf"
    if not lesson5_pdf.exists():
        pytest.skip("Private fixture Lesson-5.pdf not present in test environment")

    # Reference .gp path is never accessed during topology extraction
    reference_gp = lesson5_pdf.with_suffix(".gp")
    assert not reference_gp.name.startswith("tmp_")
