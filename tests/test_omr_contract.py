import json
import zipfile
from pathlib import Path
from typer.testing import CliRunner
import hashlib
import time

from score2gp.cli import app

def test_omr_artifact_contract_success(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy pdf content")

    mock_audiveris = tmp_path / "mock_audiveris.sh"
    xml_content = b'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1"></score-partwise>\n'

    mock_audiveris.write_text(f"""#!/bin/bash
out_dir=$4
printf '%s' '{xml_content.decode("utf-8")}' > "$out_dir/test.xml"
""")
    mock_audiveris.chmod(0o755)

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    assert result.exit_code == 0

    manifest_path = out_dir / "omr_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["execution_status"] == "success"
    assert manifest["discovery_status"] == "success"
    assert manifest["validation_status"] == "success"
    assert manifest["refusal_code"] is None

def test_omr_artifact_contract_failed_exec_with_pre_existing_xml(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy pdf content")

    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    xml_content = b'<?xml version="1.0" encoding="UTF-8"?><score-partwise></score-partwise>\n'
    (out_dir / "pre_existing.xml").write_bytes(xml_content)

    mock_audiveris = tmp_path / "mock_audiveris.sh"
    mock_audiveris.write_text("#!/bin/bash\nexit 1")
    mock_audiveris.chmod(0o755)

    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    assert result.exit_code == 1

    manifest_path = out_dir / "omr_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["execution_status"] == "failed"
    assert manifest["discovery_status"] == "failed"
    assert manifest["refusal_code"] == "omr_execution_failed"

def test_omr_artifact_contract_success_exec_with_only_pre_existing(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy pdf content")

    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    xml_content = b'<?xml version="1.0" encoding="UTF-8"?><score-partwise></score-partwise>\n'
    (out_dir / "pre_existing.xml").write_bytes(xml_content)

    # Must wait slightly to ensure timestamps differ if they were created in the same second,
    # but here pre_existing is created before the script runs.
    time.sleep(0.1)

    mock_audiveris = tmp_path / "mock_audiveris.sh"
    mock_audiveris.write_text("#!/bin/bash\nexit 0")
    mock_audiveris.chmod(0o755)

    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    assert result.exit_code == 1

    manifest_path = out_dir / "omr_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["execution_status"] == "success"
    assert manifest["discovery_status"] == "stale"
    assert manifest["refusal_code"] == "omr_artifact_stale"

def test_omr_artifact_contract_nested_valid_xml(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy")

    mock_audiveris = tmp_path / "mock_audiveris.sh"
    xml_content = b'<?xml version="1.0" encoding="UTF-8"?><score-partwise></score-partwise>'

    mock_audiveris.write_text(f"""#!/bin/bash
out_dir=$4
mkdir -p "$out_dir/deep/nested"
printf '%s' '{xml_content.decode("utf-8")}' > "$out_dir/deep/nested/test.xml"
""")
    mock_audiveris.chmod(0o755)

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    assert result.exit_code == 0
    manifest = json.loads((out_dir / "omr_manifest.json").read_text())
    assert manifest["discovery_status"] == "success"
    assert "deep/nested/test.xml" in manifest["artifact_path"].replace("\\", "/")

def test_omr_artifact_contract_valid_mxl(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy")

    # Create valid MXL
    mxl_path = tmp_path / "test.mxl"
    with zipfile.ZipFile(mxl_path, 'w') as z:
        z.writestr('META-INF/container.xml', b'<?xml version="1.0" encoding="UTF-8"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>')
        z.writestr('score.xml', b'<?xml version="1.0" encoding="UTF-8"?><score-partwise></score-partwise>')

    mock_audiveris = tmp_path / "mock_audiveris.sh"
    mock_audiveris.write_text(f"#!/bin/bash\ncp '{mxl_path}' \"$4/test.mxl\"")
    mock_audiveris.chmod(0o755)

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    assert result.exit_code == 0
    manifest = json.loads((out_dir / "omr_manifest.json").read_text())
    assert manifest["validation_status"] == "success"

def test_omr_artifact_contract_mxl_malformed_container(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy")

    mxl_path = tmp_path / "test.mxl"
    with zipfile.ZipFile(mxl_path, 'w') as z:
        z.writestr('META-INF/container.xml', b'not xml')
        z.writestr('score.xml', b'<score-partwise></score-partwise>')

    mock_audiveris = tmp_path / "mock_audiveris.sh"
    mock_audiveris.write_text(f"#!/bin/bash\ncp '{mxl_path}' \"$4/test.mxl\"")
    mock_audiveris.chmod(0o755)

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    assert result.exit_code == 1
    manifest = json.loads((out_dir / "omr_manifest.json").read_text())
    assert manifest["validation_status"] == "invalid"
    assert manifest["refusal_code"] == "omr_artifact_invalid"

def test_omr_artifact_contract_mxl_missing_rootfile(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy")

    mxl_path = tmp_path / "test.mxl"
    with zipfile.ZipFile(mxl_path, 'w') as z:
        z.writestr('META-INF/container.xml', b'<?xml version="1.0" encoding="UTF-8"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles></rootfiles></container>')

    mock_audiveris = tmp_path / "mock_audiveris.sh"
    mock_audiveris.write_text(f"#!/bin/bash\ncp '{mxl_path}' \"$4/test.mxl\"")
    mock_audiveris.chmod(0o755)

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    assert result.exit_code == 1
    manifest = json.loads((out_dir / "omr_manifest.json").read_text())
    assert manifest["validation_status"] == "invalid"

def test_omr_artifact_contract_mxl_invalid_inner_score(tmp_path: Path):
    runner = CliRunner()
    mock_pdf = tmp_path / "test.pdf"
    mock_pdf.write_bytes(b"dummy")

    mxl_path = tmp_path / "test.mxl"
    with zipfile.ZipFile(mxl_path, 'w') as z:
        z.writestr('META-INF/container.xml', b'<?xml version="1.0" encoding="UTF-8"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>')
        z.writestr('score.xml', b'<invalid-root></invalid-root>')

    mock_audiveris = tmp_path / "mock_audiveris.sh"
    mock_audiveris.write_text(f"#!/bin/bash\ncp '{mxl_path}' \"$4/test.mxl\"")
    mock_audiveris.chmod(0o755)

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["omr", str(mock_pdf), "--out", str(out_dir), "--audiveris", str(mock_audiveris)])
    assert result.exit_code == 1
    manifest = json.loads((out_dir / "omr_manifest.json").read_text())
    assert manifest["validation_status"] == "invalid"
