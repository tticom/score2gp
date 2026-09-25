"""Real-source acceptance tests for the L3-NATIVE (Lesson 3) slice.

These use the original Lesson 3 PDF and its Guitar Pro reference from the private corpus and assert only
public-safe facts (hashes, counts, statuses). A missing corpus FAILS, matching the repository's mandatory
real-source tests. The end-to-end coordinator run additionally needs the private adjudicated manifest
(a local ignored artefact, never committed) and an enforced read boundary; when the manifest is not
mounted that single test is skipped with an explicit reason, and the harness's refusal to run without an
oracle is asserted separately in ``test_native_slice_acceptance.py``.

``HARNESS_VERIFIED`` means the measurement was trustworthy. It is not ``L3_NATIVE_ACHIEVED``: the
acceptance is intentionally red while the native pipeline is being built.
"""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import native_slice_acceptance as acceptance  # noqa: E402
import native_slice_reference as reference  # noqa: E402

PDF_SHA256 = "fbd44cefad9e33adac992a5bd73c5cc46202c7cfc64d0586bb94cf42d3b41004"
GP_SHA256 = "9e1ca7b682ecce6b401da83820020650b8a3c122807c51b37029dc441c36516d"
SIBLING = ROOT.parent / "score2gp-private-fixtures" / "fixtures" / "private"
CORPUS = SIBLING if SIBLING.exists() else ROOT / "fixtures" / "private"
ORACLE = Path(os.environ.get("SCORE2GP_L3_ORACLE", ROOT / "work" / "l3-oracle" / "manifest.json"))


def corpus_file(name: str) -> Path:
    path = CORPUS / name
    assert path.is_file(), f"mandatory real-source corpus file is unavailable: {name}; CI must mount score2gp-private-fixtures"
    return path


@pytest.fixture(scope="module")
def source_pdf() -> Path:
    return corpus_file("Lesson-3.pdf")


@pytest.fixture(scope="module")
def reference_gp() -> Path:
    return corpus_file("Lesson-3.gp")


@pytest.fixture(scope="module")
def real_reference(reference_gp: Path) -> dict[str, Any]:
    return reference.expand(reference.read_gpif(reference_gp))


def events(doc: dict[str, Any]) -> list[tuple[int, int, dict[str, Any]]]:
    return [(m["index"], i, e) for m in doc["measures"] for i, e in enumerate(m["staves"][0]["voices"][0]["events"])]


def test_source_files_are_the_pinned_lesson3_inputs(source_pdf: Path, reference_gp: Path) -> None:
    assert reference.file_sha256(source_pdf) == PDF_SHA256
    assert reference.file_sha256(reference_gp) == GP_SHA256


def test_independent_reader_matches_the_planned_occurrence_aggregates(real_reference: dict[str, Any]) -> None:
    stats = real_reference["stats"]
    # Occurrence counts come from expanding reused records; definitions are far fewer than occurrences.
    assert (stats["measures"], stats["beat_occurrences"], stats["note_occurrences"]) == (66, 465, 473)
    assert (stats["rest_occurrences"], stats["chord_occurrences"]) == (2, 2)
    assert (stats["definitions"]["beats"], stats["definitions"]["notes"]) == (94, 30)
    assert stats["unreferenced_definitions"] == {k: 0 for k in ("bars", "voices", "beats", "notes", "rhythms")}
    assert real_reference["conventions"]["tuning_low_to_high"] == [40, 45, 50, 55, 59, 64]
    assert real_reference["stats"] == reference.expand(reference.read_gpif(CORPUS / "Lesson-3.gp"))["stats"]


def test_pdf_topology_is_measured_without_the_reference_and_agrees_with_it(source_pdf: Path, real_reference: dict[str, Any]) -> None:
    topology = reference.source_topology(source_pdf)
    assert topology["independent_of_reference"] is True
    assert (topology["pages"], topology["systems_total"]) == (4, 23)
    assert topology["measures_per_page"] == [15, 22, 19, 10]
    assert topology["measures_total"] == len(real_reference["measures"]) == 66
    assert all(system["measures"] >= 1 for system in topology["systems"])
    first = topology["systems"][0]
    assert (first["page"], first["system"], first["measures"]) == (1, 1, 3)
    # Stems that span the whole notation staff exist in the first system and must NOT be counted as barlines.
    assert first["notation_full_height_stem_xs"], "expected full-height note stems that the paired-staff rule must exclude"
    assert len(first["barline_xs"]) == first["measures"] + 1


def _first(doc: dict[str, Any], predicate: Any) -> tuple[int, int, dict[str, Any]]:
    return next(item for item in events(doc) if predicate(item[2]))


