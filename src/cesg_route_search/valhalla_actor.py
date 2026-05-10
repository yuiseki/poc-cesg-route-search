"""Singleton Valhalla Actor with lazy initialization."""

import json
import logging
import os
import shutil
import tarfile
import time
from pathlib import Path
from threading import Lock

import valhalla

logger = logging.getLogger(__name__)

_actor = None
_actor_lock = Lock()
_artifact_mode = "unknown"


def get_actor() -> valhalla.Actor:
    global _actor
    if _actor is None:
        with _actor_lock:
            if _actor is None:
                _actor = _init_actor()
    return _actor


def get_artifact_mode() -> str:
    return _artifact_mode


def _patch_config_dict(cfg: dict, local_dir: str) -> dict:
    """
    Apply config patching in-place (same logic as scripts/120_patch_tokyo_valhalla_config.py).

    - Replace all /custom_files/ path prefixes with local_dir
    - Ensure loki.service_defaults fields required by pyvalhalla 3.x are present
    """
    import copy

    cfg = copy.deepcopy(cfg)

    def _patch_val(val: str) -> str:
        if isinstance(val, str) and val.startswith("/custom_files"):
            suffix = val[len("/custom_files"):]
            return local_dir.rstrip("/") + suffix
        return val

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    obj[k] = _patch_val(v)
                elif isinstance(v, (dict, list)):
                    _walk(v)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str):
                    obj[i] = _patch_val(item)
                else:
                    _walk(item)

    _walk(cfg)

    # Add missing loki fields required by pyvalhalla 3.x
    loki_sd = cfg.setdefault("loki", {}).setdefault("service_defaults", {})
    if "mvt_min_zoom_road_class" not in loki_sd:
        loki_sd["mvt_min_zoom_road_class"] = [7, 7, 8, 11, 11, 12, 13, 14]
        logger.info("Added missing loki.service_defaults.mvt_min_zoom_road_class")
    if "mvt_cache_min_zoom" not in loki_sd:
        loki_sd["mvt_cache_min_zoom"] = 11
        logger.info("Added missing loki.service_defaults.mvt_cache_min_zoom")

    return cfg


