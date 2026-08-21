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
    assert bars[3].time_signature.numerator == 8

def test_extract_floating_barlines_negative_control():
    from score2gp.pdf_geometry import extract_floating_barlines, _LineSegment
    # Standard barline (thin)
    standard_barline = _LineSegment(x0=100.0, y0=50.0, x1=100.0, y1=150.0, stroke_width=1.0)
    # Thick barline (repeat sign without dots)
    thick_barline = _LineSegment(x0=200.0, y0=50.0, x1=200.0, y1=150.0, stroke_width=3.5)
    # Another thin line close to the thick one (part of repeat sign)
    thin_barline_close = _LineSegment(x0=203.0, y0=50.0, x1=203.0, y1=150.0, stroke_width=1.0)

    segments = [standard_barline, thick_barline, thin_barline_close]

    # Extract
    extracted = extract_floating_barlines(segments, staff_top_y=40.0, staff_bottom_y=160.0)

    # Should merge the thick+thin into one, and keep the standard thin one separate.
    # Total extracted = 2
    assert len(extracted) == 2
    assert extracted[0].x0 == 100.0
    assert extracted[1].x0 == 200.0
