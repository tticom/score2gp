"""Infrastructure and negative controls for the L3-NATIVE acceptance harness.

Rationale for synthetic data: these tests exercise the oracle reader, the comparator, the manifest
gate and the coordinator's classification and isolation logic. They make no recognition, conversion,
timing or fidelity claim; that evidence lives in ``test_lesson3_native_acceptance.py`` and uses the real
source. The fake ``score2gp`` package below only lets the coordinator's own behaviour be observed.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import native_slice_acceptance as acceptance  # noqa: E402
import native_slice_reference as reference  # noqa: E402

TUNING = [40, 45, 50, 55, 59, 64]
EIGHTHS = [(0, 3), (1, 2), (1, 5), (2, 5), (3, 4), (4, 3), (5, 3), (5, 7)]


def eighth(note: tuple[int, int], **extra: Any) -> dict[str, Any]:
    return {"v": "Eighth", "notes": [note], **extra}


def two_bar_score() -> list[list[dict[str, Any]]]:
    """Bar 1: eight eighths (first labelled). Bar 2: dotted half + quarter, a chord (arpeggiated) is bar 3."""
    first = [eighth(n) for n in EIGHTHS]
    first[0]["text"] = "Section A"
    second = [{"v": "Half", "dots": 1, "notes": [(0, 3)]}, {"v": "Quarter", "notes": []}]
    third = [{"v": "Whole", "notes": [(0, 3), (2, 5), (3, 5)], "arp": "Down"}]
    return [first, first, second, third]


def gpif(measures: list[list[dict[str, Any]]], *, id_shift: int = 0, reverse: bool = False, double_last: bool = True,
         title: str = "Synthetic", tempo: int = 120) -> str:
    """A small GPIF document with real id reuse (identical bars/voices/beats/notes share one definition)."""
    tables: dict[str, dict[Any, int]] = {k: {} for k in ("note", "rhythm", "beat", "voice", "bar")}

    def rid(kind: str, key: Any) -> int:
        table = tables[kind]
        if key not in table:
            table[key] = len(table) + id_shift
        return table[key]

    masters = []
    for beats in measures:
        beat_ids = []
        for beat in beats:
            rhythm = rid("rhythm", (beat["v"], beat.get("dots", 0)))
            notes = tuple(rid("note", n) for n in beat.get("notes", []))
            beat_ids.append(rid("beat", (rhythm, notes, beat.get("arp"), beat.get("text"))))
        masters.append(rid("bar", rid("voice", tuple(beat_ids))))

    def emit(kind: str, render: Any) -> str:
        items = sorted(tables[kind].items(), key=lambda kv: kv[1], reverse=reverse)
        return "".join(render(key, value) for key, value in items)

    note_xml = lambda key, i: (  # noqa: E731
        f'<Note id="{i}"><InstrumentArticulation>0</InstrumentArticulation><Properties>'
        f'<Property name="ConcertPitch"><Pitch><Step>G</Step><Accidental/><Octave>3</Octave></Pitch></Property>'
        f'<Property name="Fret"><Fret>{key[1]}</Fret></Property>'
        f'<Property name="Midi"><Number>{TUNING[key[0]] + key[1]}</Number></Property>'
        f'<Property name="String"><String>{key[0]}</String></Property>'
        f'<Property name="TransposedPitch"><Pitch><Step>G</Step><Accidental/><Octave>4</Octave></Pitch></Property>'
        f"</Properties></Note>")
    rhythm_xml = lambda key, i: (  # noqa: E731
        f'<Rhythm id="{i}"><NoteValue>{key[0]}</NoteValue>'
        + (f'<AugmentationDot count="{key[1]}"/>' if key[1] else "") + "</Rhythm>")
    beat_xml = lambda key, i: (  # noqa: E731
        f'<Beat id="{i}"><Dynamic>MF</Dynamic><Rhythm ref="{key[0]}"/>'
        + (f"<FreeText>{key[3]}</FreeText>" if key[3] else "")
        + (f"<Arpeggio>{key[2]}</Arpeggio>" if key[2] else "")
        + (f'<Notes>{" ".join(map(str, key[1]))}</Notes>' if key[1] else "")
        + '<Properties><Property name="PrimaryPickupVolume"><Float>0.5</Float></Property></Properties></Beat>')
    voice_xml = lambda key, i: f'<Voice id="{i}"><Beats>{" ".join(map(str, key))}</Beats></Voice>'  # noqa: E731
    bar_xml = lambda key, i: f'<Bar id="{i}"><Clef>G2</Clef><Voices>{key} -1 -1 -1</Voices></Bar>'  # noqa: E731

    last = len(masters) - 1
    master_xml = "".join(
        '<MasterBar><Key><AccidentalCount>1</AccidentalCount><Mode>Major</Mode><TransposeAs>Sharps</TransposeAs></Key>'
        f'<Time>4/4</Time>{"<DoubleBar/>" if double_last and i == last else ""}<Bars>{bar}</Bars></MasterBar>'
        for i, bar in enumerate(masters))
    return (
        f"<GPIF><Score><Title>{title}</Title><Music>Composer</Music></Score>"
        f'<MasterTrack><Automations><Automation><Type>Tempo</Type><Bar>0</Bar><Position>0</Position><Value>{tempo} 2</Value></Automation></Automations></MasterTrack>'
        f'<Tracks><Track><Staves><Staff><Properties><Property name="Tuning"><Pitches>{" ".join(map(str, TUNING))}</Pitches></Property></Properties></Staff></Staves></Track></Tracks>'
        f"<MasterBars>{master_xml}</MasterBars><Bars>{emit('bar', bar_xml)}</Bars><Voices>{emit('voice', voice_xml)}</Voices>"
        f"<Beats>{emit('beat', beat_xml)}</Beats><Notes>{emit('note', note_xml)}</Notes><Rhythms>{emit('rhythm', rhythm_xml)}</Rhythms></GPIF>")


def write_gp(path: Path, xml: str) -> Path:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr(reference.GPIF_MEMBER, xml)
    return path


@pytest.fixture()
def base_xml() -> str:
    return gpif(two_bar_score())


@pytest.fixture()
def base_doc(tmp_path: Path, base_xml: str) -> dict[str, Any]:
    return reference.expand(reference.read_gpif(write_gp(tmp_path / "base.gp", base_xml)))


# ------------------------------------------------------------------------- expansion by occurrence


def test_reused_definitions_expand_by_occurrence(base_doc: dict[str, Any]) -> None:
    stats = base_doc["stats"]
    # measures 1 and 2 share one bar/voice/beat set: definitions are far fewer than occurrences.
    assert stats["measures"] == 4
    assert stats["definitions"]["bars"] == 3 and stats["definitions"]["voices"] == 3
    assert stats["beat_occurrences"] == 8 + 8 + 2 + 1
    assert stats["definitions"]["beats"] < stats["beat_occurrences"]
    assert stats["note_occurrences"] == 8 + 8 + 1 + 3
    assert stats["rest_occurrences"] == 1 and stats["chord_occurrences"] == 1
    assert stats["dotted_occurrences"] == 1 and stats["arpeggio_occurrences"] == 1
    assert stats["text_labels"] == 2  # the label is on the reused first beat, so it is counted per occurrence
    assert stats["double_bars"] == 1
    assert stats["unreferenced_definitions"] == {k: 0 for k in ("bars", "voices", "beats", "notes", "rhythms")}


def test_exact_rational_timing_and_onsets(base_doc: dict[str, Any]) -> None:
    events = base_doc["measures"][2]["staves"][0]["voices"][0]["events"]
    assert [(e["onset"], e["duration"], e["kind"]) for e in events] == [("0/1", "3/1", "note"), ("3/1", "1/1", "rest")]
    eighths = base_doc["measures"][0]["staves"][0]["voices"][0]["events"]
    assert [e["onset"] for e in eighths][:3] == ["0/1", "1/2", "1/1"]
    chord = base_doc["measures"][3]["staves"][0]["voices"][0]["events"][0]
    assert chord["arpeggio"] == "Down" and len(chord["notes"]) == 3 and chord["duration"] == "4/1"


def test_identical_semantics_with_different_ids_and_order_pass(tmp_path: Path, base_doc: dict[str, Any]) -> None:
    other = write_gp(tmp_path / "shuffled.gp", gpif(two_bar_score(), id_shift=100, reverse=True))
    other_doc = reference.expand(reference.read_gpif(other))
    result = reference.compare(base_doc, other_doc)
    assert result["equal"] and set(result["layers"].values()) == {"PASS"}


# ------------------------------------------------------------------------------- fail-closed reading


def expand_xml(tmp_path: Path, xml: str) -> dict[str, Any]:
    return reference.expand(reference.read_gpif(write_gp(tmp_path / "case.gp", xml)))


@pytest.mark.parametrize(
    ("label", "edit", "code"),
    [
        ("duplicate beat id", lambda x: x.replace('<Beat id="1">', '<Beat id="0">', 1), "duplicate_id"),
        ("dangling beat", lambda x: x.replace("<Beats>0 ", "<Beats>999 ", 1), "dangling_reference"),
        ("dangling note", lambda x: x.replace("<Notes>0</Notes>", "<Notes>999</Notes>", 1), "dangling_reference"),
        ("dangling rhythm", lambda x: x.replace('<Rhythm ref="0"/>', '<Rhythm ref="999"/>', 1), "dangling_reference"),
        ("unsupported tie on a beat", lambda x: x.replace("<Dynamic>", "<Tie/><Dynamic>", 1), "unsupported_feature"),
        ("unsupported note property", lambda x: x.replace('<Property name="Fret">', '<Property name="Bended"><Enable/></Property><Property name="Fret">', 1), "unsupported_feature"),
        ("unsupported tuplet", lambda x: x.replace("<NoteValue>Eighth</NoteValue>", '<NoteValue>Eighth</NoteValue><PrimaryTuplet num="3" den="2"/>', 1), "unsupported_feature"),
        ("unsupported note value", lambda x: x.replace("<NoteValue>Eighth</NoteValue>", "<NoteValue>Breve</NoteValue>", 1), "unsupported_feature"),
        ("midi disagrees with tuning", lambda x: x.replace("<Number>43</Number>", "<Number>44</Number>", 1), "midi_tuning_mismatch"),
        ("voice with no beats", lambda x: x.replace("<Beats>0 1 2 3 4 5 6 7</Beats>", "<Beats></Beats>", 1), "empty_voice"),
        ("bar not filled", lambda x: x.replace("<Time>4/4</Time>", "<Time>3/4</Time>", 1), "voice_duration_mismatch"),
        ("missing beats container", lambda x: x.replace("</Voices><Beats><Beat ", "</Voices><Beatz><Beat ", 1).replace("</Beat></Beats><Notes>", "</Beat></Beatz><Notes>", 1), "missing_container"),
        ("non-numeric reference", lambda x: x.replace("<Beats>0 ", "<Beats>x ", 1), "malformed_reference"),
    ],
)
def test_reader_fails_closed(tmp_path: Path, base_xml: str, label: str, edit: Any, code: str) -> None:
    edited = edit(base_xml)
    assert edited != base_xml, f"the edit for {label!r} did not change the document"
    with pytest.raises(reference.ReferenceError) as caught:
        expand_xml(tmp_path, edited)
    assert caught.value.code == code, label


def test_reader_rejects_unreadable_and_foreign_sources(tmp_path: Path) -> None:
    (tmp_path / "not-a-package.gp").write_bytes(b"this is not a zip or xml")
    with pytest.raises(reference.ReferenceError) as bad:
        reference.read_gpif(tmp_path / "not-a-package.gp")
    assert bad.value.code == "source_unreadable"
    empty = tmp_path / "empty.gp"
    with zipfile.ZipFile(empty, "w") as package:
        package.writestr("Content/other.txt", "x")
    with pytest.raises(reference.ReferenceError) as no_member:
        reference.read_gpif(empty)
    assert no_member.value.code == "gpif_member_missing"
    with pytest.raises(reference.ReferenceError) as foreign:
        reference.read_gpif(write_gp(tmp_path / "foreign.gp", "<Other/>"))
    assert foreign.value.code == "not_gpif"
    with pytest.raises(reference.ReferenceError) as missing:
        reference.read_gpif(tmp_path / "absent.gp")
    assert missing.value.code == "source_missing"


# --------------------------------------------------------------------------- oracle mutation controls


def _events(doc: dict[str, Any], measure: int) -> list[dict[str, Any]]:
    return doc["measures"][measure]["staves"][0]["voices"][0]["events"]


MUTATIONS: list[tuple[str, Any, str, str]] = [
    ("string", lambda d: _events(d, 0)[0]["notes"][0].__setitem__("string", 1), "notes", "chord_members"),
    ("fret", lambda d: _events(d, 0)[1]["notes"][0].__setitem__("fret", 9), "notes", "chord_members"),
    ("pitch", lambda d: _events(d, 0)[2]["notes"][0].__setitem__("midi", 99), "notes", "chord_members"),
    ("duration", lambda d: _events(d, 0)[3].__setitem__("duration", "1/1"), "events", "duration"),
    ("onset", lambda d: _events(d, 0)[4].__setitem__("onset", "9/8"), "events", "onset"),
    ("dot", lambda d: _events(d, 2)[0].__setitem__("dots", 0), "events", "dots"),
    ("note to rest", lambda d: _events(d, 0)[5].__setitem__("kind", "rest"), "events", "kind"),
    ("rest to note", lambda d: _events(d, 2)[1].__setitem__("kind", "note"), "events", "kind"),
    ("chord member removed", lambda d: _events(d, 3)[0]["notes"].pop(), "notes", "chord_members"),
    ("chord member added", lambda d: _events(d, 3)[0]["notes"].append({"string": 5, "fret": 0, "midi": 64}), "notes", "chord_members"),
    ("arpeggio", lambda d: _events(d, 3)[0].__setitem__("arpeggio", "Up"), "events", "arpeggio"),
    ("arpeggio removed", lambda d: _events(d, 3)[0].__setitem__("arpeggio", None), "events", "arpeggio"),
    ("section label", lambda d: _events(d, 0)[0].__setitem__("text", "Section B"), "events", "text"),
    ("section label dropped", lambda d: _events(d, 0)[0].__setitem__("text", None), "events", "text"),
    ("event dropped", lambda d: _events(d, 1).pop(), "events", "presence"),
    ("time signature", lambda d: d["measures"][1].__setitem__("time", [3, 4]), "structure", "time"),
    ("key signature", lambda d: d["measures"][2]["key"].__setitem__("accidentals", 2), "structure", "key"),
    ("final barline", lambda d: d["measures"][3].__setitem__("double_bar", False), "structure", "double_bar"),
    ("section barline", lambda d: d["measures"][1].__setitem__("double_bar", True), "structure", "double_bar"),
    ("measure dropped", lambda d: d["measures"].pop(), "structure", "measure_count"),
    ("tempo", lambda d: d["tempo"][0].__setitem__("bpm", 121), "tempo", "automations"),
    ("title", lambda d: d["header"].__setitem__("Title", "Other"), "header", "Title"),
    ("tuning", lambda d: d["conventions"]["tuning_low_to_high"].__setitem__(0, 38), "structure", "tuning"),
]


@pytest.mark.parametrize(("label", "mutate", "layer", "field"), MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_oracle_detects_each_represented_musical_field(base_doc: dict[str, Any], label: str, mutate: Any, layer: str, field: str) -> None:
    mutated = copy.deepcopy(base_doc)
    mutate(mutated)
    result = reference.compare(base_doc, mutated)
    assert not result["equal"], f"{label}: mutation was not detected"
    assert result["layers"][layer] == "FAIL", (label, result["layers"])
    assert any(d["layer"] == layer and d["field"] == field for d in result["divergences"]), (label, result["divergences"])
    assert reference.compare(base_doc, copy.deepcopy(base_doc))["equal"]  # the control that must still pass


def test_comparison_reports_location_of_first_divergence(base_doc: dict[str, Any]) -> None:
    mutated = copy.deepcopy(base_doc)
    _events(mutated, 1)[6]["notes"][0]["fret"] = 0
    first = reference.compare(base_doc, mutated)["first_divergence"]
    assert (first["measure"], first["staff"], first["voice"], first["event"]) == (1, 0, 0, 6)


# ------------------------------------------------------------------------ alias and independence


def test_reference_alias_is_rejected(tmp_path: Path, base_xml: str) -> None:
    original = write_gp(tmp_path / "reference.gp", base_xml)
    copy_path = tmp_path / "renamed-copy.gp"
    copy_path.write_bytes(original.read_bytes())
    with pytest.raises(reference.ReferenceError) as same_file:
        reference.assert_distinct_sources(original, original)
    assert same_file.value.code == "reference_alias"
    with pytest.raises(reference.ReferenceError) as same_bytes:
        reference.assert_distinct_sources(original, copy_path)
    assert same_bytes.value.code == "reference_alias"
    other = write_gp(tmp_path / "other.gp", gpif(two_bar_score(), title="Different"))
    reference.assert_distinct_sources(original, other)  # distinct content is allowed


@pytest.mark.parametrize("name", ["native_slice_reference.py", "native_slice_acceptance.py"])
def test_harness_never_imports_product_code(name: str) -> None:
    tree = ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "score2gp" not in imported


def test_reference_module_is_standard_library_at_import_time() -> None:
    tree = ast.parse((SCRIPTS / "native_slice_reference.py").read_text(encoding="utf-8"))
    top_level = {n.names[0].name.split(".")[0] for n in tree.body if isinstance(n, ast.Import)}
    top_level |= {n.module.split(".")[0] for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}
    assert "fitz" not in top_level and "pymupdf" not in top_level  # only the lazy topology probe may need it


# ------------------------------------------------------------------------------------- manifest gate


def synthetic_topology(measures: int = 4) -> dict[str, Any]:
    system = {"page": 1, "system": 1, "measures": measures, "notation_staff_y": [10.0, 20.0], "tab_staff_y": [30.0, 40.0],
              "barline_xs": [10.0, 60.0, 110.0, 160.0, 210.0][: measures + 1], "double_barline_secondary_xs": [],
              "notation_full_height_stem_xs": [35.0]}
    return {"method": "synthetic", "pages": 1, "measures_per_page": [measures], "systems_total": 1,
            "measures_total": measures, "systems": [system], "independent_of_reference": True}


def source_read(doc: dict[str, Any], measures: tuple[int, ...] = (1, 2, 3, 4)) -> list[dict[str, Any]]:
    tuning = len(doc["conventions"]["tuning_low_to_high"])
    return [{"measure": m, "events": [
        {"kind": e["kind"], "duration": e["duration"], "notes": [[tuning - n["string"], n["fret"]] for n in e["notes"]]}
        for e in doc["measures"][m - 1]["staves"][0]["voices"][0]["events"]]} for m in measures]


def adjudication(doc: dict[str, Any], **override: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"status": reference.ADJUDICATED, "unadjudicated": {"measures_from": 5}, "disagreements": [],
                             "first_system": {"page": 1, "system": 1, "printed_measures": [1, 2, 3, 4], "source_read": source_read(doc)}}
    value.update(override)
    return value


def make_manifest(doc: dict[str, Any], **override: Any) -> dict[str, Any]:
    return reference.build_manifest(doc, "a" * 64, "b" * 64, adjudication(doc, **override), synthetic_topology())


def test_manifest_accepts_matching_source_and_reference(base_doc: dict[str, Any]) -> None:
    manifest = make_manifest(base_doc)
    assert manifest["blockers"] == []
    reference.validate_manifest(manifest)
    assert manifest["adjudication"]["first_system"]["barline_xs"][0] == 10.0  # geometry comes from the measured topology


def test_manifest_preserves_source_reference_disagreement_as_blocker(base_doc: dict[str, Any]) -> None:
    wrong = adjudication(base_doc)
    wrong["first_system"]["source_read"][0]["events"][0]["notes"] = [[1, 1]]
    manifest = reference.build_manifest(base_doc, "a" * 64, "b" * 64, wrong, synthetic_topology())
    assert [b["code"] for b in manifest["blockers"]] == ["source_reference_disagreement"]
    with pytest.raises(reference.ReferenceError) as caught:
        reference.validate_manifest(manifest)
    assert caught.value.code == "manifest_has_blockers"


def test_manifest_blocks_on_measure_count_and_unresolved_disagreements(base_doc: dict[str, Any]) -> None:
    short = reference.build_manifest(base_doc, "a" * 64, "b" * 64, adjudication(base_doc), synthetic_topology(measures=3))
    assert {b["code"] for b in short["blockers"]} >= {"printed_measure_count_disagreement", "topology_measure_count_disagreement"}
    unresolved = make_manifest(base_doc, disagreements=["ambiguous digit"])
    assert [b["code"] for b in unresolved["blockers"]] == ["unresolved_disagreement"]


def test_manifest_detects_tampering_and_incomplete_adjudication(base_doc: dict[str, Any]) -> None:
    manifest = make_manifest(base_doc)
    tampered = copy.deepcopy(manifest)
    _events(tampered["reference"], 0)[0]["notes"][0]["fret"] = 8
    with pytest.raises(reference.ReferenceError) as caught:
        reference.validate_manifest(tampered)
    assert caught.value.code == "manifest_tampered"
    with pytest.raises(reference.ReferenceError):
        reference.validate_manifest({"schema": "wrong"})
    with pytest.raises(reference.ReferenceError):
        reference.build_manifest(base_doc, "a" * 64, "b" * 64, {"status": "draft"}, synthetic_topology())
    with pytest.raises(reference.ReferenceError):
        reference.build_manifest(base_doc, "a" * 64, "b" * 64, adjudication(base_doc, first_system={"page": 1}), synthetic_topology())


# ------------------------------------------------------------- coordinator: classification helpers


def test_first_system_divergence_reports_extra_and_missing_boundaries(base_doc: dict[str, Any], tmp_path: Path) -> None:
    manifest = make_manifest(base_doc)
    gen = tmp_path / "gen"
    (gen / "intermediates" / "tab").mkdir(parents=True)

    def write(barline_xs: list[float]) -> None:
        raw = {"tab_staff_bbox": [0, 30.0, 100, 40.0], "barline_xs": barline_xs, "bar_boxes": [{}] * (len(barline_xs) - 1),
               "grouping_status": "partial"}
        (gen / "intermediates" / "tab" / "tab_raw.json").write_text(
            json.dumps({"candidates": [{"page_index": 1, "raw": raw}]}), encoding="utf-8")

    write([10.0, 35.0, 60.0, 110.0, 160.0, 210.0])  # one extra boundary, on the adjudicated stem
    found = acceptance.first_system_divergence(manifest, gen)
    assert found["status"] == "DIVERGENT"
    assert found["counts"] == {"expected_boundaries": 5, "observed_boundaries": 6, "extra": 1, "missing": 0,
                               "extra_on_notation_stem": 1, "measures_expected": 4, "bar_boxes_observed": 5, "grouping_status": "partial"}
    write([10.0, 110.0, 160.0, 210.0])  # boundaries missing
    assert acceptance.first_system_divergence(manifest, gen)["counts"]["missing"] == 1
    write([10.0, 60.0, 110.0, 160.0, 210.0])
    assert acceptance.first_system_divergence(manifest, gen)["status"] == "TOPOLOGY_MATCHES_SOURCE"
    (gen / "intermediates" / "tab" / "tab_raw.json").unlink()
    assert acceptance.first_system_divergence(manifest, gen) == {"status": "NOT_EVALUATED", "reason": "tab_raw_absent"}


def test_output_directory_must_be_fresh(tmp_path: Path) -> None:
    stale = tmp_path / "stale"
    stale.mkdir()
    (stale / "result.gp").write_bytes(b"old")
    with pytest.raises(acceptance.HarnessRefused) as caught:
        acceptance.prepare_output(stale)
    assert caught.value.code == "OUTPUT_NOT_FRESH"
    acceptance.prepare_output(tmp_path / "new")
    acceptance.prepare_output(tmp_path / "new")  # an empty directory is fresh


def test_generation_environment_carries_no_oracle_path(tmp_path: Path) -> None:
    env = acceptance.child_env(tmp_path, tmp_path / "tmp", tmp_path / "sentinel")
    assert set(env) <= set(acceptance.CHILD_ENV_KEYS) | {"PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONUTF8", "TEMP", "TMP", "SCORE2GP_SENTINEL_REFERENCE"}
    assert env["PYTHONPATH"] == str(tmp_path / "src")


# ------------------------------------------- coordinator: end to end against a fake product package

FAKE_CLI = textwrap.dedent('''
    import json, os, shutil, sys, time
    from pathlib import Path

    root = Path(__file__).resolve().parent
    mode = (root / "mode.txt").read_text(encoding="utf-8").strip()
    args = sys.argv[1:]
    opt = lambda name: args[args.index(name) + 1]
    work, report, out = Path(opt("--work-dir")), Path(opt("--json-report")), Path(opt("--out"))
    work.mkdir(parents=True, exist_ok=True)
    (root / "argv.json").write_text(json.dumps(args), encoding="utf-8")

    def refuse(code="pdf_only_tab_grouping_unsafe", stage="layout-gating", exit_code=4):
        report.write_text(json.dumps({"refusal_code": code, "stage": stage, "status": "refused"}), encoding="utf-8")
        tab = root / "tab_raw.json"
        if tab.exists():
            (work / "tab").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tab, work / "tab" / "tab_raw.json")
        sys.exit(exit_code)

    if mode == "refuse":
        refuse()
    elif mode.startswith("copy:"):
        shutil.copyfile(mode[5:], out)
        report.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    elif mode.startswith("stale:"):
        shutil.copyfile(mode[6:], out)
        os.utime(out, (1, 1))
    elif mode == "leak":
        leaks = {}
        for name, path in json.loads((root / "probe_paths.json").read_text(encoding="utf-8")).items():
            try:
                Path(path).read_bytes()
                leaks[name] = "READABLE"
            except OSError:
                leaks[name] = "BLOCKED"
        leaks["sentinel_env_readable"] = "READABLE" if os.path.isfile(os.environ.get("SCORE2GP_SENTINEL_REFERENCE", "")) and not leaks.get("sentinel") == "BLOCKED" else "BLOCKED"
        leaks["environment_values"] = list(os.environ.values())
        Path.cwd().joinpath("leak.json").write_text(json.dumps(leaks), encoding="utf-8")
        refuse()
    elif mode == "sleep":
        time.sleep(60)
''')

ON_WINDOWS = os.name == "nt"


class Harness:
    """A fake product checkout plus a synthetic source, oracle and reference for coordinator runs."""

    def __init__(self, tmp_path: Path, doc: dict[str, Any], reference_gp: Path) -> None:
        self.tmp = tmp_path
        self.root = tmp_path / "product"
        package = self.root / "src" / "score2gp"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "cli.py").write_text(FAKE_CLI, encoding="utf-8")
        self.pdf = tmp_path / "source.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 synthetic control source")
        manifest = reference.build_manifest(doc, reference.file_sha256(self.pdf), reference.file_sha256(reference_gp),
                                            adjudication(doc), synthetic_topology())
        self.oracle = tmp_path / "manifest.json"
        self.oracle.write_text(json.dumps(manifest), encoding="utf-8")
        self.reference_gp = reference_gp
        self.package = package

    def mode(self, text: str) -> None:
        (self.package / "mode.txt").write_text(text, encoding="utf-8")

    def run(self, name: str = "out", *, isolation: str | None = "windows-file-lock", timeout: int = 120, **paths: Path) -> tuple[int, dict[str, Any], Path]:
        out = self.tmp / name
        args = acceptance.build_parser().parse_args([
            "--pdf", str(paths.get("pdf", self.pdf)), "--oracle", str(paths.get("oracle", self.oracle)), "--out-dir", str(out),
            "--product-root", str(paths.get("product_root", self.root)), "--protect", str(self.reference_gp),
            "--timeout", str(timeout), *(["--isolation", isolation] if isolation else [])])
        created: list[Path] = []
        code, receipt = acceptance.run(args, created)
        return code, receipt, out


@pytest.fixture()
def harness(tmp_path: Path, base_doc: dict[str, Any], base_xml: str) -> Harness:
    return Harness(tmp_path, base_doc, write_gp(tmp_path / "reference.gp", base_xml))


def summary(receipt: dict[str, Any]) -> dict[str, Any]:
    return receipt["public_summary"]


def test_no_isolation_provider_means_no_run(harness: Harness) -> None:
    harness.mode("refuse")
    code, receipt, out = harness.run(isolation=None)
    assert code == acceptance.EXIT_REFUSED and summary(receipt)["refusal_code"] == "ISOLATION_REQUIRED"
    assert not out.exists()  # nothing was measured, so nothing is left behind


def test_refused_conversion_is_verified_red_and_downstream_not_evaluated(harness: Harness) -> None:
    harness.mode("refuse")
    code, receipt, out = harness.run()
    if not ON_WINDOWS:
        assert code == acceptance.EXIT_REFUSED and summary(receipt)["refusal_code"] == "ISOLATION_UNAVAILABLE"
        return
    assert code == acceptance.EXIT_RED
    generation = summary(receipt)["generation"]
    assert (receipt["harness"], receipt["product"]) == ("HARNESS_VERIFIED", "L3_NATIVE_NOT_ACHIEVED")
    assert generation["conversion"] == "NOT_CONVERTED" and generation["semantic"] == "NOT_EVALUATED"
    assert generation["application"] == "NOT_EVALUATED" and generation["refusal_code"] == "pdf_only_tab_grouping_unsafe"
    assert not (out / "gen" / "result.gp").exists()
    argv = json.loads((harness.package / "argv.json").read_text(encoding="utf-8"))
    assert argv[0] == "convert" and {"--pdf-only-tab", "--require-precise-timing", "--strict"} <= set(argv)
    assert Path(argv[argv.index("--pdf") + 1]).name != harness.pdf.name  # generation saw a renamed staged copy
    assert reference.file_sha256(Path(argv[argv.index("--pdf") + 1])) == reference.file_sha256(harness.pdf)


def test_generation_cannot_read_oracle_sentinel_or_reference(harness: Harness) -> None:
    if not ON_WINDOWS:
        pytest.skip("windows-file-lock is the only provider; off-Windows the harness refuses (asserted in the test above)")
    (harness.package / "probe_paths.json").write_text(json.dumps({
        "oracle": str(harness.oracle), "reference": str(harness.reference_gp),
        "sentinel": str(harness.tmp / "leak-out" / "sentinel" / "reference.sentinel")}), encoding="utf-8")
    harness.mode("leak")
    code, receipt, out = harness.run("leak-out")
    assert code == acceptance.EXIT_RED
    leaks = json.loads((out / "gen" / "leak.json").read_text(encoding="utf-8"))
    assert {leaks["oracle"], leaks["reference"], leaks["sentinel"]} == {"BLOCKED"}
    assert not any(str(harness.oracle) in value or str(harness.reference_gp) in value for value in leaks["environment_values"])
    assert summary(receipt)["isolation"]["all_unreadable"] is True and summary(receipt)["isolation"]["control_readable"] is True
    assert harness.oracle.read_bytes() and harness.reference_gp.read_bytes()  # locks are released afterwards


def test_isolation_that_cannot_be_proven_refuses_to_run(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    if not ON_WINDOWS:
        pytest.skip("requires the Windows provider")
    monkeypatch.setattr(acceptance, "probe_boundary", lambda *a, **k: {"protected_count": 3, "all_unreadable": False, "control_readable": True})
    harness.mode("refuse")
    code, receipt, out = harness.run("unproven")
    assert code == acceptance.EXIT_REFUSED and summary(receipt)["refusal_code"] == "ISOLATION_NOT_ENFORCED"
    assert not (harness.package / "argv.json").exists()  # generation never started


@pytest.mark.parametrize("mode_kind", ["identical", "mutated", "alias", "stale", "locked_reference"])
def test_result_classification_never_reaches_green(harness: Harness, base_xml: str, mode_kind: str) -> None:
    if not ON_WINDOWS:
        pytest.skip("requires the Windows provider")
    candidate = harness.tmp / "candidate.gp"
    if mode_kind == "alias":
        # A byte-identical copy elsewhere: the locked original cannot be copied by generation, but a copy that
        # already exists (the case a named-file lock cannot prevent) must still be caught by its hash.
        candidate.write_bytes(harness.reference_gp.read_bytes())
    elif mode_kind == "locked_reference":
        candidate = harness.reference_gp  # generation tries to copy the locked original into its output
    elif mode_kind == "mutated":
        write_gp(candidate, base_xml.replace("<Fret>3</Fret>", "<Fret>4</Fret>", 1).replace("<Number>43</Number>", "<Number>44</Number>", 1))
    else:
        write_gp(candidate, gpif(two_bar_score(), id_shift=50, reverse=True))  # same music, different ids
    harness.mode(("stale:" if mode_kind == "stale" else "copy:") + str(candidate))
    code, receipt, _ = harness.run(mode_kind)
    generation = summary(receipt)["generation"]
    # Even a semantically identical result cannot be green while the application check is NOT_EVALUATED.
    assert code == acceptance.EXIT_RED and receipt["product"] != "L3_NATIVE_ACHIEVED"
    expected = {"identical": ("CONVERTED", "PASS"), "mutated": ("CONVERTED", "FAIL"),
                "alias": ("CONTAMINATED_REFERENCE_ALIAS", "NOT_EVALUATED"), "stale": ("STALE_OUTPUT", "NOT_EVALUATED"),
                "locked_reference": ("NOT_CONVERTED", "NOT_EVALUATED")}[mode_kind]
    assert (generation["conversion"], generation["semantic"]) == expected
    assert generation["application"] == "NOT_EVALUATED"
    if mode_kind == "identical":
        assert receipt["product"] == "L3_NATIVE_SEMANTIC_PASS_APPLICATION_NOT_EVALUATED"
    if mode_kind == "mutated":
        assert generation["first_divergence_location"]["layer"] in {"notes", "events"}


def test_conversion_timeout_is_classified(harness: Harness) -> None:
    if not ON_WINDOWS:
        pytest.skip("requires the Windows provider")
    harness.mode("sleep")
    code, receipt, _ = harness.run("timeout", timeout=3)
    assert code == acceptance.EXIT_RED and summary(receipt)["generation"]["conversion"] == "CONVERSION_TIMED_OUT"


def test_receipt_public_summary_contains_no_private_values(harness: Harness, tmp_path: Path) -> None:
    if not ON_WINDOWS:
        pytest.skip("requires the Windows provider")
    raw = {"tab_staff_bbox": [0, 30.0, 100, 40.0], "barline_xs": [10.0, 35.0, 60.0, 110.0, 160.0, 210.0], "bar_boxes": [], "grouping_status": "partial"}
    (harness.package / "tab_raw.json").write_text(json.dumps({"candidates": [{"page_index": 1, "raw": raw}]}), encoding="utf-8")
    harness.mode("refuse")
    code, receipt, out = harness.run("private")
    public = json.dumps(summary(receipt))
    for private_value in ("35.0", "160.0", str(harness.pdf), str(harness.oracle), str(harness.reference_gp)):
        assert private_value not in public
    assert receipt["private_detail"]["first_system_divergence"]["extra_xs"] == [35.0]
    assert summary(receipt)["first_system_divergence"]["counts"]["extra_on_notation_stem"] == 1


# --------------------------------------------------------- coordinator: inputs that must be refused


@pytest.mark.parametrize("case", ["missing_pdf", "missing_oracle", "wrong_source", "corrupt_oracle", "tampered_oracle", "blocked_oracle", "uncontrolled_runtime"])
def test_bad_inputs_are_refused_not_measured(harness: Harness, tmp_path: Path, case: str) -> None:
    harness.mode("refuse")
    paths: dict[str, Path] = {}
    codes = {"missing_pdf": "INPUT_MISSING", "missing_oracle": "INPUT_MISSING", "wrong_source": "SOURCE_MISMATCH",
             "corrupt_oracle": "ORACLE_UNREADABLE", "tampered_oracle": "ORACLE_INVALID", "blocked_oracle": "ORACLE_INVALID",
             "uncontrolled_runtime": "UNCONTROLLED_RUNTIME"}
    if case == "missing_pdf":
        paths["pdf"] = tmp_path / "absent.pdf"
    elif case == "missing_oracle":
        paths["oracle"] = tmp_path / "absent.json"
    elif case == "wrong_source":
        other = tmp_path / "other.pdf"
        other.write_bytes(b"%PDF-1.4 a different document")
        paths["pdf"] = other
    elif case == "corrupt_oracle":
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        paths["oracle"] = bad
    elif case in ("tampered_oracle", "blocked_oracle"):
        manifest = json.loads(harness.oracle.read_text(encoding="utf-8"))
        if case == "tampered_oracle":
            manifest["reference"]["measures"][0]["staves"][0]["voices"][0]["events"][0]["notes"][0]["fret"] = 11
        else:
            manifest["blockers"] = [{"code": "source_reference_disagreement"}]
        changed = tmp_path / "changed.json"
        changed.write_text(json.dumps(manifest), encoding="utf-8")
        paths["oracle"] = changed
    else:
        empty_root = tmp_path / "no-product"
        (empty_root / "src").mkdir(parents=True)
        paths["product_root"] = empty_root
    code, receipt, _ = harness.run(case, **paths)
    if case == "uncontrolled_runtime" and not ON_WINDOWS:
        return  # off-Windows the run is refused earlier only for isolation, after the runtime check below
    assert code == acceptance.EXIT_REFUSED, case
    assert summary(receipt)["refusal_code"] == codes[case], case
    assert not (harness.package / "argv.json").exists(), "generation must not start on a refused harness"


def test_stale_output_directory_is_refused_and_left_untouched(harness: Harness) -> None:
    stale = harness.tmp / "stale-out"
    stale.mkdir()
    (stale / "result.gp").write_bytes(b"from an earlier run")
    harness.mode("refuse")
    created: list[Path] = []
    args = acceptance.build_parser().parse_args(["--pdf", str(harness.pdf), "--oracle", str(harness.oracle), "--out-dir", str(stale),
                                                 "--product-root", str(harness.root), "--isolation", "windows-file-lock"])
    code, receipt = acceptance.run(args, created)
    assert code == acceptance.EXIT_REFUSED and summary(receipt)["refusal_code"] == "OUTPUT_NOT_FRESH"
    assert created == [] and sorted(p.name for p in stale.iterdir()) == ["result.gp"]  # no receipt was written into it


def test_windows_file_lock_blocks_other_processes_until_released(tmp_path: Path) -> None:
    if not ON_WINDOWS:
        with pytest.raises(acceptance.HarnessRefused) as caught, acceptance.windows_file_lock([tmp_path]):
            pass
        assert caught.value.code == "ISOLATION_UNAVAILABLE"
        return
    target = tmp_path / "protected.bin"
    target.write_bytes(b"secret")
    probe = [sys.executable, "-c", "import sys; open(sys.argv[1], 'rb').read(1)", str(target)]
    with acceptance.windows_file_lock([target]):
        assert subprocess.run(probe, capture_output=True).returncode != 0
        with pytest.raises(OSError):
            target.read_bytes()
    assert subprocess.run(probe, capture_output=True).returncode == 0
    with pytest.raises(acceptance.HarnessRefused) as missing, acceptance.windows_file_lock([tmp_path / "absent"]):
        pass
    assert missing.value.code == "ISOLATION_LOCK_FAILED"


def test_help_lists_the_required_invocation_contract() -> None:
    out = subprocess.run([sys.executable, str(SCRIPTS / "native_slice_acceptance.py"), "--help"], capture_output=True, text=True)
    assert out.returncode == 0
    for flag in ("--pdf", "--oracle", "--out-dir", "--isolation"):
        assert flag in out.stdout
