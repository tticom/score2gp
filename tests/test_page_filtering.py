import pytest
from pathlib import Path
from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_files
from score2gp.ir import ScoreIR
from score2gp.gp_package import write_gp, validate_roundtrip


def test_page_filtering_remediation(tmp_path) -> None:
    musicxml_path = Path("fixtures/public/test_page_filtering.musicxml")
    tabraw_path = Path("fixtures/public/test_page_filtering.tabraw.json")
    
    # 1. Compile without page filtering -> should fail due to page 2 unboxed layout warnings
    with pytest.raises(BuildIrInputRiskError) as exc_info:
        build_ir_from_files(
            musicxml_path=musicxml_path,
            tabraw_path=tabraw_path,
        )
    assert exc_info.value.category == "partial_pdf_grouping"
    assert "grouping is partial or missing" in str(exc_info.value)
    
    # 2. Compile with page range filtering constraint page_range=(1, 1) -> should succeed cleanly!
    score = build_ir_from_files(
        musicxml_path=musicxml_path,
        tabraw_path=tabraw_path,
        page_range=(1, 1),
    )
    assert isinstance(score, ScoreIR)
    assert len(score.bars) == 2
    
    # Check that page 1 candidate (parsed_fret 0, string 1) was placed in bar 1
    bar1_events = score.bars[0].events
    assert len(bar1_events) == 1
    assert bar1_events[0].notes[0].fret == 0
    assert bar1_events[0].notes[0].string == 1
    
    # Check that bar 2 has no events (is a rest) because page 2 candidates were filtered out!
    bar2_events = score.bars[1].events
    assert len(bar2_events) == 0
    
    # 3. Write GP7 package and verify roundtrip validation is 100% successful
    out_gp = tmp_path / "test_page_filtering.gp"
    warnings = write_gp(score, out_gp)
    assert warnings == []
    
    rt_res = validate_roundtrip(out_gp, score)
    assert rt_res["valid"], f"Roundtrip failed: {rt_res['errors']}"
