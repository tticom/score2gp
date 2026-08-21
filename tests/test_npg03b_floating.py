from pathlib import Path
from score2gp.pdf import extract_tab
from score2gp.tabraw import TabRaw

def test_private_acceptance_melodic(tmp_path):
    pdf_path = Path("../score2gp-private-fixtures/fixtures/private/Melodic Soloing Masterclass.pdf").resolve()
    if not pdf_path.exists():
        return

    tabraw_path = tmp_path / "melodic.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))

    # Prove that we have floating barlines extracted
    assert len(tabraw.floating_barlines) > 0

    from score2gp.build_ir import build_ir_from_tabraw_only
    ir, _ = build_ir_from_tabraw_only(tabraw_path)

    bars = ir.bars

    # Prove that we successfully assembled 9 bars
    assert len(bars) == 9

    # Prove that the floating barlines successfully allowed measure splitting/merging
    # resulting in expanded time signatures (e.g. 16/4, 12/4, 8/4)
    expanded_bars = [bar for bar in bars if bar.time_signature.numerator > 4]
    assert len(expanded_bars) > 0

    # Specifically, Bar 4 should be 8/4 (2 sub-measures)

    # Specifically, Bar 4 should be 8/4 (2 sub-measures)
    assert bars[3].time_signature.numerator == 8

    # NEGATIVE CONTROL: Prove that standard barlines from the genuine source PDF are ignored.
    # If standard barlines were incorrectly treated as floating barlines, we'd have dozens of them.
    # Furthermore, none of the valid floating barlines in this specific PDF are in the left margin (<200.0)
    # where standard start-of-system barlines exist.
    assert len(tabraw.floating_barlines) == 11
    for fb in tabraw.floating_barlines:
        assert fb.x > 200.0
