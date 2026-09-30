"""Public engraved PDF through the complete PDF-only route."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from test_dur_02_oracle import read_gp_free_text
from score2gp.pdf_text_labels import _classify


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/pdf/omit_03/engraved_text_labels.pdf"


def test_printed_labels_reach_their_source_beats() -> None:
    scratch_root = ROOT / "work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as directory:
        scratch = Path(directory)
        source = scratch / "input.pdf"
        shutil.copyfile(SOURCE, source)
        output = scratch / "written.gp"
        report = scratch / "report.json"
        result = subprocess.run(
            [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(source),
             "--pdf-only-tab", "--time-signature", "4/4", "--out", str(output),
             "--work-dir", str(scratch / "build"), "--json-report", str(report)],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr[-1200:]
        assert read_gp_free_text(output) == [(1, 1, "Example A - [0:13]"),
                                             (3, 1, "Bridge passage")]
        counts = json.loads(report.read_text())["summary_counts"]["pdf_text_candidate_counts_by_reason"]
        assert counts["pdf_text_label"] == 2
        assert sum(counts.values()) > 2


def test_annotation_classifier_refuses_other_text_roles() -> None:
    assert _classify("H", "Arial", 9, True) == "pdf_text_technique"
    assert _classify("sl.", "Arial", 9, True) == "pdf_text_technique"
    assert _classify("Am7", "Arial", 9, True) == "pdf_text_chord"
    assert _classify("A 7", "Arial", 9, True) == "pdf_text_chord"
    assert _classify("Bø", "Arial", 9, True) == "pdf_text_chord"
    assert _classify("Gm7\ue2605", "Arial", 9, True) == "pdf_text_music_symbol"
    assert _classify("= 120", "Arial", 9, True) == "pdf_text_tempo"
    assert _classify("Q=120", "Arial", 9, True) == "pdf_text_tempo"
    assert _classify("Music by Ada", "Arial", 9, True) == "pdf_text_page_furniture"
    assert _classify("Tuning: E A D G B E", "Arial", 9, True) == "pdf_text_page_furniture"
    assert _classify("Study in Motion", "Arial", 25, True) == "pdf_text_title_or_subtitle"
    assert _classify("Bridge passage", "Arial", 9, False) == "pdf_text_outside_annotation_band"
