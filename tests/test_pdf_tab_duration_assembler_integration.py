"""TAB-side duration evidence no longer sets a duration: the note-type records do.

Before DUR-02, ``assemble_pdf_tab_bar`` took a duration from TAB stem/beam/flag evidence
(``visual_morphology``), fell back to the equal-spacing grid for unstemmed events, and padded the bar
with rests. That evidence cites no symbol, so it does not meet DUR-01's standard, and DUR-01's records
replace it. Each old test has a replacement here, named in its docstring. The associator's own
extraction from the fixture is still asserted exactly.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import fitz  # type: ignore[import-not-found]
import pytest

from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_tabraw_only
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf import extract_tab
from score2gp.pdf_tab_bar_assembler import assemble_note_type_bars
from score2gp.pdf_tab_duration_associator import (
    BeamPrimitiveCandidate,
    FlagPrimitiveCandidate,
    SpatialBBox,
    StaffSystemContext,
    StemPrimitiveCandidate,
    resolve_tab_duration_evidence_for_events,
)
from score2gp.pdf_tab_duration_types import TabDurationEvidence
from score2gp.tabraw import make_tab_candidate

_spec = importlib.util.spec_from_file_location("pdf_tab_route_support", Path(__file__).with_name("test_pdf_tab_route_support.py"))
support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(support)
note, digit, records = support.note, support.digit, support.records

FIXTURE = Path("tests/fixtures/pdf/generated_pdf_tab_duration.pdf")
QUARTER = TabDurationEvidence(duration_name="quarter", duration_ticks=960, stem_present=True)
EIGHTH = TabDurationEvidence(duration_name="eighth", duration_ticks=480, stem_present=True, beam_count=1)
AMBIGUOUS = TabDurationEvidence(duration_name="ambiguous", duration_ticks=0, stem_present=True, source="ambiguous_conflict",
                                is_ambiguous=True, diagnostic_message="Conflicting stem geometry")


def _with_evidence(candidate, evidence):
    return make_tab_candidate(candidate_id=candidate.id, raw_text=candidate.raw_text, page_index=candidate.page_index,
                              bbox_values=[candidate.bbox.x0, candidate.bbox.y0, candidate.bbox.x1, candidate.bbox.y1],
                              confidence=candidate.confidence, system_index=1, staff_index=1, bar_index=1,
                              string=candidate.string, kind="fret", duration_evidence=evidence)


def _assemble(specs, digits):
    bars, route = assemble_note_type_bars(digits, records([[specs]]), track_id="t1")
    return bars[0], route["bars"][0]


def _fixture_evidence():
    pdf_path = Path("tests/fixtures/pdf/generated_pdf_tab_duration.pdf")
    assert pdf_path.exists()
    doc = fitz.open(pdf_path)
    page = doc[0]

    # Extract text-span event x-coordinates and fret numbers
    text_dict = page.get_text("dict")
    extracted_spans: list[tuple[float, str]] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "").strip()
                if txt.isdigit() and span.get("font") == "Courier":
                    bbox = span.get("bbox")
                    if bbox:
                        event_x = (bbox[0] + bbox[2]) / 2.0
                        extracted_spans.append((event_x, txt))

    extracted_spans.sort(key=lambda t: t[0])
    extracted_xs = [t[0] for t in extracted_spans]
    assert len(extracted_xs) == 12

    # Extract drawings
    stems: list[StemPrimitiveCandidate] = []
    beams: list[BeamPrimitiveCandidate] = []
    flags: list[FlagPrimitiveCandidate] = []
    drawing_lines: list[tuple[float, float, float, float]] = []

    for draw in page.get_drawings():
        for item in draw.get("items", []):
            if not item:
                continue
            itype = item[0]
            if itype == "l" and len(item) >= 3:
                p0, p1 = item[1], item[2]
                dx = abs(p0.x - p1.x)
                dy = abs(p0.y - p1.y)
                ix0, ix1 = min(p0.x, p1.x), max(p0.x, p1.x)
                iy0, iy1 = min(p0.y, p1.y), max(p0.y, p1.y)
                drawing_lines.append((ix0, iy0, ix1, iy1))

                if dy >= 5.0 and dx <= 2.0:
                    stems.append(StemPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1), is_downward=True))
                elif dy <= 1.0 and dx >= 7.0:
                    if not (149.0 <= iy0 <= 221.0 and dx > 300.0):
                        beams.append(BeamPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))
                elif dx >= 3.0 and dy >= 3.0:
                    flags.append(FlagPrimitiveCandidate(bbox=SpatialBBox(ix0, iy0, ix1, iy1)))

    staff_line_ys = sorted({round(iy0, 1) for (ix0, iy0, ix1, iy1) in drawing_lines if abs(iy0 - iy1) <= 1.0 and abs(ix1 - ix0) >= 300.0})
    staff_space = (staff_line_ys[-1] - staff_line_ys[0]) / (len(staff_line_ys) - 1)
    barline_xs = sorted({round((ix0 + ix1) / 2.0, 1) for (ix0, iy0, ix1, iy1) in drawing_lines if abs(ix0 - ix1) <= 1.0 and (iy1 - iy0) >= 60.0 and iy0 <= staff_line_ys[0] + 2.0 and iy1 >= staff_line_ys[-1] - 2.0})

    context = StaffSystemContext(
        line_y_coords=staff_line_ys,
        barline_x_coords=barline_xs,
        staff_space=staff_space,
    )
    ev_mapping = resolve_tab_duration_evidence_for_events(extracted_xs, stems, beams, flags, context)
    doc.close()
    return extracted_xs, ev_mapping


def test_pdf_tab_duration_assembler_oracle_integration(tmp_path):
    """Replaces the old oracle test. The associator still reads the fixture's TAB stems exactly (four
    quarters, then two flagged eighths, two beamed eighths and four sixteenths), but that evidence is no
    longer a duration source: the fixture has no notation staff, so it is refused, and no rest is ever
    added for the 960 ticks its second bar was short."""
    xs, mapping = _fixture_evidence()
    assert [mapping[x].duration_name for x in xs] == ["quarter"] * 4 + ["eighth"] * 4 + ["16th"] * 4
    assert all(mapping[x].source == "visual_morphology" for x in xs)
    tabraw = tmp_path / "tab_raw.json"
    extract_tab(FIXTURE, tabraw)
    with pytest.raises(BuildIrInputRiskError) as err:
        build_ir_from_tabraw_only(tabraw, note_durations=read_note_durations(FIXTURE, time_signature=(4, 4)))
    assert err.value.category == "pdf_only_tab_no_notation_bars"


def test_tab_evidence_never_overrides_the_note_type():
    """The records say eighths and a half; every TAB digit carries quarter evidence. The records win."""
    specs = [note(20.0, "eighth"), note(40.0, "eighth"), note(60.0, "quarter"), note(100.0, "half")]
    digits = [_with_evidence(digit(f"q{i}", 0, s["x"], 1, i), QUARTER) for i, s in enumerate(specs)]
    bar, entry = _assemble(specs, digits)
    assert entry["status"] == "written"
    assert [e.timing.duration_ticks for e in bar.events] == [480, 480, 960, 1920]


def test_unstemmed_fallback_preservation():
    """Replaces the old test (unstemmed digits became eighths and a half rest): an unstemmed notehead
    is an unread event, and its bar is refused."""
    specs = [note(20.0), note(60.0, unread="filled_notehead_without_stem"), note(100.0), note(140.0)]
    bar, entry = _assemble(specs, [digit(f"u{i}", 0, s["x"], 1, 3) for i, s in enumerate(specs)])
    assert bar.events == []
    assert (entry["reason"], entry["detail"], entry["location"]["event_index"]) == (
        "note_duration_event_unread", "filled_notehead_without_stem", 1)


def test_measure_capacity_enforcement_overcapacity():
    """Replaces the old test: five quarter notes in 4/4 refuse their bar, whatever the TAB evidence."""
    specs = [note(10.0 + 35.0 * i) for i in range(5)]
    digits = [_with_evidence(digit(f"o{i}", 0, s["x"], 6, 0), QUARTER) for i, s in enumerate(specs)]
    bar, entry = _assemble(specs, digits)
    assert (entry["status"], entry["reason"], entry["detail"]) == ("refused", "bar_total_mismatch", "5 of 4 quarters")
    assert bar.events == []


def test_ambiguous_duration_evidence_fail_closed():
    """Replaces the old test. An event whose note type is not read refuses its bar; ambiguous TAB
    evidence under an event whose note type is read changes nothing."""
    unread = [note(20.0, "whole", unread="flag_glyph_unidentified")]
    bar, entry = _assemble(unread, [_with_evidence(digit("a", 0, 20.0, 1, 5), AMBIGUOUS)])
    assert bar.events == [] and entry["reason"] == "note_duration_event_unread"
    bar, entry = _assemble([note(20.0, "whole")], [_with_evidence(digit("a", 0, 20.0, 1, 5), AMBIGUOUS)])
    assert entry["status"] == "written" and bar.events[0].timing.duration_ticks == 3840


def test_mixed_stemmed_and_unstemmed_subgroup_behavior():
    """Replaces the old test (stemmed 960, unstemmed 480 from the grid): both come from their records."""
    specs = [note(20.0, "half"), note(100.0, "half")]
    digits = [_with_evidence(digit("m1", 0, 20.0, 1, 3), QUARTER), digit("m2", 0, 100.0, 1, 5)]
    bar, entry = _assemble(specs, digits)
    assert entry["status"] == "written" and [e.timing.duration_ticks for e in bar.events] == [1920, 1920]


def test_matching_multi_string_chord_duration_evidence():
    """Replaces the old test: a three-note chord is one event with the record's duration."""
    digits = [_with_evidence(digit(f"s{s}", 0, 20.0, s, f), QUARTER) for s, f in ((1, 0), (2, 1), (3, 0))]
    bar, entry = _assemble([note(20.0, "whole", heads=3)], digits)
    assert entry["status"] == "written"
    assert [(n.string, n.fret) for n in bar.events[0].notes] == [(1, 0), (2, 1), (3, 0)]
    assert bar.events[0].timing.notated_duration.value == "whole"


def test_conflicting_multi_string_chord_duration_evidence_fails_closed():
    """Replaces the old test: conflicting TAB evidence no longer decides anything; a chord whose
    noteheads the reader could not read as one value is unread, and refuses its bar."""
    digits = [_with_evidence(digit("c1", 0, 20.0, 1, 0), QUARTER), _with_evidence(digit("c2", 0, 20.0, 2, 1), EIGHTH)]
    bar, entry = _assemble([note(20.0, "whole", heads=2, unread="mixed_notehead_kinds")], digits)
    assert bar.events == [] and (entry["reason"], entry["detail"]) == ("note_duration_event_unread", "mixed_notehead_kinds")
    bar, entry = _assemble([note(20.0, "whole", heads=2)], digits)
    assert entry["status"] == "written" and bar.events[0].timing.duration_ticks == 3840
