"""TS-READ-01 on genuine sources: the printed time signature is read, used, and never silently overridden.

These tests need the private corpus mounted in ``fixtures/private`` (CI mounts it); they fail, not skip, when
it is absent. Conversions run under ``<repo>/work`` in a ``tempfile.TemporaryDirectory`` (never pytest's
``tmp_path``: ``gpif.build_gpif`` writes a legacy layout when "pytest" is in a path).

No reference ``.gp`` exists for Combining_Maj_minor_pent_-_A: its conversion is asserted on what the PDF
prints (signature, bars written, refusal codes), not against a reference.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

from score2gp.notation_omr import note_duration, time_signature
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf_tab_bar_assembler import assemble_note_type_bars

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "fixtures/private"
COMBINING = PRIVATE / "Combining_Maj_minor_pent_-_A.pdf"
LESSONS = [PRIVATE / f"Lesson-{n}.pdf" for n in (3, 4, 5, 6, 7)]
OTHERS = [PRIVATE / "Gloria.pdf", PRIVATE / "Melodic_Expressions_Chap_19_.pdf"]
EXPECTED = {COMBINING: "12/8", **{path: "4/4" for path in LESSONS + OTHERS}}


def _require(path: Path) -> Path:
    assert path.is_file(), f"{path.name} is not mounted in fixtures/private"
    return path


@pytest.fixture(scope="module")
def printed_reads():
    """Each approved source read with no declared signature at all."""
    return {path: read_note_durations(_require(path)) for path in EXPECTED}


def _assert_printed(sidecar: dict, expected: str, name: str) -> None:
    checks = sidecar["bar_checks"]
    assert checks, name
    assert {c["time_signature"] for c in checks} == {expected}, name
    assert {c["time_signature_source"] for c in checks} == {"vector_glyphs"}, name
    bases = sidecar["diagnostics"]["bar_time_signatures"]
    assert {b["basis"] for b in bases.values()} == {"printed"}, name
    assert {b["declared"] for b in bases.values()} == {None}, name
    first = sidecar["diagnostics"]["time_signatures"][0]
    assert (first["status"], first["shape"], first["value"]) == ("read", "numerals", [int(p) for p in expected.split("/")]), name
    assert first["sources"] and first["location"]["page_index"] == 0, name


@pytest.mark.parametrize("path", sorted(EXPECTED), ids=lambda p: p.stem)
def test_the_printed_signature_is_read_without_any_flag(printed_reads, path):
    _assert_printed(printed_reads[path], EXPECTED[path], path.name)


def test_later_systems_without_a_printed_signature_carry_the_printed_one(printed_reads):
    sidecar = printed_reads[COMBINING]
    systems = sidecar["diagnostics"]["time_signatures"]
    assert [s["status"] for s in systems] == ["read", "absent"]
    origins = [b["origin"] for _, b in sorted(sidecar["diagnostics"]["bar_time_signatures"].items())]
    assert origins[0] == "system_start" and origins[-1] == "carried"


def _conflict_refusals(path: Path, declared: tuple[int, int], pages: tuple[int, int] | None) -> tuple[dict, dict]:
    sidecar = read_note_durations(_require(path), pages=pages, time_signature=declared)
    _, route = assemble_note_type_bars([], sidecar, track_id="t")
    return sidecar, route


def _assert_refused_naming_both(path: Path, printed: str, declared: tuple[int, int], pages) -> None:
    sidecar, route = _conflict_refusals(path, declared, pages)
    wrong = f"{declared[0]}/{declared[1]}"
    assert {c["status"] for c in sidecar["bar_checks"]} == {"signature_conflict"}, path.name
    assert route["summary"]["written_bars"] == 0 and route["summary"]["refused_bars"] == len(route["bars"]) > 0, path.name
    assert route["summary"]["refusal_reasons"] == {"time_signature_conflict": len(route["bars"])}, path.name
    for bar in route["bars"]:
        assert bar["status"] == "refused" and bar["reason"] == "time_signature_conflict", path.name
        assert printed in bar["detail"] and wrong in bar["detail"], bar["detail"]
        assert bar["time_signature"] == printed and bar["declared_time_signature"] == wrong
        assert bar["time_signature_basis"] == "printed"
        assert {"page_index", "system_index", "bar_index"} <= set(bar["location"]), path.name


def test_a_wrong_declared_value_on_combining_is_refused_naming_both_values():
    _assert_refused_naming_both(COMBINING, "12/8", (4, 4), None)


def test_a_wrong_declared_value_on_a_lesson_is_refused_naming_both_values():
    _assert_refused_naming_both(PRIVATE / "Lesson-5.pdf", "4/4", (3, 4), (1, 1))


def test_a_matching_declared_value_changes_nothing():
    sidecar = read_note_durations(_require(COMBINING), time_signature=(12, 8))
    assert {c["status"] for c in sidecar["bar_checks"]} <= {"match", "mismatch", "incomplete"}
    assert {b["basis"] for b in sidecar["diagnostics"]["bar_time_signatures"].values()} == {"printed"}
    assert {b["declared"] for b in sidecar["diagnostics"]["bar_time_signatures"].values()} == {"12/8"}


def _convert(pdf: Path, scratch: Path, *flags: str) -> tuple[subprocess.CompletedProcess, Path, Path]:
    output = scratch / "out.gp"
    work = scratch / "work"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "score2gp.cli", "convert", "--pdf", str(_require(pdf)), "--pdf-only-tab",
         *flags, "--out", str(output), "--work-dir", str(work)],
        text=True, capture_output=True, env=env,
    )
    return result, output, work


def _gpif(path: Path) -> bytes:
    with zipfile.ZipFile(path) as package:
        return package.read(next(n for n in package.namelist() if n.endswith(".gpif")))


def _scratch():
    (ROOT / "work").mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=ROOT / "work")


def test_combining_converts_under_its_printed_12_8_without_a_flag():
    with _scratch() as directory:
        result, output, work = _convert(COMBINING, Path(directory))
        assert result.returncode == 0, result.stderr[-1000:]
        route = json.loads((work / "note-type-route.json").read_text(encoding="utf-8"))
        # Measured: every one of the 8 bars is written and none is refused; no reference .gp exists for it.
        assert route["summary"]["source_bars"] == 8
        assert route["summary"]["written_bars"] == 8 and route["summary"]["refused_bars"] == 0
        assert route["summary"]["refusal_reasons"] == {}
        assert {b["time_signature"] for b in route["bars"]} == {"12/8"}
        assert {b["time_signature_basis"] for b in route["bars"]} == {"printed"}
        assert {b["time_signature_source"] for b in route["bars"]} == {"vector_glyphs"}
        gpif = _gpif(output).decode("utf-8")
        assert gpif.count("<Time>12/8</Time>") >= 8 and "<Time>4/4</Time>" not in gpif
        # Declaring the same printed value is the same conversion, byte for byte.
        declared = Path(directory) / "declared"
        declared.mkdir()
        again, declared_output, _ = _convert(COMBINING, declared, "--time-signature", "12/8")
        assert again.returncode == 0, again.stderr[-1000:]
        assert _gpif(declared_output) == _gpif(output)


def test_combining_with_a_wrong_declared_value_is_refused_not_converted_at_4_4():
    with _scratch() as directory:
        result, _, work = _convert(COMBINING, Path(directory), "--time-signature", "4/4")
        assert result.returncode != 0
        route = json.loads((work / "note-type-route.json").read_text(encoding="utf-8"))
        assert route["summary"]["written_bars"] == 0
        assert route["summary"]["refusal_reasons"] == {"time_signature_conflict": 8}
        assert all("12/8" in b["detail"] and "4/4" in b["detail"] for b in route["bars"])


@pytest.mark.parametrize("name", ["Lesson-5.pdf", "Tasty_A_Major_Lick.pdf"])
def test_a_converting_source_is_unchanged_by_dropping_its_flag(name):
    with _scratch() as directory:
        flagged_dir, bare_dir = Path(directory) / "flagged", Path(directory) / "bare"
        flagged_dir.mkdir()
        bare_dir.mkdir()
        flagged, flagged_out, _ = _convert(PRIVATE / name, flagged_dir, "--time-signature", "4/4")
        bare, bare_out, work = _convert(PRIVATE / name, bare_dir)
        assert flagged.returncode == 0 and bare.returncode == 0, bare.stderr[-1000:]
        assert _gpif(bare_out) == _gpif(flagged_out)
        route = json.loads((work / "note-type-route.json").read_text(encoding="utf-8"))
        assert {b["time_signature_basis"] for b in route["bars"]} == {"printed"}


# --- mutants: each wrong implementation must fail the real-file checks above ---------------------------------

def _real_file_checks() -> None:
    """The acceptance assertions on the real files, reduced to what the mutants can break."""
    _assert_printed(read_note_durations(_require(COMBINING)), "12/8", "Combining")
    _assert_printed(read_note_durations(_require(PRIVATE / "Lesson-5.pdf"), pages=(1, 1)), "4/4", "Lesson-5")
    _assert_refused_naming_both(COMBINING, "12/8", (4, 4), None)
    _assert_refused_naming_both(PRIVATE / "Lesson-5.pdf", "4/4", (3, 4), (1, 1))


def test_the_unmutated_reader_passes_the_real_file_checks():
    _real_file_checks()


def _reader_mutant(monkeypatch, edit):
    real = time_signature.read_system_time_signature

    def mutated(staff, symbols):
        result = real(staff, symbols)
        if result["status"] == "read" and result["shape"] == "numerals":
            result = edit(dict(result))
        return result

    monkeypatch.setattr(time_signature, "read_system_time_signature", mutated)


def test_mutant_always_use_the_declared_value_fails(monkeypatch):
    def always_declared(printed, origin, declared, unread):
        return {**declared, "basis": "caller_declared", "origin": None, "unread": unread} if declared else None

    monkeypatch.setattr(note_duration, "_governing_signature", always_declared)
    with pytest.raises(AssertionError):
        _real_file_checks()


def test_mutant_read_only_the_top_numeral_fails(monkeypatch):
    # Only the first numeral of the top row is used: 12 becomes 1.
    _reader_mutant(monkeypatch, lambda r: {**r, "numerator": int(str(r["numerator"])[0])})
    with pytest.raises(AssertionError):
        _real_file_checks()


def test_mutant_ignore_the_denominator_fails(monkeypatch):
    _reader_mutant(monkeypatch, lambda r: {**r, "denominator": 4})
    with pytest.raises(AssertionError):
        _real_file_checks()


def test_mutant_choose_silently_on_disagreement_fails(monkeypatch):
    real = note_duration._governing_signature

    def silent(printed, origin, declared, unread):
        signature = real(printed, origin, declared, unread)
        if signature:
            signature.pop("conflict", None)
        return signature

    monkeypatch.setattr(note_duration, "_governing_signature", silent)
    with pytest.raises(AssertionError):
        _real_file_checks()
