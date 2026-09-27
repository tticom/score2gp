"""Synthetic note-duration records and TAB digits for unit tests of the note-type route.

``records`` builds a ``note-duration-records`` document shaped like the DUR-01 reader's output, one
system per page, and ``digit`` builds a TAB fret candidate placed under a notation event. The test
below keeps the synthetic records in step with the reader's real output shape.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from score2gp.notation_omr.note_duration import SCHEMA, WRITTEN_VALUES
from score2gp.tabraw import TabCandidate, make_tab_candidate

SPACE = 4.0
PAGE_HEIGHT = 800.0
STAFF_TOP = 100.0
BAR_X0 = 50.0
BAR_WIDTH = 200.0
TAB_TOP = STAFF_TOP + 4 * SPACE + 30.0
TAB_GAP = 6.0


def event_x(bar_in_system: int, x: float) -> float:
    return BAR_X0 + bar_in_system * BAR_WIDTH + x


def note(x: float, written: str = "quarter", *, dots: int = 0, heads: int = 1, tuplet: tuple[int, int] | None = None,
         tie: tuple[bool, bool] = (False, False), unread: str | None = None) -> dict[str, Any]:
    return {"kind": "chord" if heads > 1 else "note", "x": x, "written": written, "dots": dots, "heads": heads,
            "tuplet": tuplet, "tie": tie, "unread": unread}


def rest(x: float, written: str = "quarter", *, dots: int = 0) -> dict[str, Any]:
    return {"kind": "rest", "x": x, "written": written, "dots": dots, "heads": 0, "tuplet": None,
            "tie": (False, False), "unread": None}


def _record(spec: dict[str, Any], page: int, bar: int, bar_in_system: int, index: int) -> dict[str, Any]:
    cx = event_x(bar_in_system, spec["x"])
    location = {"page_index": page, "system_index": 0, "bar_index": bar, "event_index": index,
                "bbox": [cx - 2.5, STAFF_TOP + 4, cx + 2.5, STAFF_TOP + 8]}
    record: dict[str, Any] = {
        "page_index": page, "system_index": 0, "system_number": page, "bar_index": bar, "bar_in_system": bar_in_system,
        "event_index": index, "kind": spec["kind"], "status": "read", "reason": None, "location": location,
        "notehead": None if spec["kind"] == "rest" else {"kind": "filled", "count": spec["heads"], "sources": []},
        "stem": None, "flags": {"count": 0, "glyphs": []},
        "beams": {"count": 0, "sources": [], "group": None, "group_size": 0},
        "dots": {"count": spec["dots"], "sources": []},
        "rest": {"glyph": spec["written"], "source": "r"} if spec["kind"] == "rest" else None,
        "tuplet": ({"actual": spec["tuplet"][0], "normal": spec["tuplet"][1], "sources": []} if spec["tuplet"] else None),
        "tie": {"start": spec["tie"][0], "stop": spec["tie"][1], "sources": []},
        "written": None, "value_quarters": None, "duration_quarters": None,
    }
    if spec["unread"]:
        record.update(status="unread", reason=spec["unread"])
        return record
    value = WRITTEN_VALUES[spec["written"]] * (2 - Fraction(1, 2 ** spec["dots"]))
    duration = value * Fraction(spec["tuplet"][1], spec["tuplet"][0]) if spec["tuplet"] else value
    record.update(written=spec["written"], value_quarters=str(value), duration_quarters=str(duration))
    return record


def records(pages: list[list[list[dict[str, Any]]]], *, time_signature: str | None = "4/4") -> dict[str, Any]:
    """``pages[p][b]`` is the event list of bar ``b`` of the one system on page ``p``."""
    events, systems, checks = [], [], []
    bar = 0
    for page, bars in enumerate(pages):
        systems.append({"page_index": page, "system_index": 0, "system_number": page, "first_bar_index": bar,
                        "bar_count": len(bars), "staff_space": SPACE,
                        "staff": {"top": STAFF_TOP, "bottom": STAFF_TOP + 4 * SPACE, "x0": BAR_X0,
                                  "x1": BAR_X0 + len(bars) * BAR_WIDTH},
                        "bars": [[BAR_X0 + i * BAR_WIDTH, BAR_X0 + (i + 1) * BAR_WIDTH] for i in range(len(bars))]})
        for bar_in_system, specs in enumerate(bars):
            bar_records = [_record(spec, page, bar, bar_in_system, i) for i, spec in enumerate(specs)]
            events.extend(bar_records)
            unread = sum(1 for r in bar_records if r["status"] != "read")
            total = sum((Fraction(r["duration_quarters"]) for r in bar_records if r["status"] == "read"), Fraction(0))
            check = {"bar_index": bar, "events": len(bar_records), "unread_events": unread, "total_quarters": str(total),
                     "time_signature": time_signature, "time_signature_source": "text_glyphs" if time_signature else None,
                     "expected_quarters": None}
            if time_signature:
                numerator, denominator = (int(v) for v in time_signature.split("/"))
                check["expected_quarters"] = str(Fraction(4 * numerator, denominator))
            if unread:
                check["status"] = "incomplete"
            elif not time_signature:
                check["status"] = "time_signature_unread"
            else:
                check["status"] = "match" if str(total) == check["expected_quarters"] else "mismatch"
            checks.append(check)
            bar += 1
    return {"schema": SCHEMA, "source": {"pdf_sha256": "0" * 64, "pages": None, "page_heights": [PAGE_HEIGHT] * len(pages)},
            "systems": systems, "events": events, "bar_checks": checks, "summary": {}, "diagnostics": {}}


def digit(ident: str, bar_in_system: int, x: float, string: int, fret: int, *, page: int = 0) -> TabCandidate:
    """A TAB fret digit under ``x`` of a bar; its y runs on down the document, as TabRaw's does."""
    cx = event_x(bar_in_system, x)
    y = page * PAGE_HEIGHT + TAB_TOP + (string - 1) * TAB_GAP
    return make_tab_candidate(candidate_id=ident, raw_text=str(fret), page_index=page + 1,
                              bbox_values=[cx - 2.0, y - 3.0, cx + 2.0, y + 3.0], confidence=0.9,
                              system_index=1, staff_index=1, bar_index=1, string=string, kind="fret")


def test_synthetic_records_have_the_readers_shape(tmp_path):
    import importlib.util
    from pathlib import Path

    from score2gp.notation_omr.note_duration import read_note_durations

    path = Path(__file__).resolve().parent / "test_dur_02_note_type_route.py"
    spec = importlib.util.spec_from_file_location("dur_02_route", path)
    route = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(route)
    real = read_note_durations(route.clean_pdf(tmp_path / "clean.pdf"))
    synthetic = records([[[note(20.0)]]])
    assert set(synthetic) == set(real) and set(synthetic["source"]) == set(real["source"])
    assert set(synthetic["systems"][0]) == set(real["systems"][0])
    assert set(synthetic["systems"][0]["staff"]) == set(real["systems"][0]["staff"])
    assert set(synthetic["events"][0]) == set(real["events"][0])
    assert set(synthetic["events"][0]["location"]) == set(real["events"][0]["location"])
    assert set(synthetic["bar_checks"][0]) == set(real["bar_checks"][0])
