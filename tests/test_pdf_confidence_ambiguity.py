import pytest
# Assuming internal imports based on previous pipeline architecture
from score2gp.pdf import process_pdf_text_grouping, TabRawCandidate

def create_mock_system_and_bar():
    # Helper to mock a standard 6-string tab staff and a single bar box
    string_lines = [700.0, 706.0, 712.0, 718.0, 724.0, 730.0]
    return string_lines, {"x0": 50.0, "x1": 200.0}

def test_pdf_fret_digit_symbol_overlap_ambiguous():
    """Test that a digit overlapping with a technique symbol (e.g., 'b') is flagged."""
    string_lines, bar = create_mock_system_and_bar()
    
    # Digit '12' overlapping with technique text 'b'
    candidates = [
        TabRawCandidate(text="12", x0=100.0, x1=110.0, y_min=705.0, y_max=715.0),
        TabRawCandidate(text="b", x0=108.0, x1=115.0, y_min=705.0, y_max=715.0) # Overlaps X
    ]
    
    result, warnings = process_pdf_text_grouping(candidates, string_lines, bars=[bar], strip_technique_text=False)
    
    assert result.grouping_status == "partial"
    assert "pdf_fret_digit_symbol_overlap_ambiguous" in [w.code for w in warnings]

def test_pdf_fret_digits_not_merged_gap_too_large():
    """Test that adjacent digits spaced beyond the max_digit_gap are flagged."""
    string_lines, bar = create_mock_system_and_bar()
    
    # '1' and '2' spaced 6.0 points apart (default max_digit_gap is usually 2.0 or 4.5)
    candidates = [
        TabRawCandidate(text="1", x0=100.0, x1=104.0, y_min=705.0, y_max=715.0),
        TabRawCandidate(text="2", x0=110.0, x1=114.0, y_min=705.0, y_max=715.0)
    ]
    
    result, warnings = process_pdf_text_grouping(candidates, string_lines, bars=[bar], max_digit_gap=4.5)
    
    assert result.grouping_status == "partial"
    assert "pdf_fret_digits_not_merged_gap_too_large" in [w.code for w in warnings]

def test_pdf_string_assignment_compact_staff_ambiguous():
    """Test that a candidate sitting exactly halfway between two string lines triggers ambiguity."""
    string_lines, bar = create_mock_system_and_bar()
    
    # String 1 is at 700.0, String 2 is at 706.0. Midpoint is 703.0.
    # A candidate perfectly centered at 703.0 should fail unambiguous assignment if snap tolerance is strict.
    candidates = [
        TabRawCandidate(text="5", x0=100.0, x1=105.0, y_min=700.0, y_max=706.0) # y_center = 703.0
    ]
    
    result, warnings = process_pdf_text_grouping(candidates, string_lines, bars=[bar], string_snap_tolerance=1.5)
    
    assert result.grouping_status == "partial"
    assert "pdf_string_assignment_compact_staff_ambiguous" in [w.code for w in warnings]

def test_pdf_fret_optical_bounds_confidence_below_threshold():
    """Test that a candidate with bizarre aspect ratios is rejected for low confidence."""
    string_lines, bar = create_mock_system_and_bar()
    
    # A text candidate claiming to be a digit but with a 50x50 bounding box (highly unusual for a standard font)
    candidates = [
        TabRawCandidate(text="3", x0=100.0, x1=150.0, y_min=680.0, y_max=730.0)
    ]
    
    result, warnings = process_pdf_text_grouping(candidates, string_lines, bars=[bar])
    
    assert result.grouping_status == "partial"
    assert "pdf_fret_optical_bounds_confidence_below_threshold" in [w.code for w in warnings]

def test_confidence_safe_counterpart():
    """Test that a well-spaced, standard aspect-ratio candidate passes cleanly."""
    string_lines, bar = create_mock_system_and_bar()
    
    # Perfectly centered on the 700.0 line, normal dimensions
    candidates = [
        TabRawCandidate(text="7", x0=100.0, x1=105.0, y_min=697.0, y_max=703.0)
    ]
    
    result, warnings = process_pdf_text_grouping(candidates, string_lines, bars=[bar])
    
    assert result.grouping_status == "grouped"
    warning_codes = [w.code for w in warnings]
    assert "partial_pdf_grouping" not in warning_codes