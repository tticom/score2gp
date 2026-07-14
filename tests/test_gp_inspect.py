from __future__ import annotations
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from score2gp.gp_package import inspect_gp, compare_gp

def _create_synthetic_gp_package(temp_dir: Path, filename: str, gpif_xml: bytes) -> Path:
    gp_path = temp_dir / filename
    with zipfile.ZipFile(gp_path, "w") as zf:
        zf.writestr("VERSION", b"7.0\n")
        zf.writestr("Content/score.gpif", gpif_xml)
    return gp_path

def test_inspect_gp_classic_format(tmp_path) -> None:
    gpif_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score>
    <Tracks>
      <Track id="0">
        <Name>Classic Track</Name>
      </Track>
    </Tracks>
    <Bars>
      <Bar id="0">
        <Voices>0 -1 -1 -1</Voices>
      </Bar>
    </Bars>
    <Voice id="0">
      <Event id="e1">
        <Note string="1" fret="5" pitch="64"/>
        <Note string="2" fret="5" pitch="59"/>
      </Event>
      <Event id="e2">
        <Note string="3" fret="2" pitch="55"/>
      </Event>
    </Voice>
  </Score>
</GPIF>
"""
    gp_path = _create_synthetic_gp_package(tmp_path, "classic.gp", gpif_xml)
    summary = inspect_gp(gp_path)
    assert summary["note_count"] == 3

def test_inspect_gp_relational_format(tmp_path) -> None:
    gpif_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score>
    <Tracks>
      <Track id="0">
        <Name>Relational Track</Name>
      </Track>
    </Tracks>
    <Bars>
      <Bar id="0">
        <Voices>0 -1 -1 -1</Voices>
      </Bar>
    </Bars>
  </Score>
  <Voices>
    <Voice id="0"><Beats>0 1</Beats></Voice>
  </Voices>
  <Beats>
    <Beat id="0">
      <Notes>0 1</Notes>
    </Beat>
    <Beat id="1">
      <Notes>0 2</Notes>
    </Beat>
  </Beats>
  <Notes>
    <Note id="0">
      <Fret>5</Fret>
    </Note>
    <Note id="1">
      <Fret>7</Fret>
    </Note>
    <Note id="2">
      <Fret>8</Fret>
    </Note>
  </Notes>
</GPIF>
"""
    gp_path = _create_synthetic_gp_package(tmp_path, "relational.gp", gpif_xml)
    summary = inspect_gp(gp_path)
    assert summary["note_count"] == 4

def test_compare_gp_different_representations(tmp_path) -> None:
    classic_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score>
    <Tracks>
      <Track id="0">
        <Name>Guitar</Name>
      </Track>
    </Tracks>
    <Bars>
      <Bar id="0">
        <Voices>0 -1 -1 -1</Voices>
      </Bar>
    </Bars>
    <Voice id="0">
      <Event id="e1">
        <Note string="1" fret="5" pitch="64"/>
      </Event>
      <Event id="e2">
        <Note string="2" fret="5" pitch="59"/>
      </Event>
    </Voice>
  </Score>
</GPIF>
"""
    relational_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score>
    <Tracks>
      <Track id="0">
        <Name>Guitar</Name>
      </Track>
    </Tracks>
    <Bars>
      <Bar id="0">
        <Voices>0 -1 -1 -1</Voices>
      </Bar>
    </Bars>
  </Score>
  <Voices>
    <Voice id="0"><Beats>0 1</Beats></Voice>
  </Voices>
  <Beats>
    <Beat id="0">
      <Notes>0</Notes>
    </Beat>
    <Beat id="1">
      <Notes>1</Notes>
    </Beat>
  </Beats>
  <Notes>
    <Note id="0">
      <Fret>5</Fret>
    </Note>
    <Note id="1">
      <Fret>5</Fret>
    </Note>
  </Notes>
</GPIF>
"""
    path_classic = _create_synthetic_gp_package(tmp_path, "classic.gp", classic_xml)
    path_relational = _create_synthetic_gp_package(tmp_path, "relational.gp", relational_xml)

    comp = compare_gp(path_classic, path_relational)
    assert "note_count" not in comp["differences"]


def test_compare_gp_normalized_track_names(tmp_path) -> None:
    gpif_guitar = b"""<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score>
    <Tracks>
      <Track id="0">
        <Name>Guitar</Name>
      </Track>
    </Tracks>
  </Score>
</GPIF>
"""
    gpif_clean_guitar = b"""<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score>
    <Tracks>
      <Track id="0">
        <Name>Clean Guitar</Name>
      </Track>
    </Tracks>
  </Score>
</GPIF>
"""
    path_guitar = _create_synthetic_gp_package(tmp_path, "guitar.gp", gpif_guitar)
    path_clean = _create_synthetic_gp_package(tmp_path, "clean.gp", gpif_clean_guitar)

    comp = compare_gp(path_guitar, path_clean)
    assert comp["matches"] is True
    assert "tracks" not in comp["differences"]
