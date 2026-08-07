from __future__ import annotations

import json
from pathlib import Path
from typer.testing import CliRunner

from score2gp.cli import app
from score2gp.compare import (
    BarData,
    EventData,
    NoteData,
    compare_bar_scores,
    compact_bar_summary,
    format_mismatch_report,
    load_bar_data,
)
from score2gp.ir import (
    Bar,
    Event,
    KeySignature,
    Note,
    ScoreIR,
    Tempo,
    TimeSignature,
    Timing,
    Track,
    Tuning,
    TuningString,
)

runner = CliRunner()


def _make_sample_score_ir() -> ScoreIR:
    bar1 = Bar(
        index=1,
        time_signature=TimeSignature(numerator=4, denominator=4),
        key_signature=KeySignature(fifths=0, mode="major"),
        tempo=Tempo(bpm=120),
        layout_break="line",
        barline="regular",
        events=[
            Event(
                id="e1_1",
                track_id="t1",
                is_rest=True,
                timing=Timing(bar_index=1, onset_ticks=0, duration_ticks=960),
            ),
            Event(
                id="e1_2",
                track_id="t1",
                is_rest=False,
                timing=Timing(bar_index=1, onset_ticks=960, duration_ticks=960),
                notes=[Note(string=1, fret=3, pitch=67)],
            ),
            Event(
                id="e1_3",
                track_id="t1",
                is_rest=False,
                timing=Timing(bar_index=1, onset_ticks=1920, duration_ticks=1920),
                notes=[Note(string=2, fret=1, pitch=60)],
            ),
        ],
    )
    bar2 = Bar(
        index=2,
        time_signature=TimeSignature(numerator=4, denominator=4),
        key_signature=KeySignature(fifths=0, mode="major"),
        tempo=Tempo(bpm=120),
        barline="end",
        events=[
            Event(
                id="e2_1",
                track_id="t1",
                is_rest=False,
                timing=Timing(bar_index=2, onset_ticks=0, duration_ticks=3840),
                notes=[Note(string=1, fret=0, pitch=64)],
            ),
        ],
    )
    return ScoreIR(
        tempo=Tempo(bpm=120),
        tracks=[
            Track(
                id="t1",
                name="Guitar",
                tuning=Tuning(
                    name="Standard",
                    strings=[
                        TuningString(number=1, pitch=64, name="E4"),
                        TuningString(number=2, pitch=59, name="B3"),
                        TuningString(number=3, pitch=55, name="G3"),
                        TuningString(number=4, pitch=50, name="D3"),
                        TuningString(number=5, pitch=45, name="A2"),
                        TuningString(number=6, pitch=40, name="E2"),
                    ],
                ),
            )
        ],
        bars=[bar1, bar2],
    )


def test_bar_comparator_invariant_checker_valid():
    score = _make_sample_score_ir()
    result = compare_bar_scores(score, expected_source=None)

    assert result["mode"] == "invariant_check"
    assert result["matches"] is True
    assert result["total_bars_actual"] == 2
    assert result["first_mismatch"] is None
    assert len(result["mismatches"]) == 0
    assert len(result["bar_summary"]) == 2


def test_bar_comparator_invariant_checker_invalid():
    invalid_bar = BarData(
        bar_index=5,  # Out of sequence index (expected 1)
        time_signature=(0, 3),  # Invalid numerator and non-power of two denominator
        events=[
            EventData(event_type="note", onset_beats=2.0, duration_beats=-1.0, notes=[NoteData(pitch=150, string=15, fret=-2)]),
            EventData(event_type="note", onset_beats=0.0, duration_beats=1.0, notes=[NoteData(pitch=60, string=1, fret=0)]),
        ],
    )
    result = compare_bar_scores([invalid_bar], expected_source=None)

    assert result["mode"] == "invariant_check"
    assert result["matches"] is False
    assert len(result["mismatches"]) > 0
    assert result["first_mismatch"] is not None


def test_bar_comparator_matching_scores():
    score1 = _make_sample_score_ir()
    score2 = _make_sample_score_ir()

    result = compare_bar_scores(score1, score2)

    assert result["mode"] == "diagnostic_comparison"
    assert result["matches"] is True
    assert result["total_bars_actual"] == 2
    assert result["total_bars_expected"] == 2
    assert result["first_mismatch"] is None
    assert len(result["mismatches"]) == 0


