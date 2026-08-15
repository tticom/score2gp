import pytest
from pathlib import Path
import os
import xml.etree.ElementTree as ET

def _get_dynamic_private_pdf() -> Path:
    private_dir = Path("fixtures/private")
    if private_dir.exists():
        pdfs = list(private_dir.glob("*.pdf"))
        if pdfs:
            # Prefer Lesson-5 or Lesson-6 if available
            for p in pdfs:
                if "Lesson-6" in p.name:
                    return p
            return pdfs[0]
    pytest.skip("No private fixtures found", allow_module_level=True)
    return Path("fixtures/private/dummy.pdf")

def _get_dynamic_private_musicxml() -> Path:
    artifacts_dir = Path("tests/artifacts")
    if artifacts_dir.exists():
        mxmls = list(artifacts_dir.glob("*.musicxml"))
        if mxmls:
            # Prefer Lesson-6
            for m in mxmls:
                if "Lesson-6" in m.name:
                    return m
            return mxmls[0]
    pytest.skip("No private fixtures found", allow_module_level=True)
    return Path("tests/artifacts/dummy.musicxml")

def create_synthetic_overfull_musicxml(base_musicxml: Path, out_path: Path) -> Path:
    """Dynamically mutate a real private MusicXML artifact to create an overfull measure for testing."""
    tree = ET.parse(base_musicxml)
    root = tree.getroot()
    # Find first measure with notes
    for part in root.findall("part"):
        for measure in part.findall("measure"):
            notes = measure.findall("note")
            if notes:
                # Add an extra long note to overflow the measure
                new_note = ET.SubElement(measure, "note")
                dur = ET.SubElement(new_note, "duration")
                dur.text = "100" # Exceed standard capacity
                voice = ET.SubElement(new_note, "voice")
                voice.text = "1"
                ET.SubElement(new_note, "rest")
                
                tree.write(out_path, encoding="utf-8")
                return out_path
    
    # Fallback if no notes found
    tree.write(out_path, encoding="utf-8")
    return out_path


def _get_safe_dynamic_private_pdf() -> Path:
    private_dir = Path("fixtures/private")
    if private_dir.exists():
        pdfs = list(private_dir.glob("*.pdf"))
        if pdfs:
            for p in pdfs:
                if "Lesson-5" in p.name:
                    return p
            return pdfs[0]
    pytest.skip("No private fixtures found", allow_module_level=True)
    return Path("fixtures/private/dummy.pdf")
