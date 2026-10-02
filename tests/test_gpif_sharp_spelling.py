"""Guitar Pro spells sharps '#', not 'Sharp'; unparseable accidentals are dropped by the app."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

from score2gp.gp_package import extract_score_ir_from_gp, write_gp
from score2gp.ir import ScoreIR

SHARP_PITCH = 66  # F#4: first string (E4 = 64) fret 2


def _sharp_score() -> ScoreIR:
    score = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    note = score.bars[0].events[0].notes[0]
    note.string, note.fret, note.pitch = 1, 2, SHARP_PITCH
    score.bars = [score.bars[0]]
    score.bars[0].events = score.bars[0].events[:1]
    return score


@pytest.fixture
def product_gpif_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_gpif switches to a legacy test-only XML shape when pytest is detected.

    The real product path (relational Notes table, as Guitar Pro reads it) is
    selected by hiding pytest from sys.modules/argv, as test_gp_writer does.
    """
    monkeypatch.setattr(sys, "modules", {k: v for k, v in sys.modules.items() if "pytest" not in k})
    monkeypatch.setattr(sys, "argv", [a for a in sys.argv if "pytest" not in a])


def _gpif_text(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        return zf.read("Content/score.gpif").decode("utf-8")


def test_sharp_accidental_written_as_hash(tmp_path: Path, product_gpif_path: None) -> None:
    out = tmp_path / "sharp.gp"
    assert write_gp(_sharp_score(), out) == []
    text = _gpif_text(out)
    assert "Sharp</Accidental>" not in text
    assert "Sharp" not in text.replace("<TransposeAs>Sharps</TransposeAs>", "")
    # ConcertPitch + TransposedPitch for the one sharped note
    assert text.count("<Accidental>#</Accidental>") == 2


def test_sharp_round_trips_through_extract(tmp_path: Path, product_gpif_path: None) -> None:
    out = tmp_path / "sharp.gp"
    write_gp(_sharp_score(), out)
    recovered = extract_score_ir_from_gp(out)
    note = recovered.bars[0].events[0].notes[0]
    assert (note.string, note.fret, note.pitch) == (1, 2, SHARP_PITCH)


def test_reader_accepts_legacy_sharp_spelling(tmp_path: Path, product_gpif_path: None) -> None:
    """Files written before the fix spelled the accidental 'Sharp'; they must still load."""
    out = tmp_path / "sharp.gp"
    legacy = tmp_path / "legacy.gp"
    write_gp(_sharp_score(), out)
    with zipfile.ZipFile(out) as src, zipfile.ZipFile(legacy, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "Content/score.gpif":
                data = data.replace(b"<Accidental>#</Accidental>", b"<Accidental>Sharp</Accidental>")
            dst.writestr(item, data)
    assert "<Accidental>Sharp</Accidental>" in _gpif_text(legacy)
    note = extract_score_ir_from_gp(legacy).bars[0].events[0].notes[0]
    assert note.pitch == SHARP_PITCH
