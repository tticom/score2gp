from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path
from typing import Any

CACHE_MANIFEST_NAME = "cache_manifest.json"
CACHE_DIR_NAME = "cache_artifacts"


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """
    Computes a unique SHA-256 hash of the payload parameters and referenced file contents.
    Ensures that modifications to configuration parameters or source file contents
    will correctly invalidate the cache (producing a new hash).
    """
    hasher = hashlib.sha256()

    # Sort payload keys to ensure deterministic hashing
    file_keys = {"musicxml", "tabraw", "ascii_alignment", "template"}
    
    # 1. Hash configuration and scalar keys (ignoring 'id' and 'out' paths)
    config_dict = {}
    for k, v in sorted(payload.items()):
        if k not in file_keys and k not in {"id", "out"}:
            config_dict[k] = v
            
    config_bytes = json.dumps(config_dict, sort_keys=True).encode("utf-8")
    hasher.update(config_bytes)

    # 2. Hash contents of referenced files (if they exist)
    for k in sorted(file_keys):
        file_val = payload.get(k)
        if file_val:
            file_path = Path(file_val)
            if file_path.exists() and file_path.is_file():
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)
            else:
                # If path is declared but missing, hash the string representation to indicate difference
                hasher.update(str(file_val).encode("utf-8"))
                
    return hasher.hexdigest()


class PipelineCacheManager:
    _lock = threading.Lock()

    def __init__(self, base_work_dir: Path) -> None:
        self.base_work_dir = base_work_dir
        self.cache_dir = base_work_dir / CACHE_DIR_NAME
        self.manifest_path = base_work_dir / CACHE_MANIFEST_NAME
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_manifest()

    def _load_manifest(self) -> None:
        with self._lock:
            if self.manifest_path.exists():
                try:
                    self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                except Exception:
                    self.manifest = {}
            else:
                self.manifest = {}

    def _save_manifest(self) -> None:
        # Assumes lock is already held
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2, sort_keys=True), encoding="utf-8")

    def get_cached_artifact(self, payload_hash: str, target_out_path: Path) -> Path | None:
        """
        Checks if a valid cache entry exists for the given hash.
        If yes, copies the cached GP7 artifact to target_out_path and returns it.
        Otherwise returns None.
        """
        with self._lock:
            entry = self.manifest.get(payload_hash)
            if not entry:
                return None
                
            cached_file_str = entry.get("cached_file")
            if not cached_file_str:
                return None
                
            cached_file = Path(cached_file_str)
            if not cached_file.exists():
                # Obsolete / deleted artifact: invalidating
                self.manifest.pop(payload_hash, None)
                self._save_manifest()
                return None
                
            # Copy to the desired target path
            target_out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cached_file, target_out_path)
            return target_out_path

    def cache_artifact(self, payload_hash: str, generated_out_path: Path, payload: dict[str, Any]) -> None:
        """
        Caches the successfully generated GP7 artifact from generated_out_path.
        """
        with self._lock:
            if not generated_out_path.exists():
                return
                
            cached_file = self.cache_dir / f"{payload_hash}.gp"
            shutil.copy2(generated_out_path, cached_file)
            
            self.manifest[payload_hash] = {
                "cached_file": str(cached_file),
                "original_out": str(generated_out_path),
                "payload_id": payload.get("id"),
            }
            self._save_manifest()

    def invalidate_entry(self, payload_hash: str) -> None:
        """
        Explicitly invalidates and deletes a cache entry and its artifact.
        """
        with self._lock:
            entry = self.manifest.pop(payload_hash, None)
            if entry:
                cached_file_str = entry.get("cached_file")
                if cached_file_str:
                    cached_file = Path(cached_file_str)
                    if cached_file.exists():
                        cached_file.unlink()
                self._save_manifest()
