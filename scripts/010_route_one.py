#!/usr/bin/env python3
"""
010_route_one.py — Run a single route: Tokyo Station → Shinjuku.

Outputs:
    outputs/route-one.json       raw Valhalla response
    outputs/route-one.geojson    GeoJSON LineString
    outputs/route-one.meta.json  distance_m, time_s, runtime_ms, success

Usage:
    python scripts/010_route_one.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cesg_route_search.config import get_env_paths
from cesg_route_search.geojson import route_to_geojson
from cesg_route_search.route import build_route_request, extract_meta, run_route

OUTPUTS = Path(__file__).parent.parent / "outputs"
LOCAL_CONFIG = OUTPUTS / "valhalla_local.json"

# Tokyo Station → Shinjuku
ORIGIN = (139.767125, 35.681236)
DEST = (139.700464, 35.689487)


def main():
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    if not LOCAL_CONFIG.exists():
        print(
            f"[ERROR] {LOCAL_CONFIG} not found. Run scripts/001_check_env.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loading config: {LOCAL_CONFIG}")

    try:
        import valhalla
    except ImportError as e:
        print(f"[ERROR] Cannot import pyvalhalla: {e}", file=sys.stderr)
        sys.exit(1)

    # Build patched config dict for tile_dir (not tile_extract) to avoid mmap issues
    with open(LOCAL_CONFIG) as f:
        cfg = json.load(f)

    # Prefer tile_dir over tile_extract to avoid potential mmap/seek errors on large tar
    # (pyvalhalla will try tile_extract first if present; clear it to force tile_dir)
    cfg["mjolnir"]["tile_extract"] = ""

    print("Initializing Valhalla Actor (loading tile index from tile_dir)...")
    try:
        actor = valhalla.Actor(cfg)
        print("[OK] Actor initialized.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize Actor with tile_dir: {e}", file=sys.stderr)
        print("Retrying with tile_extract (tar)...", file=sys.stderr)
        # Restore tile_extract
        with open(LOCAL_CONFIG) as f:
            cfg2 = json.load(f)
        cfg2["mjolnir"]["tile_dir"] = ""
        try:
            actor = valhalla.Actor(cfg2)
            print("[OK] Actor initialized via tile_extract.")
        except Exception as e2:
            print(f"[ERROR] Both tile_dir and tile_extract failed: {e2}", file=sys.stderr)
            # Write failure meta
            meta = {
                "success": False,
                "error": str(e2),
                "origin": ORIGIN,
                "dest": DEST,
            }
            with open(OUTPUTS / "route-one.meta.json", "w") as f:
                json.dump(meta, f, indent=2)
            print(f"Failure metadata written to {OUTPUTS}/route-one.meta.json")
            sys.exit(1)

    request = build_route_request(
        origin_lon=ORIGIN[0], origin_lat=ORIGIN[1],
        dest_lon=DEST[0], dest_lat=DEST[1],
        costing="auto",
    )

    print(f"\nRouting: {ORIGIN} → {DEST} (costing=auto)")

    try:
        response, elapsed_ms = run_route(actor, request)
        meta = extract_meta(response, elapsed_ms)
        meta["origin"] = {"lon": ORIGIN[0], "lat": ORIGIN[1]}
        meta["dest"] = {"lon": DEST[0], "lat": DEST[1]}
        meta["costing"] = "auto"
    except Exception as e:
        print(f"[ERROR] Route search failed: {e}", file=sys.stderr)
        meta = {
            "success": False,
            "error": str(e),
            "origin": ORIGIN,
            "dest": DEST,
        }
        with open(OUTPUTS / "route-one.meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        print(f"Failure metadata written to {OUTPUTS}/route-one.meta.json")
        sys.exit(1)

    # Save outputs
    with open(OUTPUTS / "route-one.json", "w") as f:
        json.dump(response, f, indent=2)
    print(f"  Saved: {OUTPUTS}/route-one.json")

    geojson = route_to_geojson(response)
    with open(OUTPUTS / "route-one.geojson", "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"  Saved: {OUTPUTS}/route-one.geojson")

    with open(OUTPUTS / "route-one.meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Saved: {OUTPUTS}/route-one.meta.json")

    print("\n=== Route Result ===")
    print(f"  Success     : {meta['success']}")
    print(f"  Distance    : {meta.get('distance_m', 'N/A')} m")
    print(f"  Time        : {meta.get('time_s', 'N/A')} s")
    print(f"  Runtime     : {meta.get('runtime_ms', 'N/A')} ms")


if __name__ == "__main__":
    main()
