"""Real-source controls for the explicitly added REFUSE-20 coverage.

No recognition oracle is synthesized here. The rule-drop control retains the
old unresolved input state; the GPIF control retains exact old byte digests
outside the one independently page-checked newly written bar.
"""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile


def disable_duration_roll_extension(monkeypatch):
    from score2gp.notation_omr import note_duration as nd

    original = nd._wave_column_ids

    def legacy(glyphs, space):
        with patch("score2gp.pdf_arpeggios._marks_from_drawings", return_value=[]):
            return original(glyphs, space)

    monkeypatch.setattr(nd, "_wave_column_ids", legacy)


def legacy_duration_roll_cli():
    return [sys.executable, "-c",
            "from unittest.mock import patch\n"
            "from score2gp.notation_omr import note_duration as nd\n"
            "original=nd._wave_column_ids\n"
            "def legacy(glyphs, space):\n"
            "    with patch('score2gp.pdf_arpeggios._marks_from_drawings', return_value=[]):\n"
            "        return original(glyphs, space)\n"
            "nd._wave_column_ids=legacy\n"
            "from score2gp.cli import app\napp()"]


def without_verified_added_bar(actual: bytes, score_file: Path, bar_index: int) -> bytes:
    """Retain old whole-file hashes while checking the allowed new-bar exception.

    Verify that the saved IR reproduces the actual normal-CLI GPIF byte for
    byte. Check the new bar's page-counted shape and all four slide channels,
    then restore only that bar's former empty events. Every other model field
    and every old byte remain subject to the caller's original fixed digests.
    """
    from score2gp.gp_package import write_gp
    from score2gp.ir import ScoreIR

    score = ScoreIR.from_json_file(score_file)
    events = score.bars[bar_index].events
    assert len(events) == 4
    assert [len(e.notes) for e in events] == [3, 3, 1, 2]
    assert all(not e.is_rest for e in events)
    assert sum(e.timing.duration_ticks for e in events) == 3840
    slides = [[t for n in e.notes for t in n.techniques if t.kind == "slide"] for e in events]
    assert list(map(len, slides)) == [3, 0, 0, 1]
    assert all(t.style == "legato" for group in slides for t in group)
    assert slides[-1][0].target_event_id == score.bars[bar_index + 1].events[0].id
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="r20-preserve-", dir=root / "work") as directory:
        output = Path(directory) / "output.gp"
        write_gp(score.model_copy(deep=True), output)
        with ZipFile(output) as package:
            assert package.read("Content/score.gpif") == actual
        prior = score.model_copy(deep=True)
        prior.bars[bar_index].events = []
        write_gp(prior, output)
        with ZipFile(output) as package:
            return package.read("Content/score.gpif")
