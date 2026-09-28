"""Public engraved-score PDF to GPIF barline regressions.

The PDFs are derived from a standard notation and TAB source. The six marks
are drawn as ordinary notation, independently of the production stroke table.
"""

import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/pdf/omit_02"


@pytest.mark.parametrize(("source", "expected"), [
    ("standard_single", [(False, False, None), (False, False, None)]),
    ("standard_double", [(True, False, None), (False, False, None)]),
    ("repeat_dots", [(False, False, 2), (False, False, None)]),
    ("repeat_start", [(False, False, None), (False, True, None)]),
    ("final_heavy", [(False, False, None), (False, False, None)]),
    ("thick_single", [(False, False, None), (False, False, None)]),
    ("system_start_bracket", [(False, False, None), (False, False, None)]),
])
def test_engraved_barline_reaches_master_gpif(source, expected):
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omit02_", dir=work) as directory:
        scratch = Path(directory)
        pdf = scratch / "input.pdf"
        gp = scratch / "output.gp"
        shutil.copyfile(FIXTURES / f"{source}.pdf", pdf)
        source_root = os.environ.get("SCORE2GP_OMIT02_MUTANT_SRC", str(ROOT / "src"))
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(pdf),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(gp),
             "--work-dir", str(scratch / "work")],
            env={**os.environ, "PYTHONPATH": source_root}, text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        with ZipFile(gp) as package:
            root = ET.fromstring(package.read("Content/score.gpif"))
        bars = root.find("MasterBars").findall("MasterBar")
        flags = [(bar.find("DoubleBar") is not None,
                  bar.find("RepeatStart") is not None,
                  int(bar.find("Repeat").get("count")) if bar.find("Repeat") is not None else None)
                 for bar in bars]
        assert flags == expected
        if source in {"standard_double", "repeat_dots", "repeat_start", "final_heavy", "thick_single"}:
            ir = json.loads((scratch / "work/score.ir.json").read_text(encoding="utf-8"))
            code = {"standard_double": "pdf_double_barline_read",
                    "repeat_dots": "pdf_repeat_end_barline_read",
                    "repeat_start": "pdf_repeat_start_barline_read",
                    "final_heavy": "pdf_end_barline_read",
                    "thick_single": "pdf_barline_thick_single_kind_unresolved"}[source]
            evidence = [warning for warning in ir["warnings"] if warning["code"] == code]
            assert len(evidence) == 1
            strokes = evidence[0]["provenance"][0]["raw"]["strokes"]
            assert len(strokes) >= (1 if source == "thick_single" else 2)
            assert all(stroke["primitive_id"] for stroke in strokes)
        if source == "final_heavy":
            assert bars[-1].findtext("Barline") == "End"
