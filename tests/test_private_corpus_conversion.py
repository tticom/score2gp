import tempfile
import zipfile
from pathlib import Path
import pytest

from score2gp.notation_omr.pipeline import run_recognition_on_file
from score2gp.gpif_builder import GPIFBuilder

# Private fixtures directory
PRIVATE_FIXTURES_DIR = Path("fixtures/private")

# PDFs that are known to pass perfectly in the current state of development
KNOWN_PASSING_PDFS = {
    "Lesson-5.pdf",
    "Lesson-6.pdf",
}

def get_private_pdfs():
    """Yields all PDFs in the private fixtures directory."""
    if not PRIVATE_FIXTURES_DIR.exists():
        return []
    return list(PRIVATE_FIXTURES_DIR.glob("*.pdf"))

# Create parameterized test cases
def pytest_generate_tests(metafunc):
    if "private_pdf_path" in metafunc.fixturenames:
        pdfs = get_private_pdfs()
        
        test_cases = []
        for pdf_path in pdfs:
            if pdf_path.name in KNOWN_PASSING_PDFS:
                # These must pass strictly
                test_cases.append(pytest.param(pdf_path, id=pdf_path.name))
            else:
                # These may fail due to unimplemented requirements (XFAIL)
                # strict=False allows them to pass without breaking the build (XPASS)
                # so developers know they can be moved to KNOWN_PASSING_PDFS
                test_cases.append(
                    pytest.param(
                        pdf_path, 
                        marks=pytest.mark.xfail(
                            strict=False, 
                            reason=f"Unimplemented requirements for {pdf_path.name}"
                        ),
                        id=pdf_path.name
                    )
                )
        metafunc.parametrize("private_pdf_path", test_cases)

def test_full_pdf_to_gp_conversion(private_pdf_path):
    """
    Comprehensive pipeline test for private PDFs.
    Passes each PDF through the OMR, ScoreIR generation, and GP binary writing.
    """
    res = run_recognition_on_file(private_pdf_path, assume_treble_clef=True)
    assert res is not None, f"OMR pipeline returned None for {private_pdf_path.name}"
    
    # Assert expected metadata
    assert "timeline_preview" in res, "OMR result missing timeline_preview"
    assert "fretboard_position_ownership" in res, "OMR result missing fretboard_position_ownership"

    # Build the ScoreIR
    builder = GPIFBuilder()
    score_ir = builder.compile_to_score_ir(
        bar_timelines=res.get("timeline_preview", []),
        position_ownership=res.get("fretboard_position_ownership", []),
    )
    
    assert score_ir is not None
    assert score_ir.semantic_contract_is_valid() is score_ir
    assert len(score_ir.tracks) >= 1, "Expected at least one track"
    assert len(score_ir.bars) >= 1, "Expected at least one bar"

    # Write the .gp binary file
    with tempfile.TemporaryDirectory() as tmpdir:
        out_gp = Path(tmpdir) / f"{private_pdf_path.stem}_out.gp"
        builder.write_gp_file(score_ir, out_gp)
        
        assert out_gp.exists(), "GP file was not created"
        assert out_gp.stat().st_size > 0, "GP file is empty"

        # Verify the structure of the resulting ZIP (GP) file
        with zipfile.ZipFile(out_gp, "r") as z:
            names = set(z.namelist())
            assert "VERSION" in names, "Missing VERSION in .gp binary"
            assert "Content/score.gpif" in names, "Missing Content/score.gpif in .gp binary"
