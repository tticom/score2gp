from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .gpif import build_gpif, gpif_warnings
from .ir import ScoreIR, ScoreBooklet

REQUIRED_MEMBERS = {"VERSION", "Content/score.gpif"}


def write_gp(score: ScoreIR | ScoreBooklet, out_path: str | Path, template: str | Path | None = None) -> list[str]:
    warnings: list[str] = gpif_warnings(score)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    copied: dict[str, bytes] = {}
    if template:
        template_path = Path(template)
        if template_path.exists():
            try:
                with zipfile.ZipFile(template_path, "r") as zin:
                    copied = {name: zin.read(name) for name in zin.namelist() if name != "Content/score.gpif"}
            except zipfile.BadZipFile:
                warnings.append(f"template is not a valid zip package: {template_path}")
        else:
            warnings.append(f"template does not exist: {template_path}")

    copied.setdefault("VERSION", b"7.0\n")
    copied.setdefault("Content/Preferences.json", b"{}\n")
    copied.setdefault("Content/LayoutConfiguration", b"")
    copied.setdefault("Content/PartConfiguration", b"")
    copied.setdefault("Content/BinaryStylesheet", b"")

    if isinstance(score, ScoreBooklet):
        # Build main/primary score GPIF with Booklet index embedded
        gpif = build_gpif(score)
        copied["Content/score.gpif"] = gpif

        # Compile sequential movements and page indexing
        start_page = score.pagination.start_page if score.pagination else 1
        movements_list = []
        for idx, s in enumerate(score.scores):
            mov_gpif = build_gpif(s, booklet=score)
            mov_path = f"Content/movement_{idx + 1}.gpif"
            copied[mov_path] = mov_gpif

            movements_list.append({
                "index": idx + 1,
                "title": s.metadata.title,
                "file": mov_path,
                "start_page": start_page
            })
            pg_count = s.conversion.source_page_count if s.conversion.source_page_count is not None else 1
            start_page += pg_count

        # Write the Booklet index JSON
        booklet_index = {
            "booklet_title": score.booklet_title,
            "metadata": score.metadata.model_dump(exclude_none=True),
            "pagination": score.pagination.model_dump(exclude_none=True) if score.pagination else None,
            "movements": movements_list
        }
        copied["Content/booklet_index.json"] = json.dumps(booklet_index, indent=2).encode("utf-8")
    else:
        gpif = build_gpif(score)
        copied["Content/score.gpif"] = gpif

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        directories = {"Content/"}
        for directory in sorted(directories):
            zout.writestr(directory, b"")
        for name, data in copied.items():
            if not name.endswith("/"):
                zout.writestr(name, data)

    return warnings


def validate_gp(path: str | Path) -> dict[str, Any]:
    gp = Path(path)
    result: dict[str, Any] = {
        "path": str(gp),
        "is_zip": False,
        "required_members": {},
        "xml_well_formed": False,
        "errors": [],
    }
    try:
        with zipfile.ZipFile(gp, "r") as zf:
            result["is_zip"] = True
            names = set(zf.namelist())
            result["members"] = sorted(names)
            result["required_members"] = {name: name in names for name in sorted(REQUIRED_MEMBERS)}
            if not all(result["required_members"].values()):
                result["errors"].append("missing required GP package members")
            try:
                ET.fromstring(zf.read("Content/score.gpif"))
                result["xml_well_formed"] = True
            except Exception as exc:  # noqa: BLE001 - report parser detail to caller
                result["errors"].append(f"GPIF XML is not well formed: {exc}")
    except zipfile.BadZipFile:
        result["errors"].append("not a zip package")
    except FileNotFoundError:
        result["errors"].append("file does not exist")
    return result


def inspect_gp(path: str | Path) -> dict[str, Any]:
    gp = Path(path)
    validation = validate_gp(gp)
    summary: dict[str, Any] = {
        "path": str(gp),
        "package": validation,
        "gp_version": None,
        "tracks": [],
        "tunings": [],
        "tempo": None,
        "time_signatures": [],
        "bar_count": 0,
        "note_count": 0,
        "chord_symbols": [],
        "techniques": [],
    }
    if validation["errors"]:
        return summary

    with zipfile.ZipFile(gp, "r") as zf:
        if "VERSION" in zf.namelist():
            summary["gp_version"] = zf.read("VERSION").decode("utf-8", errors="replace").strip()
        root = ET.fromstring(zf.read("Content/score.gpif"))

    summary.update(_summarize_gpif(root))
    return summary


