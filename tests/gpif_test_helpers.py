"""Explicit compatibility writers and structural checks for writer plumbing tests.

Public IR inputs here prove serialization selection, not musical fidelity.
"""

from functools import partial
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from score2gp.gp_package import write_gp
from score2gp.gpif import build_gpif


legacy_write_gp = partial(write_gp, gpif_layout="legacy")
legacy_build_gpif = partial(build_gpif, layout="legacy")


def assert_production_gpif(data):
    root = ET.fromstring(data)
    assert root.tag == "GPIF"
    for table in ("Tracks", "MasterBars", "Bars", "Voices", "Beats", "Notes", "Rhythms"):
        assert root.find(table) is not None, f"production GPIF missing root table {table}"
    assert root.find("Score/Bars") is None, "legacy hierarchical GPIF emitted"


def assert_production_package(path):
    with ZipFile(path) as package:
        names = [name for name in package.namelist() if name.endswith(".gpif")]
        assert "Content/score.gpif" in names
        for name in names:
            assert_production_gpif(package.read(name))
