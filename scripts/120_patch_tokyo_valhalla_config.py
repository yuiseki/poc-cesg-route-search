#!/usr/bin/env python3
"""
120_patch_tokyo_valhalla_config.py — Patch valhalla.json for host-side pyvalhalla.

Reads data/tokyo/valhalla/valhalla.json (produced by Docker build) and replaces
all /custom_files/ path prefixes with the absolute path to data/tokyo/valhalla/.
Sets mjolnir.tile_dir explicitly and clears mjolnir.tile_extract.

Writes: data/tokyo/valhalla/valhalla.host.json

Usage:
    python scripts/120_patch_tokyo_valhalla_config.py
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VALHALLA_DIR = REPO_ROOT / "data" / "tokyo" / "valhalla"
SOURCE_JSON = VALHALLA_DIR / "valhalla.json"
OUTPUT_JSON = VALHALLA_DIR / "valhalla.host.json"


def patch_value(val: str, valhalla_dir: str) -> tuple[str, bool]:
    """Replace /custom_files prefix with valhalla_dir. Returns (new_val, changed)."""
    if isinstance(val, str) and val.startswith("/custom_files"):
        suffix = val[len("/custom_files"):]
        new_val = valhalla_dir.rstrip("/") + suffix
        return new_val, True
    return val, False


def patch_config(cfg: dict, valhalla_dir: str) -> dict:
    """Recursively patch all /custom_files paths in the config dict."""
    patched_keys: list[str] = []

    def _patch(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                full_key = f"{path}.{k}" if path else k
                if isinstance(v, str):
                    new_v, changed = patch_value(v, valhalla_dir)
                    if changed:
                        obj[k] = new_v
                        patched_keys.append(f"{full_key}: {v!r} → {new_v!r}")
                elif isinstance(v, (dict, list)):
                    _patch(v, full_key)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _patch(item, f"{path}[{i}]")

    _patch(cfg)
    return cfg, patched_keys


def main():
    if not SOURCE_JSON.exists():
        print(
            f"[ERROR] {SOURCE_JSON} not found.\n"
            "  Run scripts/110_build_tokyo_valhalla_tiles.sh first.",
            file=sys.stderr,
        )
        sys.exit(1)

    valhalla_dir_abs = str(VALHALLA_DIR.resolve())
    tiles_dir_abs = str((VALHALLA_DIR / "valhalla_tiles").resolve())
    admins_abs = str((VALHALLA_DIR / "admins.sqlite").resolve())
    timezones_abs = str((VALHALLA_DIR / "timezones.sqlite").resolve())

    print(f"Reading: {SOURCE_JSON}")
    with open(SOURCE_JSON) as f:
        cfg = json.load(f)

    # Patch all /custom_files references generically
    cfg, patched_keys = patch_config(cfg, valhalla_dir_abs)

    # Explicit key overrides for known critical paths
    mjolnir = cfg.setdefault("mjolnir", {})
    mjolnir["tile_dir"] = tiles_dir_abs
    mjolnir["tile_extract"] = ""  # force tile_dir mode
    mjolnir["admin"] = admins_abs
    mjolnir["timezone"] = timezones_abs

    # Add pyvalhalla 3.x required loki.service_defaults fields that newer Docker
    # images omit but older pyvalhalla builds require.
    loki_sd = cfg.setdefault("loki", {}).setdefault("service_defaults", {})
    if "mvt_min_zoom_road_class" not in loki_sd:
        loki_sd["mvt_min_zoom_road_class"] = [7, 7, 8, 11, 11, 12, 13, 14]
        print("\nAdded missing loki.service_defaults.mvt_min_zoom_road_class")
    if "mvt_cache_min_zoom" not in loki_sd:
        loki_sd["mvt_cache_min_zoom"] = 11
        print("Added missing loki.service_defaults.mvt_cache_min_zoom")

    print(f"\nPatched {len(patched_keys)} /custom_files references:")
    for line in patched_keys[:30]:
        print(f"  {line}")
    if len(patched_keys) > 30:
        print(f"  ... and {len(patched_keys) - 30} more")

    print(f"\nExplicit overrides:")
    print(f"  mjolnir.tile_dir     = {tiles_dir_abs}")
    print(f"  mjolnir.tile_extract = '' (cleared)")
    print(f"  mjolnir.admin        = {admins_abs}")
    print(f"  mjolnir.timezone     = {timezones_abs}")

    with open(OUTPUT_JSON, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"\nWritten: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
