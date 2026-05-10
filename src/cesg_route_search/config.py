"""Configuration loading and patching for Valhalla."""

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment variable names used by valhalla_actor.py
# ---------------------------------------------------------------------------

# Remote download URLs
ENV_TILE_EXTRACT_URL = "VALHALLA_TILE_EXTRACT_URL"
ENV_CONFIG_URL = "VALHALLA_CONFIG_URL"
ENV_MANIFEST_URL = "VALHALLA_MANIFEST_URL"  # future use

# Local working directory and paths
ENV_LOCAL_DIR = "VALHALLA_LOCAL_DIR"               # default: /tmp/valhalla
ENV_LOCAL_TILE_EXTRACT = "VALHALLA_LOCAL_TILE_EXTRACT"  # default: /tmp/valhalla/valhalla_tiles.tar
ENV_LOCAL_CONFIG = "VALHALLA_LOCAL_CONFIG"         # default: /tmp/valhalla/valhalla.json

# Operational mode
ENV_ARTIFACT_MODE = "VALHALLA_ARTIFACT_MODE"       # "tile_extract" or "tile_dir"
ENV_FALLBACK_EXTRACT = "VALHALLA_FALLBACK_EXTRACT_TO_TILE_DIR"  # "true"/"false"

# Local source paths (for dev; skips download if file exists)
ENV_LOCAL_TILE_EXTRACT_SOURCE = "VALHALLA_LOCAL_TILE_EXTRACT_SOURCE"
ENV_LOCAL_CONFIG_SOURCE = "VALHALLA_LOCAL_CONFIG_SOURCE"

# Default values
DEFAULT_LOCAL_DIR = "/tmp/valhalla"
DEFAULT_LOCAL_TILE_EXTRACT = "/tmp/valhalla/valhalla_tiles.tar"
DEFAULT_LOCAL_CONFIG = "/tmp/valhalla/valhalla.json"


def load_valhalla_config(config_path: str) -> dict:
    """Load raw valhalla.json from disk."""
    with open(config_path) as f:
        return json.load(f)


def patch_config(config: dict, data_dir: str, tiles_dir: str, tiles_tar: str) -> dict:
    """
    Replace Docker-style /custom_files/ paths with real local paths.

    The original valhalla.json from osm-planet-in-da-house uses /custom_files/
    because it was built inside a Docker container.  We replace the relevant
    keys so that pyvalhalla can find the data on the host filesystem.
    """
    import copy

    cfg = copy.deepcopy(config)
    mj = cfg.setdefault("mjolnir", {})

    mj["tile_dir"] = tiles_dir
    mj["tile_extract"] = tiles_tar
    mj["admin"] = str(Path(data_dir) / "admins.sqlite")
    mj["timezone"] = str(Path(data_dir) / "timezones.sqlite")

    # Remove paths that don't exist locally to avoid confusing Valhalla
    mj.pop("traffic_extract", None)
    mj.pop("transit_dir", None)
    mj.pop("transit_feeds_dir", None)
    mj.pop("landmarks", None)
    mj.pop("default_speeds_config", None)

    cfg.pop("additional_data", None)

    return cfg


def write_patched_config(cfg: dict, output_path: str) -> None:
    """Write patched config to disk."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(cfg, f, indent=2)


def get_env_paths() -> dict:
    """Read environment variables and return a dict of paths."""
    data_dir = os.environ.get(
        "VALHALLA_DATA_DIR",
        "/everything/src/github.com/yuiseki/osm-planet-in-da-house/data/valhalla",
    )
    return {
        "data_dir": data_dir,
        "config": os.environ.get("VALHALLA_CONFIG", str(Path(data_dir) / "valhalla.json")),
        "tiles_dir": os.environ.get("VALHALLA_TILES_DIR", str(Path(data_dir) / "valhalla_tiles")),
        "tiles_tar": os.environ.get("VALHALLA_TILES_TAR", str(Path(data_dir) / "valhalla_tiles.tar")),
    }
