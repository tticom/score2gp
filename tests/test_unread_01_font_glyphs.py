"""Source-font paint reaches unchanged recognition rules; no reference enters them."""
from pathlib import Path
import tempfile

import pymupdf
import pytest

from score2gp.notation_omr.note_duration import extract_page_symbols, find_staves, read_note_durations

ROOT = Path(__file__).resolve().parents[1]


def test_derek_music_font_keys_are_read_or_located_by_the_existing_gate():
    source = ROOT / "fixtures/private/Derek Trucks BB King.pdf"
    assert source.is_file(), "required approved private source missing"
    result = read_note_durations(source)
    keys = result["diagnostics"]["key_signatures"]
    assert len(keys) == 9
    assert [key["fifths"] for key in keys if key["status"] == "read"] == [-4] * 8
    refused = [key for key in keys if key["status"] == "refused"]
    assert len(refused) == 1
    assert refused[0]["reason"] == "font_glyph_key_signature_partial_or_ambiguous"
    assert all(refused[0]["location"][k] is not None for k in
               ("page_index", "system_index", "bar_index"))
    assert result["summary"]["bars"] == 16
    assert result["summary"]["read_events"] == 217
    assert result["summary"]["unread_reasons"] == {
        "grace_note_in_tuplet": 9, "rest_glyph_unidentified": 1}


@pytest.mark.parametrize("name,read,unread", [
    ("G-Am-C-Lick", 70, 38), ("Lesson-3", 465, 0),
])
def test_approved_drawing_sources_keep_their_reader_events(name, read, unread):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    result = read_note_durations(source)
    assert result["summary"]["read_events"] == read
    assert result["summary"]["unread_events"] == unread


@pytest.mark.parametrize("scale", [0.5, 2.0])
def test_actual_font_contours_keep_their_staff_relative_dimensions(scale):
    """A transformed copy of the approved PDF, never generated notation."""
    source = ROOT / "fixtures/private/Derek Trucks BB King.pdf"
    assert source.is_file(), "required approved private source missing"
    with pymupdf.open(source) as original:
        original_symbols = extract_page_symbols(original[0], 0)
        original_staff = find_staves(original_symbols)[0][0]
        contours = [g for g in original_symbols.glyphs
                    if g.drawing.get("font_glyph_codes") == ["U+E050"]]
        assert len(contours) == 5
        original_ratios = [(g.w / original_staff.space, g.h / original_staff.space) for g in contours]
        work = ROOT / "work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="unread01-font-", dir=work) as directory:
            target = Path(directory) / "scaled.pdf"
            with pymupdf.open() as derived:
                page = derived.new_page(width=original[0].rect.width * scale,
                                        height=original[0].rect.height * scale)
                page.show_pdf_page(page.rect, original, 0)
                derived.save(target)
            with pymupdf.open(target) as transformed:
                symbols = extract_page_symbols(transformed[0], 0)
                staff = find_staves(symbols)[0][0]
                contours = [g for g in symbols.glyphs
                            if g.drawing.get("font_glyph_codes") == ["U+E050"]]
                assert len(contours) == 5
                ratios = [(g.w / staff.space, g.h / staff.space) for g in contours]
                for before, after in zip(original_ratios, ratios):
                    assert after == pytest.approx(before, abs=0.005)


@pytest.mark.parametrize("name, counts", [
    ("Derek Trucks BB King", [421, 372]),
    ("Can't Find My Way Home (open chord shenanigans)", [3, 2]),
])
def test_music_font_outlines_work_in_a_fresh_process(name, counts):
    """The ordinary reader must not depend on prior XML namespace registration."""
    import json
    import subprocess
    import sys

    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    code = (
        "import json,sys,pymupdf; "
        "from score2gp.notation_omr.font_glyphs import music_font_drawings; "
        "d=pymupdf.open(sys.argv[1]); "
        "print(json.dumps([len(music_font_drawings(p)) for p in d]))"
    )
    run = subprocess.run([sys.executable, "-c", code, str(source)], cwd=ROOT,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == counts


@pytest.mark.parametrize("name, beam_events", [
    ("Derek Trucks BB King", 120), ("G-Am-C-Lick", 54), ("Lesson-3", 448),
])
def test_real_source_beams_reach_read_events(name, beam_events):
    source = ROOT / "fixtures/private" / (name + ".pdf")
    assert source.is_file(), "required approved private source missing"
    result = read_note_durations(source)
    assert sum(e["status"] == "read" and e["beams"]["count"] > 0
               for e in result["events"]) == beam_events
