"""Digest of a GPIF with its slide marks removed, to prove everything else is unchanged by SLIDE-01."""

import hashlib
import io
import re
from xml.etree import ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


def without_verified_default_template_sizes(data: bytes) -> bytes:
    """Retain frozen digests across OMIT-05-FU1's seven approved attributes.

    Supplemental digest infrastructure only: compare this genuine output's
    sizes with the independently read default-policy reference, then remove
    only those added attributes without XML reserialization. Missing or wrong
    sizes must fail before normalization; all historical hashes stay intact.
    Reference access happens here in validation, after conversion has finished.
    """
    from test_dur_02_oracle import read_gp_template_sizes

    reference = Path(__file__).resolve().parents[1] / "fixtures/private/Lesson-6.gp"
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as package:
        package.writestr("Content/score.gpif", data)
    assert read_gp_template_sizes(buffer.getvalue()) == read_gp_template_sizes(reference)

    def remove_sizes(match):
        field = match.group(1)
        stripped, count = re.subn(rb' style="font-size:\d+pt;"', b"", match.group())
        assert count == (5 if field == b"FirstPageHeader" else 1)
        return stripped

    result, count = re.subn(
        rb"<(FirstPageHeader|FirstPageFooter|PageFooter)>.*?</\1>",
        remove_sizes, data, flags=re.S,
    )
    assert count == 3
    return result


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
