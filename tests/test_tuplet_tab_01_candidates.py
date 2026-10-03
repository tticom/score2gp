"""A TAB fret inside the notation zone must not become a tuplet number."""

from pathlib import Path

from score2gp.notation_omr import note_duration as nd


FIXTURES = Path(__file__).parent / "fixtures" / "pdf" / "dur_01"


def _fragment_tab_and_add_fret(symbols):
    # Break each public TAB line around a different fret position. The gaps
    # exceed find_staves' fragment merge reach, while each full row stays broad.
    tab_lines = [s for s in symbols.segments if s.horizontal and 115 <= s.y0 <= 153]
    assert len(tab_lines) == 6
    for row, segment in enumerate(tab_lines):
        left_end = 106 + 35 * row
        symbols.segments.remove(segment)
        symbols.segments.extend([
            nd.Segment(f"{segment.ident}-left", segment.x0, segment.y0, left_end, segment.y1, segment.width),
            nd.Segment(f"{segment.ident}-right", left_end + 28, segment.y0, segment.x1, segment.y1, segment.width),
        ])
    # On the first TAB line, the added digit is inside the unclamped notation
    # zone and aligns horizontally with notation event 2.
    symbols.texts.append(nd.Text("synthetic-fret", "7", (118, 115, 122, 119)))
    assert not nd.find_staves(symbols)[1]
    return symbols


def test_fret_on_tab_line_inside_unclamped_zone_is_not_a_tuplet(monkeypatch):
    original_extract = nd.extract_page_symbols

    def with_fret(page, page_index):
        return _fragment_tab_and_add_fret(original_extract(page, page_index))

    monkeypatch.setattr(nd, "extract_page_symbols", with_fret)
    result = nd.read_note_durations(FIXTURES / "half_and_32nds.pdf")
    assert result["events"][2]["status"] == "read"
    assert result["events"][2]["tuplet"] is None
    assert result["diagnostics"]["unassociated_numbers"] == 0


def test_real_printed_tuplet_with_group_remains_found():
    result = nd.read_note_durations(FIXTURES / "triplet.pdf")
    tuplets = [event["tuplet"] for event in result["events"] if event["tuplet"]]
    assert len(tuplets) == 6
    assert all(t["actual"] == 3 and t["normal"] == 2 for t in tuplets)
    assert len({t["group"] for t in tuplets}) == 2
    assert all(len(t["sources"]) == 3 for t in tuplets)  # printed number and its grouping marks


def test_removing_tab_row_rule_restores_the_unassociated_refusal(monkeypatch):
    original_extract = nd.extract_page_symbols

    def with_fret(page, page_index):
        return _fragment_tab_and_add_fret(original_extract(page, page_index))

    monkeypatch.setattr(nd, "extract_page_symbols", with_fret)
    monkeypatch.setattr(nd, "_on_tab_text_row", lambda text, rows: False, raising=False)
    result = nd.read_note_durations(FIXTURES / "half_and_32nds.pdf")
    assert result["events"][2]["reason"] == "tuplet_number_unassociated"
