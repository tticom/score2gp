"""Real-source refusals that end without a route record (NOROUTE-01).

Seven approved sources are refused by the CLI before any bar exists. NOROUTE-01 measured each one; this test
pins what the located refusal says, on the real sources only. No source is converted by this task: every
class stays refused (reader or representation gap) because the page evidence cannot settle it without a guess.

Oracle: the printed pages, viewed (counts and classes only). Synthetic tests carry no acceptance weight; none
are used. Mutant:
  DROP_LOCATED_REASON   `_no_candidates_details` returns {}: the scanned-book refusal no longer says that the
                        source is a scanned raster with no vector TAB (the diagnostics `details` are empty).
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from score2gp.cli import app

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"

# source -> (CLI exit code, refusal category) as measured on the current runtime.
# PARANOID - BLACK SABBATH was listed here with pdf_only_tab_time_signature_unread; TSIG-01 reads its printed
# cut-time glyph, so it now converts (23 of 38 bars written) and is pinned by test_tsig_01_cut_time_glyph_private.py.
REFUSALS = {
    "5_Grateful_Dead_Intros": (2, "pdf_only_tab_no_notation_bars"),  # PERCX-01: was percussive_strike_without_owning_note
    "LegatoLicks": (4, "pdf_only_tab_grouping_unsafe"),
    "Lick in All 5 CAGED Shapes start on the 5 _ guitar tab creator": (4, "pdf_only_tab_grouping_unsafe"),
}


def _convert(tmp_path, name, *extra):
    pdf = PRIVATE / f"{name}.pdf"
    assert pdf.is_file(), "REQUIRED_NOROUTE_01_SOURCE_MISSING"
    build = tmp_path / "build"
    result = CliRunner().invoke(app, ["convert", "--pdf", str(pdf), "--pdf-only-tab", *extra,
                                      "--out", str(tmp_path / "o.gp"), "--work-dir", str(build)])
    return result.exit_code, build


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_source_stays_refused_with_its_category(tmp_path, name):
    """Rejects: an unmeasured change that converts or reclassifies one of the seven sources without evidence."""
    code, category = REFUSALS[name]
    exit_code, build = _convert(tmp_path, name)
    assert exit_code == code, f"NOROUTE_01_EXIT_{exit_code}"
    diagnostics = json.loads((build / "diagnostics.json").read_bytes())
    assert diagnostics["category"] == category
    assert not (tmp_path / "o.gp").exists()


def test_scanned_book_refusal_is_located_as_a_raster_source(tmp_path):
    """Rejects: the bare "no candidates found in TabRaw" refusal that says nothing about why (mutant above)."""
    exit_code, build = _convert(tmp_path, "Hal Leonard Corporation. Rock Ballads", "--pages", "21-21")
    assert exit_code == 4
    diagnostics = json.loads((build / "diagnostics.json").read_bytes())
    assert diagnostics["category"] == "pdf_only_tab_grouping_unsafe"
    details = diagnostics["details"]
    assert details["located_reason"] == "scanned_raster_source_without_vector_tab"
    assert details["inspection_kind"] == "scanned-or-raster"
    assert "pdf_input_class_scanned_pdf_unsupported" in details["pdf_layout_warnings"]
