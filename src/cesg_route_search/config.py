"""Configuration loading and patching for Valhalla."""

import json
import os
from pathlib import Path


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
