from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from score2gp.batch import run_batch_pipeline
from score2gp.cache import PipelineCacheManager, compute_payload_hash


def test_incremental_build_cache_flow(tmp_path) -> None:
    manifest_path = Path("fixtures/public/test_cache_execution_manifest.json")
    workdir = tmp_path / "cache_work"

    # --- Run 1: Clean cache (expect MISS) ---
    result1 = run_batch_pipeline(manifest_path, workdir, max_workers=2, use_cache=True)
    assert result1["total_payloads"] == 2
    assert result1["success_count"] == 2
    assert result1["cache_miss_count"] == 2
    assert result1["cache_hit_count"] == 0

    for res in result1["results"]:
        assert res["cache_status"] == "miss"
        assert res["payload_hash"] is not None
        assert Path(res["output_path"]).exists()

    # --- Run 2: Populated cache (expect HIT) ---
    result2 = run_batch_pipeline(manifest_path, workdir, max_workers=2, use_cache=True)
    assert result2["total_payloads"] == 2
    assert result2["success_count"] == 2
    assert result2["cache_miss_count"] == 0
    assert result2["cache_hit_count"] == 2

    for res in result2["results"]:
        assert res["cache_status"] == "hit"
        assert Path(res["output_path"]).exists()


def test_cache_invalidation_on_config_change(tmp_path) -> None:
    # Build custom temp payload
    musicxml_src = Path("tests/fixtures/musicxml/tiny_single_bar.musicxml")
    tabraw_src = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")
    
    musicxml_temp = tmp_path / "test.musicxml"
    tabraw_temp = tmp_path / "test.tabraw.json"
    
    shutil.copy2(musicxml_src, musicxml_temp)
    shutil.copy2(tabraw_src, tabraw_temp)

    payload = {
        "id": "test_payload",
        "musicxml": str(musicxml_temp),
        "tabraw": str(tabraw_temp),
        "allow_remediation": False,
    }

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([payload]), encoding="utf-8")
    workdir = tmp_path / "cache_work_config"

    # 1. First run with allow_remediation=False (expect MISS)
    res1 = run_batch_pipeline(manifest, workdir, max_workers=1, use_cache=True)
    assert res1["cache_miss_count"] == 1
    assert res1["cache_hit_count"] == 0

    # 2. Second run with unchanged parameters (expect HIT)
    res2 = run_batch_pipeline(manifest, workdir, max_workers=1, use_cache=True)
    assert res2["cache_hit_count"] == 1

    # 3. Third run with allow_remediation=True (config changed -> expect MISS)
    payload["allow_remediation"] = True
    manifest.write_text(json.dumps([payload]), encoding="utf-8")
    res3 = run_batch_pipeline(manifest, workdir, max_workers=1, use_cache=True)
    assert res3["cache_miss_count"] == 1
    assert res3["cache_hit_count"] == 0


def test_cache_invalidation_on_file_content_change(tmp_path) -> None:
    musicxml_src = Path("tests/fixtures/musicxml/tiny_single_bar.musicxml")
    tabraw_src = Path("tests/fixtures/tabraw/tiny_single_bar_tabraw.json")
    
    musicxml_temp = tmp_path / "test_file.musicxml"
    tabraw_temp = tmp_path / "test_file.tabraw.json"
    
    shutil.copy2(musicxml_src, musicxml_temp)
    shutil.copy2(tabraw_src, tabraw_temp)

    payload = {
        "id": "test_file_payload",
        "musicxml": str(musicxml_temp),
        "tabraw": str(tabraw_temp),
    }

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([payload]), encoding="utf-8")
    workdir = tmp_path / "cache_work_file"

    # 1. First run (expect MISS)
    res1 = run_batch_pipeline(manifest, workdir, max_workers=1, use_cache=True)
    assert res1["cache_miss_count"] == 1

    # 2. Modify input file content (expect MISS)
    # Let's append some whitespace or an XML comment to the MusicXML file
    content = musicxml_temp.read_text(encoding="utf-8")
    modified_content = content + "\n<!-- Modified for cache test -->"
    musicxml_temp.write_text(modified_content, encoding="utf-8")

    res2 = run_batch_pipeline(manifest, workdir, max_workers=1, use_cache=True)
    assert res2["cache_miss_count"] == 1
    assert res2["cache_hit_count"] == 0


def test_cache_invalidation_on_missing_artifact(tmp_path) -> None:
    manifest_path = Path("fixtures/public/test_cache_execution_manifest.json")
    workdir = tmp_path / "cache_work_artifact"

    # 1. First run to populate cache (expect MISS)
    res1 = run_batch_pipeline(manifest_path, workdir, max_workers=1, use_cache=True)
    assert res1["cache_miss_count"] == 2

    # 2. Explicitly delete one of the cached artifacts in the cache directory
    cache_artifacts_dir = workdir / "cache_artifacts"
    cached_gps = list(cache_artifacts_dir.glob("*.gp"))
    assert len(cached_gps) == 2
    
    # Delete one
    cached_gps[0].unlink()

    # 3. Second run (expect 1 HIT and 1 MISS due to missing artifact)
    res2 = run_batch_pipeline(manifest_path, workdir, max_workers=2, use_cache=True)
    assert res2["cache_hit_count"] == 1
    assert res2["cache_miss_count"] == 1


def test_cache_disabled_behavior(tmp_path) -> None:
    manifest_path = Path("fixtures/public/test_cache_execution_manifest.json")
    workdir = tmp_path / "cache_work_disabled"

    # Run 1: expect MISS
    res1 = run_batch_pipeline(manifest_path, workdir, max_workers=2, use_cache=False)
    assert res1["cache_miss_count"] == 2

    # Run 2 with use_cache=False: expect MISS again
    res2 = run_batch_pipeline(manifest_path, workdir, max_workers=2, use_cache=False)
    assert res2["cache_miss_count"] == 2
    assert res2["cache_hit_count"] == 0
