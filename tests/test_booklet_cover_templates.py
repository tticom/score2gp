from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from score2gp.gp_package import write_gp, extract_score_ir_from_gp, validate_roundtrip
from score2gp.ir import ScoreBooklet, BookletCoverPage, BarNumberingOverride


def test_booklet_cover_page_and_bar_numbering_roundtrip(tmp_path) -> None:
    # 1. Load the synthetic booklet cover templates fixture
    fixture_path = "fixtures/public/test_booklet_cover_templates.ir.json"
    booklet = ScoreBooklet.from_json_file(fixture_path)

    # Validate models loaded correctly
    assert booklet.booklet_title == "Synthetic Multi-Movement Cover Template Booklet"
    assert booklet.cover_page is not None
    assert booklet.cover_page.enabled is True
    assert booklet.cover_page.title_alignment == "center"
    assert booklet.cover_page.margin_offset == 25.0
    assert booklet.cover_page.separator_style == "decorative"
    assert booklet.cover_page.intro_text == "Welcome to the Synthetic Collection!"

    # Score I measure numbering overrides
    assert booklet.scores[0].bars[0].bar_numbering is not None
    assert booklet.scores[0].bars[0].bar_numbering.prefix == "A"
    assert booklet.scores[0].bars[0].bar_numbering.offset == 10
    assert booklet.scores[0].bars[0].bar_numbering.show is True

    # Score II measure numbering overrides
    assert booklet.scores[1].bars[0].bar_numbering is not None
    assert booklet.scores[1].bars[0].bar_numbering.prefix == "B"
    assert booklet.scores[1].bars[0].bar_numbering.offset == 20
    assert booklet.scores[1].bars[0].bar_numbering.show is False

    # 2. Write the booklet to a GP package
    out_gp = tmp_path / "booklet_templates.gp"
    warnings = write_gp(booklet, out_gp)
    assert warnings == []
    assert zipfile.is_zipfile(out_gp)

    # 3. Read & Verify Zip contents and XML layouts
    with zipfile.ZipFile(out_gp, "r") as zf:
        members = zf.namelist()
        assert "VERSION" in members
        assert "Content/score.gpif" in members
        assert "Content/movement_1.gpif" in members
        assert "Content/movement_2.gpif" in members
        assert "Content/booklet_index.json" in members

        # Verify booklet_index.json
        index_data = json.loads(zf.read("Content/booklet_index.json").decode("utf-8"))
        assert index_data["booklet_title"] == "Synthetic Multi-Movement Cover Template Booklet"
        assert index_data["cover_page"]["title_alignment"] == "center"
        assert index_data["cover_page"]["margin_offset"] == 25.0
        assert index_data["cover_page"]["separator_style"] == "decorative"
        assert index_data["cover_page"]["intro_text"] == "Welcome to the Synthetic Collection!"

        # Verify <CoverPage> in primary score.gpif Booklet element
        score_xml = zf.read("Content/score.gpif")
        score_root = ET.fromstring(score_xml)
        bk_node = score_root.find(".//Score/Booklet")
        assert bk_node is not None
        assert bk_node.get("title") == "Synthetic Multi-Movement Cover Template Booklet"
        
        cp_node = bk_node.find("CoverPage")
        assert cp_node is not None
        assert cp_node.get("enabled") == "true"
        assert cp_node.find("TitleAlignment").text == "center"
        assert cp_node.find("MarginOffset").text == "25.0"
        assert cp_node.find("SeparatorStyle").text == "decorative"
        assert cp_node.find("IntroText").text == "Welcome to the Synthetic Collection!"

        # Verify <BarNumbering> in movement_1.gpif first Bar node
        mov1_xml = zf.read("Content/movement_1.gpif")
        mov1_root = ET.fromstring(mov1_xml)
        bar1_node = mov1_root.find(".//Bars/Bar[@index='1']")
        assert bar1_node is not None
        bn1 = bar1_node.find("BarNumbering")
        assert bn1 is not None
        assert bn1.find("Prefix").text == "A"
        assert bn1.find("Offset").text == "10"
        assert bn1.find("Show").text == "true"

        # Verify <BarNumbering> in movement_2.gpif first Bar node
        mov2_xml = zf.read("Content/movement_2.gpif")
        mov2_root = ET.fromstring(mov2_xml)
        bar2_node = mov2_root.find(".//Bars/Bar[@index='1']")
        assert bar2_node is not None
        bn2 = bar2_node.find("BarNumbering")
        assert bn2 is not None
        assert bn2.find("Prefix").text == "B"
        assert bn2.find("Offset").text == "20"
        assert bn2.find("Show").text == "false"

    # 4. Extract and check round-trip symmetric equality
    recovered = extract_score_ir_from_gp(out_gp)
    assert isinstance(recovered, ScoreBooklet)
    assert recovered.booklet_title == booklet.booklet_title
    assert recovered.cover_page is not None
    assert recovered.cover_page.title_alignment == "center"
    assert recovered.cover_page.margin_offset == 25.0
    assert recovered.cover_page.separator_style == "decorative"
    assert recovered.cover_page.intro_text == "Welcome to the Synthetic Collection!"

    assert recovered.scores[0].bars[0].bar_numbering is not None
    assert recovered.scores[0].bars[0].bar_numbering.prefix == "A"
    assert recovered.scores[0].bars[0].bar_numbering.offset == 10
    assert recovered.scores[0].bars[0].bar_numbering.show is True

    assert recovered.scores[1].bars[0].bar_numbering is not None
    assert recovered.scores[1].bars[0].bar_numbering.prefix == "B"
    assert recovered.scores[1].bars[0].bar_numbering.offset == 20
    assert recovered.scores[1].bars[0].bar_numbering.show is False

    # 5. Call validate_roundtrip and assert success
    rt_res = validate_roundtrip(out_gp, booklet)
    assert rt_res["valid"] is True
    assert rt_res["errors"] == []
