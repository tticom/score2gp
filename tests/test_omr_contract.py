import json
from pathlib import Path
from typer.testing import CliRunner
import hashlib

from score2gp.cli import app

def test_omr_artifact_contract_success(tmp_path: Path):
    runner = CliRunner()
    
    # Setup mock PDF
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy pdf content")
    
    # Setup mock audiveris executable that generates a valid MusicXML file
    mock_audiveris = tmp_path / "mock_audiveris.sh"
    xml_content = b'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1"></score-partwise>\n'
    
    # Shell script that writes the xml_content into the output dir
    mock_audiveris.write_text(f"""#!/bin/bash
    out_dir=$4
    printf '%s' '{xml_content.decode("utf-8")}' > "$out_dir/test.xml"
    """)
    mock_audiveris.chmod(0o755)
    
    out_dir = tmp_path / "out"
    
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    
    assert result.exit_code == 0
    
    manifest_path = out_dir / "omr_manifest.json"
    assert manifest_path.exists()
    
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "success"
    assert manifest["artifact_path"].endswith("test.xml")
    assert manifest["pdf_sha256"] == hashlib.sha256(b"dummy pdf content").hexdigest()
    assert manifest["artifact_sha256"] == hashlib.sha256(xml_content).hexdigest()
    assert manifest["next_handoff"] == f"score2gp convert --pdf {mock_pdf} --musicxml {manifest['artifact_path']}"
    assert manifest["provenance_note"] == "Association is command-run provenance only; not proof of musical equivalence."
    assert "product_sha" in manifest
    assert "omr_executable" in manifest

def test_omr_artifact_contract_missing(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy pdf content")
    
    mock_audiveris = tmp_path / "mock_audiveris_missing.sh"
    mock_audiveris.write_text("#!/bin/bash\nexit 0")
    mock_audiveris.chmod(0o755)
    
    out_dir = tmp_path / "out_missing"
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    
    assert result.exit_code == 1
    assert "omr_artifact_missing" in result.output
    
def test_omr_artifact_contract_ambiguous(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy pdf content")
    
    mock_audiveris = tmp_path / "mock_audiveris_ambiguous.sh"
    mock_audiveris.write_text("""#!/bin/bash
    out_dir=$4
    touch "$out_dir/test1.xml"
    touch "$out_dir/test2.xml"
    """)
    mock_audiveris.chmod(0o755)
    
    out_dir = tmp_path / "out_ambiguous"
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    
    assert result.exit_code == 1
    assert "omr_artifact_ambiguous" in result.output

def test_omr_artifact_contract_invalid(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy pdf content")
    
    mock_audiveris = tmp_path / "mock_audiveris_invalid.sh"
    mock_audiveris.write_text("""#!/bin/bash
    out_dir=$4
    echo "not xml" > "$out_dir/test.xml"
    """)
    mock_audiveris.chmod(0o755)
    
    out_dir = tmp_path / "out_invalid"
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    
    assert result.exit_code == 1
    assert "omr_artifact_invalid" in result.output