def _download_file(url: str, dest: Path) -> None:
    """Download a file from url to dest, streaming with progress log."""
    import httpx

    logger.info("Downloading %s → %s", url, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    with httpx.stream("GET", url, follow_redirects=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
    elapsed = time.monotonic() - t0
    logger.info(
        "Downloaded %d bytes in %.1fs (%.1f MB/s)",
        downloaded,
        elapsed,
        downloaded / 1024 / 1024 / max(elapsed, 0.001),
    )


def _init_actor() -> valhalla.Actor:
    global _artifact_mode

    # --- Resolve env vars ---
    local_dir = os.environ.get("VALHALLA_LOCAL_DIR", "/tmp/valhalla")
    local_config = os.environ.get("VALHALLA_LOCAL_CONFIG", "/tmp/valhalla/valhalla.json")
    local_tar = os.environ.get("VALHALLA_LOCAL_TILE_EXTRACT", "/tmp/valhalla/valhalla_tiles.tar")
    config_url = os.environ.get("VALHALLA_CONFIG_URL", "")
    tile_extract_url = os.environ.get("VALHALLA_TILE_EXTRACT_URL", "")
    local_config_source = os.environ.get("VALHALLA_LOCAL_CONFIG_SOURCE", "")
    local_tar_source = os.environ.get("VALHALLA_LOCAL_TILE_EXTRACT_SOURCE", "")
    artifact_mode_env = os.environ.get("VALHALLA_ARTIFACT_MODE", "")
    fallback_extract = os.environ.get("VALHALLA_FALLBACK_EXTRACT_TO_TILE_DIR", "true").lower() == "true"

    local_dir_path = Path(local_dir)
    local_config_path = Path(local_config)
    local_tar_path = Path(local_tar)

    local_dir_path.mkdir(parents=True, exist_ok=True)

    # --- Resolve config ---
    if local_config_source and Path(local_config_source).exists():
        logger.info("Using local config source: %s", local_config_source)
        # Re-patch even if already patched (to ensure loki fields are present)
        with open(local_config_source) as f:
            cfg = json.load(f)
    elif config_url:
        if not local_config_path.exists():
            _download_file(config_url, local_config_path)
        else:
            logger.info("Config already exists at %s, skipping download", local_config)
        with open(local_config_path) as f:
            cfg = json.load(f)
    else:
        raise RuntimeError(
            "No config source. Set VALHALLA_LOCAL_CONFIG_SOURCE or VALHALLA_CONFIG_URL."
        )

    # Patch config paths
    cfg = _patch_config_dict(cfg, local_dir)

    # --- Resolve tile extract (tar) ---
    if local_tar_source and Path(local_tar_source).exists():
        logger.info("Using local tile extract source: %s", local_tar_source)
        resolved_tar = Path(local_tar_source)
    elif tile_extract_url:
        if not local_tar_path.exists():
            _download_file(tile_extract_url, local_tar_path)
        else:
            logger.info("Tar already exists at %s, skipping download", local_tar)
        resolved_tar = local_tar_path
    else:
        resolved_tar = local_tar_path if local_tar_path.exists() else None

    # --- Save working config ---
    local_config_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Attempt tile_extract mode ---
    if artifact_mode_env in ("tile_extract", "") and resolved_tar and resolved_tar.exists():
        logger.info("Attempting tile_extract mode with tar: %s", resolved_tar)
        cfg_te = json.loads(json.dumps(cfg))  # deep copy
        cfg_te.setdefault("mjolnir", {})["tile_extract"] = str(resolved_tar)
        cfg_te["mjolnir"]["tile_dir"] = ""
        # Write config
        with open(local_config_path, "w") as f:
            json.dump(cfg_te, f, indent=2)
        try:
            t0 = time.monotonic()
            actor = valhalla.Actor(cfg_te)
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.info("tile_extract Actor initialized in %.1f ms", elapsed_ms)
            _artifact_mode = "tile_extract"
            return actor
        except Exception as e:
            logger.warning("tile_extract mode failed (%s), falling back to tile_dir", e)
            if artifact_mode_env == "tile_extract":
                logger.error("VALHALLA_ARTIFACT_MODE=tile_extract but init failed; trying tile_dir anyway")

    # --- tile_dir mode ---
    if artifact_mode_env == "tile_extract":
        logger.warning("Forced tile_extract mode failed; attempting tile_dir anyway")

    tile_dir_path = local_dir_path / "valhalla_tiles"

    # Extract tar to tile_dir if needed
    if not tile_dir_path.exists() or not any(tile_dir_path.iterdir()):
        if fallback_extract and resolved_tar and resolved_tar.exists():
            logger.info("Extracting tar to %s ...", tile_dir_path)
            tile_dir_path.mkdir(parents=True, exist_ok=True)
            t0 = time.monotonic()
            with tarfile.open(str(resolved_tar)) as tf:
                tf.extractall(str(tile_dir_path))
            elapsed = time.monotonic() - t0
            logger.info("Extracted tar in %.1f s", elapsed)
        else:
            raise RuntimeError(
                f"tile_dir {tile_dir_path} does not exist and no tar to extract from. "
                "Set VALHALLA_FALLBACK_EXTRACT_TO_TILE_DIR=true or provide a tile directory."
            )

    logger.info("Using tile_dir mode: %s", tile_dir_path)
    cfg_td = json.loads(json.dumps(cfg))
    cfg_td.setdefault("mjolnir", {})["tile_dir"] = str(tile_dir_path)
    cfg_td["mjolnir"]["tile_extract"] = ""

    with open(local_config_path, "w") as f:
        json.dump(cfg_td, f, indent=2)

    t0 = time.monotonic()
    actor = valhalla.Actor(cfg_td)
    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info("tile_dir Actor initialized in %.1f ms", elapsed_ms)
    _artifact_mode = "tile_dir"
    return actor
