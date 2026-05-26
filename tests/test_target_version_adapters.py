from __future__ import annotations

import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from score2gp.version_adapter import adapt_gpif, get_version_file_content
from score2gp.batch import run_batch_pipeline


def test_adapt_gpif_structural_transformations() -> None:
    # Build a mock source GPIF XML string containing visual style collections, master mixer and pipeline cascades
    source_xml = b"""<GPIF version="7">
        <Score>
            <Metadata>
                <Title>Test Score</Title>
            </Metadata>
            <PageSetup>
                <Width>210</Width>
            </PageSetup>
            <StyleCollections>
                <StyleCollection name="Default"/>
            </StyleCollections>
            <MasterMixer>
                <Volume>1.0</Volume>
            </MasterMixer>
            <PipelinePresetCascade>
                <Preset>Default</Preset>
            </PipelinePresetCascade>
        </Score>
    </GPIF>"""

    # --- Test GP6 Legacy Down-conversion ---
    gp6_res = adapt_gpif(source_xml, "GP6")
    root_gp6 = ET.fromstring(gp6_res)
    assert root_gp6.attrib["version"] == "6"
    
    score_gp6 = root_gp6.find("Score")
    assert score_gp6 is not None
    assert score_gp6.find("StyleCollections") is None
    assert score_gp6.find("MasterMixer") is None
    assert score_gp6.find("PipelinePresetCascade") is None
    
    ps_gp6 = score_gp6.find("PageSetup")
    assert ps_gp6 is not None
    assert ps_gp6.find("LegacyLayout") is not None
    assert ps_gp6.find("LegacyLayout").text == "True"

    # --- Test GP8 Modern Up-conversion ---
    gp8_res = adapt_gpif(source_xml, "GP8")
    root_gp8 = ET.fromstring(gp8_res)
    assert root_gp8.attrib["version"] == "8"
    
    score_gp8 = root_gp8.find("Score")
    assert score_gp8 is not None
    
    metadata_gp8 = score_gp8.find("Metadata")
    assert metadata_gp8 is not None
    assert metadata_gp8.find("TargetCompliancy") is not None
    assert metadata_gp8.find("TargetCompliancy").text == "ModernGP8"
    assert metadata_gp8.find("VersionLayout") is not None
    assert metadata_gp8.find("VersionLayout").text == "GP8-Standard"
    
    sc_gp8 = score_gp8.find("StyleCollections")
    assert sc_gp8 is not None
    assert sc_gp8.attrib.get("gp8Compatible") == "true"


def test_batch_pipeline_multi_target_execution(tmp_path) -> None:
    manifest_path = Path("fixtures/public/test_version_adapters_manifest.json")
    workdir = tmp_path / "version_work"

    # Run the batch pipeline with 3 concurrent workers (each compiling a different target version)
    result = run_batch_pipeline(manifest_path, workdir, max_workers=3)

    assert result["total_payloads"] == 3
    assert result["success_count"] == 3
    assert result["failure_count"] == 0

    results_by_id = {res["id"]: res for res in result["results"]}

    # --- Verify GP6 Output Package ---
    gp6_res = results_by_id["payload_gp6"]
    out_gp6 = Path(gp6_res["output_path"])
    assert out_gp6.exists()
    assert zipfile.is_zipfile(out_gp6)
    
    with zipfile.ZipFile(out_gp6, "r") as z:
        assert z.read("VERSION").strip() == b"6.0"
        gpif_gp6 = ET.fromstring(z.read("Content/score.gpif"))
        assert gpif_gp6.attrib["version"] == "6"
        score_gp6 = gpif_gp6.find("Score")
        assert score_gp6 is not None
        assert score_gp6.find("StyleCollections") is None

    # --- Verify GP7 Output Package ---
    gp7_res = results_by_id["payload_gp7"]
    out_gp7 = Path(gp7_res["output_path"])
    assert out_gp7.exists()
    assert zipfile.is_zipfile(out_gp7)
    
    with zipfile.ZipFile(out_gp7, "r") as z:
        assert z.read("VERSION").strip() == b"7.0"
        gpif_gp7 = ET.fromstring(z.read("Content/score.gpif"))
        assert gpif_gp7.attrib["version"] == "7"

    # --- Verify GP8 Output Package ---
    gp8_res = results_by_id["payload_gp8"]
    out_gp8 = Path(gp8_res["output_path"])
    assert out_gp8.exists()
    assert zipfile.is_zipfile(out_gp8)
    
    with zipfile.ZipFile(out_gp8, "r") as z:
        assert z.read("VERSION").strip() == b"8.0"
        gpif_gp8 = ET.fromstring(z.read("Content/score.gpif"))
        assert gpif_gp8.attrib["version"] == "8"
        score_gp8 = gpif_gp8.find("Score")
        assert score_gp8 is not None
        metadata_gp8 = score_gp8.find("Metadata")
        assert metadata_gp8 is not None
        assert metadata_gp8.find("TargetCompliancy").text == "ModernGP8"
