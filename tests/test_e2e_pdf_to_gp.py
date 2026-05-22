from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from score2gp.ascii_alignment import align_ascii_musicxml_files
from score2gp.build_ir import build_ir_from_files
from score2gp.gp_package import inspect_gp, validate_gp, write_gp
from score2gp.ir import validate_score_ir_file
from score2gp.pdf import extract_tab

ASCII_GATE_PDF = Path("tests/fixtures/pdf/generated_ascii_tab_scoreir_gate.pdf")
ASCII_GATE_MUSICXML = Path("tests/fixtures/musicxml/ascii_scoreir_gate_simple.musicxml")


def test_public_e2e_pdf_to_gp_smoke_proof(tmp_path) -> None:
    # 1. Extract TabRaw from PDF
    tabraw_path = tmp_path / "smoke.tabraw.json"
    extract_tab(ASCII_GATE_PDF, tabraw_path)
    assert tabraw_path.exists()

    # 2. Align ASCII to MusicXML
    alignment_dir = tmp_path / "alignment"
    align_ascii_musicxml_files(
        tabraw_path=tabraw_path,
        musicxml_path=ASCII_GATE_MUSICXML,
        out_dir=alignment_dir,
    )
    alignment_path = alignment_dir / "ascii_musicxml_alignment.json"
    assert alignment_path.exists()

    # 3. Build ScoreIR using the compatible alignment sidecar
    ir_path = tmp_path / "smoke.ir.json"
    diagnostics_path = tmp_path / "smoke.diagnostics.json"
    score = build_ir_from_files(
        musicxml_path=ASCII_GATE_MUSICXML,
        tabraw_path=tabraw_path,
        out_path=ir_path,
        diagnostics_out_path=diagnostics_path,
        ascii_alignment_path=alignment_path,
    )
    assert ir_path.exists()
    assert diagnostics_path.exists()

    # 4. Validate the generated ScoreIR
    validated, errors = validate_score_ir_file(ir_path)
    assert errors == []
    assert validated is not None

    # 5. Write the minimal GP package
    gp_path = tmp_path / "smoke.gp"
    warnings = write_gp(score, gp_path)
    assert gp_path.exists()

    # 6. Validate the GP package zip structure and GPIF XML well-formedness
    validation = validate_gp(gp_path)
    assert validation["is_zip"] is True
    assert validation["xml_well_formed"] is True
    assert validation["errors"] == []

    # 7. Inspect the GP package to retrieve semantic facts
    summary = inspect_gp(gp_path)

    # 8. Assert expected semantic facts
    assert summary["tracks"] == ["Guitar"]
    assert summary["tempo"] == "84"
    assert summary["time_signatures"] == ["4/4"]
    assert summary["bar_count"] == 2
    assert summary["note_count"] == 4

    # String & fret checks
    # The note frets for measure 1 are [0, 1, 2] on string 1, and [3] on string 1 for measure 2.
    # Standard tuning has strings 1-6 as E4, B3, G3, D3, A2, E2.
    # In gpif representation:
    # note pitch elements match the midi pitches:
    # fret 0 on string 1 (E4) -> MIDI 64
    # fret 1 on string 1 (F4) -> MIDI 65
    # fret 2 on string 1 (F#4) -> MIDI 66
    # fret 3 on string 1 (G4) -> MIDI 67
    
    # Assert tunings structure matches Standard Guitar Tuning
    assert len(summary["tunings"]) == 1
    tuning_info = summary["tunings"][0]
    assert tuning_info["track"] == "Guitar"
    assert tuning_info["name"] == "Standard guitar"
    # Ensure 6 strings are mapped
    assert len(tuning_info["strings"]) == 6

    # Verify no private musical content, PDF text, titles, URLs or files appear
    assert "derek" not in str(summary).lower()
    assert "bb king" not in str(summary).lower()
    assert "caged" not in str(summary).lower()

    # Read inside the GPIF to verify no private strings or layout clues are present
    with zipfile.ZipFile(gp_path, "r") as zf:
        gpif_bytes = zf.read("Content/score.gpif")
        gpif_str = gpif_bytes.decode("utf-8")
        assert "Generated ASCII Tab ScoreIR Gate" in gpif_str
        assert "derek" not in gpif_str.lower()
        assert "bb king" not in gpif_str.lower()
        assert "caged" not in gpif_str.lower()