def test_bar_comparator_event_mismatch():
    score_act = _make_sample_score_ir()
    score_exp = _make_sample_score_ir()

    act_dict = score_act.model_dump(mode="json")
    act_dict["bars"][1]["events"][0]["notes"][0]["pitch"] = 69
    act_dict["bars"][1]["events"][0]["notes"][0]["fret"] = 5

    result = compare_bar_scores(act_dict, score_exp)

    assert result["matches"] is False
    assert result["first_mismatch"] is not None
    assert result["first_mismatch"]["bar_index"] == 2
    assert "pitch" in result["first_mismatch"]["field"] or "fret" in result["first_mismatch"]["field"]
    assert result["first_mismatch"]["actual"] in (5, 69)
    assert result["first_mismatch"]["expected"] in (0, 64)


def test_bar_comparator_barline_and_layout_break_mismatch():
    b_act = BarData(bar_index=1, barline="double", system_break=True, page_break=False)
    b_exp = BarData(bar_index=1, barline="normal", system_break=False, page_break=False)

    result = compare_bar_scores([b_act], [b_exp])

    assert result["matches"] is False
    fields = [m["field"] for m in result["mismatches"]]
    assert "barline" in fields
    assert "system_break" in fields


def test_bar_comparator_bar_count_mismatch():
    score_act = _make_sample_score_ir()
    score_exp = ScoreIR(
        tempo=Tempo(bpm=120),
        tracks=score_act.tracks,
        bars=[score_act.bars[0]],
    )

    result = compare_bar_scores(score_act, score_exp)

    assert result["matches"] is False
    assert result["total_bars_actual"] == 2
    assert result["total_bars_expected"] == 1
    assert result["first_mismatch"]["field"] == "bar_count"


def test_bar_comparator_compact_summary():
    b = BarData(
        bar_index=1,
        time_signature=(3, 4),
        tempo=140.0,
        barline="double",
        system_break=True,
        events=[
            EventData(event_type="rest", onset_beats=0.0, duration_beats=1.0),
            EventData(event_type="note", onset_beats=1.0, duration_beats=1.5, is_dotted=True, dots=1, notes=[NoteData(pitch=64, string=1, fret=0)]),
        ],
    )
    summary = compact_bar_summary(b)

    assert summary["bar_index"] == 1
    assert summary["event_count"] == 2
    assert "R:0(1)" in summary["events_summary"]
    assert "N:1(1.5.)" in summary["events_summary"]


def test_bar_comparator_report_format():
    score_act = _make_sample_score_ir()
    score_exp = _make_sample_score_ir()

    act_dict = score_act.model_dump(mode="json")
    act_dict["bars"][0]["events"][1]["notes"][0]["pitch"] = 99

    result = compare_bar_scores(act_dict, score_exp)
    report_text = format_mismatch_report(result)

    assert "BAR-LEVEL COMPARISON REPORT" in report_text
    assert "FAIL (Mismatches Detected)" in report_text
    assert "FIRST MISMATCH:" in report_text
    assert "COMPACT BAR EVENT SUMMARY:" in report_text


def test_bar_comparator_cli_invariant_check(tmp_path: Path):
    score = _make_sample_score_ir()
    actual_path = tmp_path / "actual_ir.json"
    actual_path.write_text(score.model_dump_json(indent=2), encoding="utf-8")

    res = runner.invoke(app, ["compare-bars", str(actual_path)])
    assert res.exit_code == 0
    assert "BAR-LEVEL INVARIANT CHECK REPORT" in res.output
    assert "PASS (No Mismatches)" in res.output


def test_bar_comparator_cli_diagnostic_comparison(tmp_path: Path):
    score_act = _make_sample_score_ir()
    score_exp = _make_sample_score_ir()

    act_dict = score_act.model_dump(mode="json")
    act_dict["bars"][0]["events"][1]["notes"][0]["pitch"] = 99

    act_path = tmp_path / "act.json"
    exp_path = tmp_path / "exp.json"
    out_report = tmp_path / "report.json"

    act_path.write_text(json.dumps(act_dict, indent=2), encoding="utf-8")
    exp_path.write_text(score_exp.model_dump_json(indent=2), encoding="utf-8")

    res = runner.invoke(app, ["compare-bars", str(act_path), "--expected", str(exp_path), "--json", "--out", str(out_report)])
    assert res.exit_code == 1

    report_data = json.loads(out_report.read_text(encoding="utf-8"))
    assert report_data["matches"] is False
    assert report_data["mode"] == "diagnostic_comparison"
    assert report_data["first_mismatch"]["bar_index"] == 1
    assert report_data["first_mismatch"]["actual"] == 99
