"""Real-source bare P.M. marks, REFUSE-19.

The one-page cut is from the approved source, not a generated musical fixture.
Synthetic tests carry no acceptance weight. DROP_BARE_PALM_MARK_READER
must fail the same written-bar assertion. No reference GP exists for this
source; output is checked against the printed page, not independently verified.
"""
import json
from pathlib import Path
import tempfile

import pymupdf
import pytest
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp import pdf_tab_digit_recovery as recovery


SOURCE = Path(__file__).resolve().parents[1] / "fixtures/private/Melodic_Expressions.pdf"
NEW_BARS = (4,)


def _convert(tmp_path):
    assert SOURCE.is_file(), "REQUIRED_REFUSE_19_SOURCE_MISSING"
    with pymupdf.open(SOURCE) as source, pymupdf.open() as cut:
        cut.insert_pdf(source, from_page=6, to_page=6)
        # The legacy extractor gives paths containing 'test' a generated-input route.
        with tempfile.TemporaryDirectory(prefix="r19_") as neutral:
            pdf = Path(neutral) / "page.pdf"
            assert "test" not in str(pdf).lower(), "REAL_SOURCE_ROUTE_REQUIRED"
            cut.save(pdf)
            work = tmp_path / "build"
            result = CliRunner().invoke(app, [
                "convert", "--pdf", str(pdf), "--pdf-only-tab", "--out", str(tmp_path / "output.gp"),
                "--work-dir", str(work),
            ])
    assert result.exit_code == 0, f"REFUSE_19_CLI_EXIT_{result.exit_code}"
    route = json.loads((work / "note-type-route.json").read_bytes())
    ir = json.loads((work / "score.ir.json").read_bytes())
    return {b["source_bar_index"]: b for b in route["bars"]}, ir


def _check_written(converted):
    route, ir = converted
    bars = {b["index"]: b for b in ir["bars"]}
    for index in NEW_BARS:
        entry = route[index]
        assert entry["status"] == "written", f"BAR_{index}_STILL_REFUSED"
        events = bars[entry["output_bar_index"]]["events"]
        assert len(events) == entry["notation_events"], "TAB_ANNOTATION_ADDED_AN_EVENT"
        assert len(events) == 4 and sum(len(e["notes"]) for e in events) == 4, "PRINTED_EVENT_COUNTS_CHANGED"
        assert sum(e["is_rest"] for e in events) == 2, "PRINTED_RESTS_CHANGED"
        assert not any(n["techniques"] for e in events for n in e["notes"]), "NEIGHBOURING_BAR_MARKS_LEAKED"
    return route


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    return _convert(tmp_path_factory.mktemp("r19_tied"))


def test_read_bare_palm_marks_do_not_refuse_a_clear_bar_in_the_staff(converted):
    """Reject DROP_BARE_PALM_MARK_READER on the real-source CLI output."""
    _check_written(converted)


def _check_refused(converted):
    route, _ = converted
    for index in (2, 3, 5, 6):
        assert route[index]["status"] == "refused", f"BAR_{index}_OTHER_UNREAD_EVIDENCE_LOST"


def test_other_unread_marks_and_spans_still_refuse_their_bars(converted):
    """Reject treating every parenthesized token or every TAB mark as harmless."""
    _check_refused(converted)


def test_allow_any_parenthesized_number_would_write_unfinished_bars(converted, tmp_path, monkeypatch):
    """Reject ALLOW_ANY_PARENTHESIS: printed vibrato on these bars is still unread."""
    _check_refused(converted)
    monkeypatch.setattr(recovery, "_unread_number_word", lambda *a: None)
    with pytest.raises(AssertionError, match="OTHER_UNREAD_EVIDENCE_LOST"):
        _check_refused(_convert(tmp_path))


def test_drop_bare_palm_mark_reader_fails(converted, tmp_path, monkeypatch):
    _check_written(converted)
    original = recovery._palm_spans
    monkeypatch.setattr(recovery, "_palm_spans", lambda *a: original(*a[:-1]))
    with pytest.raises(AssertionError, match="STILL_REFUSED"):
        _check_written(_convert(tmp_path))


def test_drop_number_and_tab_mark_guards_fails(converted, tmp_path, monkeypatch):
    _check_refused(converted)
    monkeypatch.setattr(recovery, "_unread_number_word", lambda *a: None)
    monkeypatch.setattr(recovery, "_unread_tab_ink", lambda *a: False)
    with pytest.raises(AssertionError, match="OTHER_UNREAD_EVIDENCE_LOST"):
        _check_refused(_convert(tmp_path))
