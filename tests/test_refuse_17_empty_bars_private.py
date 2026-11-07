"""Real-source bars with no notation event and no TAB item (REFUSE-17).

Measured with the normal CLI over every approved PDF: 31 bars were refused as `bar_without_notation_event`.
Viewing the printed pages: one is not a bar at all (`Ex 2 Hands Up` bar 0: the clef, meter and a start-repeat
sign only), the others hold printed digits the extraction never grouped, a one-/two-bar repeat sign, or nothing.
Only the first has a fixed meaning the output can express (a start-repeat sign opens the first bar; it does
not end a bar). It is read: the source has the reference's 11 bars and each equals the reference bar by content.
Every other bar stays refused, never written empty, with a located cause (counts by source below).
Synthetic tests carry no acceptance weight: none are used.
Mutants (each run, each fails a test below):
  DROP_START_REPEAT_RULE    `_is_start_repeat_after_header` never matches: Ex 2 has 12 bars, bar 0 refused.
  DROP_START_REPEAT_SIGNAL  the first bar's start-repeat signal is not emitted: the repeat start is lost.
  DROP_UNGROUPED_DIGIT_CAUSE  the printed-digit cause is never set: the 6 + 1 bars read 'nothing printed'.
"""
import json
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from typer.testing import CliRunner

from score2gp.cli import app
from tests.test_refuse_14_ghost_heads_private import _gpif_bars

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"


def _convert(source, tmp_path):
    pdf = PRIVATE / f"{source}.pdf"
    assert pdf.is_file(), "REQUIRED_REFUSE_17_SOURCE_MISSING"
    build, out = tmp_path / "build", tmp_path / "output.gp"
    CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(out),
                             "--work-dir", str(build)])
    route = json.loads((build / "note-type-route.json").read_bytes())
    return route["bars"], out


def _repeat_flags(path):
    root = ET.fromstring(zipfile.ZipFile(path).read("Content/score.gpif"))
    return [(i + 1, m.find("Repeat").get("start"), m.find("Repeat").get("end"))
            for i, m in enumerate(root.find("MasterBars")) if m.find("Repeat") is not None]


def test_start_repeat_sign_is_not_a_bar_and_output_equals_reference(tmp_path):
    bars, out = _convert("Ex 2 Hands Up", tmp_path)
    ours, reference = _gpif_bars(out), _gpif_bars(PRIVATE / "Ex 2 Hands Up.gp")
    assert len(bars) == len(reference) == 11, "EX2_BAR_COUNT_DIFFERS_FROM_REFERENCE"
    assert all(b["status"] == "written" for b in bars), "EX2_BAR_REFUSED"
    assert len(ours) == 11 and all(bar in reference for bar in ours), "EX2_BAR_DIFFERS_FROM_REFERENCE"
    # The start-repeat sign is carried on the first bar, and the three repeat ends sit on the reference's bars.
    assert _repeat_flags(out) == _repeat_flags(PRIVATE / "Ex 2 Hands Up.gp"), "EX2_REPEAT_FLAGS_DIFFER_FROM_REFERENCE"


def _refused_causes(source, tmp_path):
    bars, _ = _convert(source, tmp_path)
    refused = [b for b in bars if b["reason"] == "bar_without_notation_event"]
    assert all(b["status"] == "refused" and not b["events"] for b in refused), "EMPTY_BAR_WRITTEN"
    return Counter(b["refusal_evidence"]["cause"] for b in refused)


def test_grateful_dead_bars_stay_refused_and_say_what_is_printed(tmp_path):
    causes = _refused_causes("7_Grateful_Dead_Melodies", tmp_path)
    assert causes == {"tab_digits_printed_but_not_grouped": 6, "bar_without_notation_or_tab_item": 16}


def test_gloria_and_exact_blank_bars_stay_refused(tmp_path):
    assert _refused_causes("Gloria", tmp_path) == {"bar_without_notation_or_tab_item": 4}
    assert _refused_causes("The_EXACT_System_Pros_Use_To_Sound_Great_On_ANY_Chord", tmp_path) == {
        "bar_without_notation_or_tab_item": 2}


def test_paranoid_bars_say_digits_are_printed_but_not_grouped(tmp_path):
    causes = _refused_causes("PARANOID - BLACK SABBATH", tmp_path)
    assert causes == {"tab_digits_printed_but_not_grouped": 1, "bar_without_notation_or_tab_item": 1}