def compare_gp(expected: str | Path, actual: str | Path) -> dict[str, Any]:
    expected_summary = inspect_gp(expected)
    actual_summary = inspect_gp(actual)
    fields = [
        "gp_version",
        "tracks",
        "tempo",
        "time_signatures",
        "bar_count",
        "note_count",
        "chord_symbols",
        "techniques",
    ]
    differences = {
        field: {"expected": expected_summary.get(field), "actual": actual_summary.get(field)}
        for field in fields
        if expected_summary.get(field) != actual_summary.get(field)
    }
    return {
        "expected": str(expected),
        "actual": str(actual),
        "matches": not differences,
        "differences": differences,
    }


def _summarize_gpif(root: ET.Element) -> dict[str, Any]:
    tracks: list[str] = []
    tunings: list[dict[str, Any]] = []
    for track in root.findall(".//Track"):
        name = _first_text(track, ["Name", "Name/Name"]) or track.get("name") or track.get("id") or "unknown"
        tracks.append(name)
        strings = []
        for string in track.findall(".//String"):
            if string.get("pitch") or string.get("name"):
                strings.append(
                    {
                        "number": string.get("number"),
                        "pitch": string.get("pitch") or string.text,
                        "name": string.get("name"),
                    }
                )

        has_staff_tuning = False
        for staff in track.findall(".//Staff"):
            pitches_node = staff.find(".//Property[@name='Tuning']/Pitches")
            if pitches_node is not None and pitches_node.text:
                pitches = pitches_node.text.split()
                staff_name = _first_text(staff, ["Name"]) or _known_tuning_name(pitches)
                staff_strings = sorted(
                    [
                        {"number": str(len(pitches) - index), "pitch": pitch, "name": None}
                        for index, pitch in enumerate(pitches)
                    ],
                    key=lambda s: int(s["number"])
                )
                if staff_strings:
                    tunings.append({"track": name, "name": staff_name, "strings": staff_strings})
                    has_staff_tuning = True

        if strings and not has_staff_tuning:
            tunings.append({"track": name, "strings": strings})

    tempo = _first_text(root, [".//Tempo/Value", ".//Tempo", ".//Tempos/Tempo/Value"])
    if tempo is None:
        for automation in root.findall(".//Automation"):
            if _first_text(automation, ["Type"]) == "Tempo":
                value = _first_text(automation, ["Value"])
                if value:
                    tempo = value.split()[0]
                    break
    time_signatures = []
    for node in root.findall(".//MasterBar"):
        value = _first_text(node, ["Time", "TimeSignature"])
        if value:
            time_signatures.append(value)

    chord_symbols = sorted(_chord_symbols(root))
    techniques = sorted(
        {
            node.get("name") or "".join(node.itertext()).strip()
            for node in root.findall(".//Technique")
            if (node.get("name") or "".join(node.itertext()).strip())
        }
    )
    notes = root.findall(".//Note")
    bars = root.findall(".//Bar")
    if not bars:
        bars = root.findall(".//MasterBar")

    return {
        "tracks": tracks,
        "tunings": tunings,
        "tempo": tempo,
        "time_signatures": sorted(set(time_signatures)),
        "bar_count": len(bars),
        "note_count": len(notes),
        "chord_symbols": chord_symbols,
        "techniques": techniques,
    }


def _first_text(root: ET.Element, paths: list[str]) -> str | None:
    for path in paths:
        node = root.find(path)
        if node is not None:
            text = "".join(node.itertext()).strip()
            if text:
                return text
    return None


def _chord_symbols(root: ET.Element) -> set[str]:
    symbols: set[str] = set()
    for node in root.findall(".//Chord"):
        text = "".join(node.itertext()).strip()
        if text and not text.isdigit():
            symbols.add(text)
    for item in root.findall(".//Property[@name='ChordCollection']//Item"):
        name = item.get("name")
        if name:
            symbols.add(name)
    return symbols


def _known_tuning_name(pitches: list[str]) -> str | None:
    known = {
        ("40", "45", "50", "55", "59", "64"): "Standard guitar",
        ("40", "47", "52", "56", "59", "64"): "Open E",
    }
    return known.get(tuple(pitches))


def dumps_summary(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True)
