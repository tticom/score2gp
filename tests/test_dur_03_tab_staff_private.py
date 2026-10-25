"""DUR-03-FU1: real-source guards for the five-legacy-row recovery alternative.

Measured through _detect_tab_systems on the mounted approved corpus, not GP
references: eight recovered systems on seven pages disappear if the alternative
is dropped or its threshold is raised to six. Lowering it to four admits an
extra system on each of Melodic_Expressions pages 9 and 12. The assertions keep
only source labels, one-based page/system indices, counts and recovery flags.
No synthetic source contributes acceptance evidence.
"""

from pathlib import Path

import pymupdf
import pytest

from score2gp.pdf import _detect_tab_systems


PRIVATE = Path(__file__).resolve().parents[1] / "fixtures" / "private"
BORING_SCALE = "This_039_Boring_039_Scale_Exercise_Will_Save_You_Years_But_Most_Skip_This_"

# Each tuple is (system index, string-line count, bar-box count, recovered).
# Dependent labels: Just-Practice P2/S2; Lesson-5 P2/S5 and P3/S2;
# Melodic_Expressions P2/S3, P13/S4 and P28/S3; Boring-Scale P1/S2 and P1/S3.
# All eight reach intact < 3 with old_line_rows == 5. The other systems on
# these pages must stay intact too; P28/S2 uses the three-intact-line route.
@pytest.mark.parametrize(("stem", "page_number", "expected"), [
    pytest.param("Just-Practice-Like-THIS-Every-Day", 2, [
        (1, 6, 2, False), (2, 6, 6, True), (3, 6, 2, False),
    ], id="Just-Practice-P2-S2"),
    pytest.param("Lesson-5", 2, [
        (1, 6, 4, False), (2, 6, 3, False), (3, 6, 2, False),
        (4, 6, 3, False), (5, 6, 3, True), (6, 6, 3, False),
    ], id="Lesson-5-P2-S5"),
    pytest.param("Lesson-5", 3, [
        (1, 6, 2, False), (2, 6, 2, True), (3, 5, 3, False),
    ], id="Lesson-5-P3-S2"),
    pytest.param("Melodic_Expressions", 2, [
        (1, 6, 2, False), (2, 6, 2, False), (3, 6, 2, True),
        (4, 6, 1, False), (5, 6, 2, False),
    ], id="Melodic-Expressions-P2-S3"),
    pytest.param("Melodic_Expressions", 13, [
        (1, 6, 2, False), (2, 6, 2, False), (3, 6, 4, False), (4, 6, 4, True),
    ], id="Melodic-Expressions-P13-S4"),
    pytest.param("Melodic_Expressions", 28, [
        (1, 6, 4, False), (2, 6, 4, True), (3, 6, 5, True),
        (4, 6, 2, False), (5, 6, 4, False),
    ], id="Melodic-Expressions-P28-S3"),
    pytest.param(BORING_SCALE, 1, [
        (1, 6, 3, False), (2, 6, 6, True), (3, 6, 4, True),
        (4, 6, 2, False), (5, 6, 2, False),
    ], id="Boring-Scale-P1-S2-S3"),
    # Negative real-source controls reject threshold 5 -> 4: each admits one
    # additional recovered system with only four legacy rows (zero/one intact).
    pytest.param("Melodic_Expressions", 9, [
        (1, 6, 2, False), (2, 5, 3, False), (3, 6, 2, False), (4, 5, 2, False),
    ], id="Melodic-Expressions-P9-reject-four-rows"),
    pytest.param("Melodic_Expressions", 12, [
        (1, 6, 2, False), (2, 6, 2, False), (3, 6, 2, False), (4, 6, 2, False),
    ], id="Melodic-Expressions-P12-reject-four-rows"),
])
def test_real_tab_recovery_topology(stem, page_number, expected):
    """Reject drop/5->6 on seven pages and 5->4 on the two negative pages."""
    path = PRIVATE / f"{stem}.pdf"
    assert path.is_file(), f"required approved PDF absent: {path.name}"
    with pymupdf.open(path) as document:
        systems = _detect_tab_systems(document[page_number - 1], page_number)
    actual = [
        (index, len(system.line_ys), max(len(system.barlines) - 1, 0),
         system.segmented_lines_recovered)
        for index, system in enumerate(systems, 1)
    ]
    assert actual == expected, f"{stem} P{page_number}: TAB system topology"


def test_lesson5_bar_counts_stay_unchanged():
    """Reject drop/5->6: they lose five of Lesson 5's 43 detected bar boxes."""
    path = PRIVATE / "Lesson-5.pdf"
    assert path.is_file(), "required approved PDF absent: Lesson-5.pdf"
    with pymupdf.open(path) as document:
        page_counts = [
            sum(max(len(system.barlines) - 1, 0)
                for system in _detect_tab_systems(page, page_number))
            for page_number, page in enumerate(document, 1)
        ]
    assert page_counts == [18, 18, 7]
    assert sum(page_counts) == 43
