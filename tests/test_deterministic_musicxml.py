import pytest
from pathlib import Path
import xml.etree.ElementTree as ET
from unittest.mock import patch
from score2gp.deterministic_musicxml import generate_musicxml_sidecar

def test_generate_musicxml_with_ties_and_rests(tmp_path):
    pdf = tmp_path / "dummy.pdf"
    pdf.write_text("dummy")
    out = tmp_path / "test.musicxml"

    # Mock run_recognition_on_file to return a synthetic timeline_preview
    synthetic_res = {
        "timeline_preview": [{
            "page_index": 1,
            "system_index": 1,
            "staff_index": 1,
            "measures": [{
                "measure_index": 1,
                "events": [
                    {
                        "candidate_id": "rest_1",
                        "symbol_type": "quarter_rest_candidate",
                        "voice": 1,
                        "start_tick": 0,
                        "duration_ticks": 960,
                        "resolved_pitch": None
                    },
                    {
                        "candidate_id": "note_1",
                        "symbol_type": "quarter_note_candidate",
                        "voice": 1,
                        "start_tick": 960,
                        "duration_ticks": 960,
                        "resolved_pitch": "C4",
                        "is_tie_start": True
                    },
                    {
                        "candidate_id": "note_2",
                        "symbol_type": "quarter_note_candidate",
                        "voice": 1,
                        "start_tick": 1920,
                        "duration_ticks": 960,
                        "resolved_pitch": "C4",
                        "is_tie_stop": True
                    }
                ]
            }]
        }]
    }

    with patch("score2gp.deterministic_musicxml.run_recognition_on_file", return_value=synthetic_res):
        generate_musicxml_sidecar(pdf, out)

    assert out.exists()

    tree = ET.parse(out)
    root = tree.getroot()

    notes = root.findall(".//note")
    assert len(notes) == 3

    # Rest
    assert notes[0].find("rest") is not None
    assert notes[0].find("chord") is None

    # Start note
    assert notes[1].find("pitch") is not None
    assert notes[1].find("pitch/step").text == "C"
    assert notes[1].find("chord") is None
    ties_start = notes[1].findall("tie")
    assert len(ties_start) == 1
    assert ties_start[0].get("type") == "start"

    notations_start = notes[1].find("notations")
    assert notations_start is not None
    tied_start = notations_start.find("tied")
    assert tied_start is not None
    assert tied_start.get("type") == "start"

    # Stop note
    assert notes[2].find("pitch") is not None
    assert notes[2].find("chord") is None
    ties_stop = notes[2].findall("tie")
    assert len(ties_stop) == 1
    assert ties_stop[0].get("type") == "stop"

    notations_stop = notes[2].find("notations")
    assert notations_stop is not None
    tied_stop = notations_stop.find("tied")
    assert tied_stop is not None
    assert tied_stop.get("type") == "stop"
