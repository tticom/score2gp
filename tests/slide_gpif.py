"""Digest of a GPIF with its slide marks removed, to prove everything else is unchanged by SLIDE-01."""

import hashlib
import re
from xml.etree import ElementTree as ET


def gpif_without_slides_sha256(data: bytes) -> str:
    root = ET.fromstring(data)
    for parent in root.iter():
        for child in list(parent):
            if child.tag == "Slide" or (child.tag == "Property" and child.get("name") == "Slide"):
                parent.remove(child)
    for element in root.iter():
        element.tail = None
        element.text = (element.text or "").strip() or None
    return hashlib.sha256(ET.tostring(root)).hexdigest()


def gpif_with_legacy_double_barlines(data: bytes) -> bytes:
    """Restore only OMIT-02-FU1's removed line for frozen whole-file digests.

    The caller separately forbids Barline in the actual output. No XML
    reserialization is allowed: every other byte remains under the old digest.
    """
    def legacy_double(match):
        bar = match.group()
        if b"<DoubleBar />" in bar:
            bar = bar.replace(b"\n    </MasterBar>",
                              b"\n      <Barline>Double</Barline>\n    </MasterBar>")
        return bar
    return re.sub(rb"<MasterBar\b[^>]*>.*?</MasterBar>", legacy_double, data, flags=re.S)
