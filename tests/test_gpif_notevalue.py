"""GPIF NoteValue spellings from Guitar Pro reference files and alphaTab.

Whole, Half, Quarter, Eighth, 16th and 32nd occur in private reference GPIFs.
64th is pinned to alphaTab's GPIF importer, GpifParser.ts, revision
212f2ece99303eb09abc925e6192900e672531d0, lines 2535-2564:
https://github.com/CoderLine/alphaTab/blob/212f2ece99303eb09abc925e6192900e672531d0/packages/alphatab/src/importer/GpifParser.ts#L2535-L2564
"""

import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from score2gp.gp_package import _extract_score_ir_from_gpif_root


def _production_gpif(value: str, ticks: int) -> ET.Element:
    # build_gpif has a legacy branch selected by pytest in sys.modules. Exercise
    # the CLI's production branch in a fresh interpreter instead.
    code = (
        "from pathlib import Path; from score2gp.ir import ScoreIR; "
        "from score2gp.gpif import build_gpif; "
        "s=ScoreIR.model_validate_json(Path('fixtures/public/tiny_score.ir.json').read_text()); "
        "e=s.bars[0].events[0]; e.timing.notated_duration.value=__import__('sys').argv[1]; "
        "e.timing.duration_ticks=int(__import__('sys').argv[2]); "
        "__import__('sys').stdout.buffer.write(build_gpif(s))"
    )
    completed = subprocess.run([sys.executable, "-c", code, value, str(ticks)],
                               capture_output=True, check=True)
    return ET.fromstring(completed.stdout)


@pytest.mark.parametrize("value,gpif_value,ticks,reference", [
    ("whole", "Whole", 3840, "Lesson-3.gp"),
    ("half", "Half", 1920, "Lesson-3.gp"),
    ("quarter", "Quarter", 960, "Lesson-3.gp"),
    ("eighth", "Eighth", 480, "Lesson-3.gp"),
    ("16th", "16th", 240, "Lesson-5.gp"),
    ("32nd", "32nd", 120, "Derek Trucks BB King.gp"),
    ("64th", "64th", 60, None),
])
def test_writer_uses_reference_notevalue_spelling(value, gpif_value, ticks, reference):
    if reference is not None:
        path = Path("fixtures/private") / reference
        if path.exists():
            with zipfile.ZipFile(path) as package:
                reference_gpif = ET.fromstring(package.read("Content/score.gpif"))
            assert gpif_value in {node.text for node in reference_gpif.iter("NoteValue")}
    gpif = _production_gpif(value, ticks)
    assert next(gpif.iter("NoteValue")).text == gpif_value
    assert gpif_value not in {"Sixteenth", "ThirtySecond", "SixtyFourth"}


@pytest.mark.parametrize("unknown", ["Sixteenth", "ThirtySecond", "SixtyFourth", "Crotchet"])
def test_reader_refuses_unknown_notevalue_instead_of_defaulting_to_quarter(unknown):
    gpif = _production_gpif("eighth", 480)
    next(gpif.iter("NoteValue")).text = unknown
    with pytest.raises(ValueError, match="Unknown GPIF NoteValue"):
        _extract_score_ir_from_gpif_root(gpif)