@pytest.mark.parametrize(
    ("label", "find", "mutate", "layer"),
    [
        ("fret", lambda e: e["notes"], lambda e: e["notes"][0].__setitem__("fret", e["notes"][0]["fret"] + 1), "notes"),
        ("string", lambda e: e["notes"], lambda e: e["notes"][0].__setitem__("string", (e["notes"][0]["string"] + 1) % 6), "notes"),
        ("rest becomes note", lambda e: e["kind"] == "rest", lambda e: e.__setitem__("kind", "note"), "events"),
        ("chord member dropped", lambda e: len(e["notes"]) > 1, lambda e: e["notes"].pop(), "notes"),
        ("dot removed", lambda e: e["dots"], lambda e: e.__setitem__("dots", 0), "events"),
        ("arpeggio removed", lambda e: e["arpeggio"], lambda e: e.__setitem__("arpeggio", None), "events"),
        ("section label changed", lambda e: e["text"], lambda e: e.__setitem__("text", e["text"] + "!"), "events"),
        ("duration changed", lambda e: e["kind"] == "note", lambda e: e.__setitem__("duration", "1/8"), "events"),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_real_source_oracle_rejects_a_known_bad_result(real_reference: dict[str, Any], label: str, find: Any, mutate: Any, layer: str) -> None:
    mutated = copy.deepcopy(real_reference)
    _, _, event = _first(mutated, find)
    mutate(event)
    result = reference.compare(real_reference, mutated)
    assert not result["equal"] and result["layers"][layer] == "FAIL", label
    assert reference.compare(real_reference, copy.deepcopy(real_reference))["equal"]  # the identical result still passes


def test_real_source_oracle_detects_structure_mutations(real_reference: dict[str, Any]) -> None:
    final = copy.deepcopy(real_reference)
    final["measures"][-1]["double_bar"] = not final["measures"][-1]["double_bar"]
    dropped = copy.deepcopy(real_reference)
    dropped["measures"].pop()
    for bad in (final, dropped):
        assert not reference.compare(real_reference, bad)["equal"]


@pytest.mark.skipif(not ORACLE.is_file(), reason=(
    "private adjudicated manifest is not mounted (local ignored artefact: build it with "
    "scripts/native_slice_reference.py build-manifest, or set SCORE2GP_L3_ORACLE); without it the harness "
    "refuses to run, which is asserted in test_native_slice_acceptance.py"))
def test_baseline_red_is_verified_and_exactly_classified(source_pdf: Path, reference_gp: Path, tmp_path: Path) -> None:
    """Runs the real CLI on the original PDF inside the read boundary and asserts today's classified red result.

    This asserts the *baseline* failure so a harness regression is caught. It must be revisited, not
    weakened, when the seam it points at is fixed.

    L3-01 fixed the first-system barline seam: the topology now matches the source exactly (4 of 4
    boundaries, 3 bar boxes, grouped). The product is still red, and the earliest remaining refusal
    is timing gating (``pdf_only_tab_missing_timing_evidence``).
    """
    out = tmp_path / "acceptance"
    args = acceptance.build_parser().parse_args([
        "--pdf", str(source_pdf), "--oracle", str(ORACLE), "--out-dir", str(out), "--protect", str(reference_gp),
        "--isolation", "windows-file-lock"])
    created: list[Path] = []
    code, receipt = acceptance.run(args, created)
    if os.name != "nt":
        assert code == acceptance.EXIT_REFUSED and receipt["public_summary"]["refusal_code"] == "ISOLATION_UNAVAILABLE"
        return
    public = receipt["public_summary"]
    assert code == acceptance.EXIT_RED, receipt.get("harness_refusal")
    assert (receipt["harness"], receipt["product"]) == ("HARNESS_VERIFIED", "L3_NATIVE_NOT_ACHIEVED")
    assert public["source_pdf_sha256"] == PDF_SHA256
    assert public["isolation"]["all_unreadable"] and public["isolation"]["control_readable"]
    assert public["runtime"]["import_path_controlled"] is True
    generation = public["generation"]
    assert generation["conversion"] == "NOT_CONVERTED" and not generation["output_written"]
    assert generation["semantic"] == "NOT_EVALUATED" and generation["application"] == "NOT_EVALUATED"
    assert generation["exit_code"] == 2
    assert (generation["stage"], generation["refusal_code"]) == ("timing-gating", "pdf_only_tab_missing_timing_evidence")
    divergence = public["first_system_divergence"]
    assert divergence["status"] == "TOPOLOGY_MATCHES_SOURCE" and divergence["kind"] is None
    counts = divergence["counts"]
    assert (counts["measures_expected"], counts["expected_boundaries"]) == (3, 4)
    assert counts["observed_boundaries"] == counts["expected_boundaries"] == 4
    assert counts["missing"] == counts["extra"] == counts["extra_on_notation_stem"] == 0
    assert counts["bar_boxes_observed"] == counts["measures_expected"] == 3
    assert counts["grouping_status"] == "grouped"
    assert "private_detail" not in public and "private" not in divergence  # coordinates and values stay in the private receipt
    assert set(receipt["private_detail"]["first_system_divergence"]) == {"expected_xs", "observed_xs", "extra_xs", "missing_xs"}
