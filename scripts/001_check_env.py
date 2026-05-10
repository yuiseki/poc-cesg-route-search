#!/usr/bin/env python3
"""
001_check_env.py — Verify environment and create patched valhalla_local.json.

Usage:
    python scripts/001_check_env.py
"""

import json
import sys
from pathlib import Path

# Allow running from repo root or scripts/ dir
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cesg_route_search.config import (
    get_env_paths,
    load_valhalla_config,
    patch_config,
    write_patched_config,
)

OUTPUT_CONFIG = Path(__file__).parent.parent / "outputs" / "valhalla_local.json"


def main():
    paths = get_env_paths()

    print("=== CESG Route Search — Environment Check ===\n")
    print(f"VALHALLA_DATA_DIR : {paths['data_dir']}")
    print(f"VALHALLA_CONFIG   : {paths['config']}")
    print(f"VALHALLA_TILES_DIR: {paths['tiles_dir']}")
    print(f"VALHALLA_TILES_TAR: {paths['tiles_tar']}")

    errors = []
    for key, path in [
        ("config", paths["config"]),
        ("tiles_dir", paths["tiles_dir"]),
        ("tiles_tar", paths["tiles_tar"]),
        ("admins.sqlite", str(Path(paths["data_dir"]) / "admins.sqlite")),
        ("timezones.sqlite", str(Path(paths["data_dir"]) / "timezones.sqlite")),
    ]:
        exists = Path(path).exists()
        print(f"  {'OK' if exists else 'MISSING':<8} {key}: {path}")
        if not exists:
            errors.append(f"Missing: {key} at {path}")

    if errors:
        print("\n[ERROR] Some required paths are missing:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print("\n[OK] All required paths exist.")

    # Patch config
    raw_cfg = load_valhalla_config(paths["config"])
    patched_cfg = patch_config(
        raw_cfg,
        data_dir=paths["data_dir"],
        tiles_dir=paths["tiles_dir"],
        tiles_tar=paths["tiles_tar"],
    )

    OUTPUT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    write_patched_config(patched_cfg, str(OUTPUT_CONFIG))
    print(f"\n[OK] Patched config written to: {OUTPUT_CONFIG}")

    # Show key config values
    mj = patched_cfg.get("mjolnir", {})
    print("\nPatched mjolnir config:")
    print(f"  tile_dir    : {mj.get('tile_dir')}")
    print(f"  tile_extract: {mj.get('tile_extract')}")
    print(f"  admin       : {mj.get('admin')}")
    print(f"  timezone    : {mj.get('timezone')}")


if __name__ == "__main__":
    main()
