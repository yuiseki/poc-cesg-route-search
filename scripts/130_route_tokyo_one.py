#!/usr/bin/env python3
"""
130_route_tokyo_one.py — Route Tokyo Station → Shinjuku using Tokyo tiles.

Env vars (all optional, defaults shown):
    ROUTE_START_LON=139.767125
    ROUTE_START_LAT=35.681236
    ROUTE_END_LON=139.700464
    ROUTE_END_LAT=35.689487
    ROUTE_COSTING=auto
    TOKYO_VALHALLA_CONFIG=<repo>/data/tokyo/valhalla/valhalla.host.json

Outputs:
    outputs/tokyo-route-one.json        raw Valhalla response
    outputs/tokyo-route-one.geojson     GeoJSON FeatureCollection (LineString)
    outputs/tokyo-route-one.meta.json   metadata summary

Usage:
    .venv/bin/python scripts/130_route_tokyo_one.py
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from cesg_route_search.geojson import route_to_geojson

OUTPUTS = REPO_ROOT / "outputs"
DEFAULT_CONFIG = REPO_ROOT / "data" / "tokyo" / "valhalla" / "valhalla.host.json"

# Coordinates
START_LON = float(os.environ.get("ROUTE_START_LON", "139.767125"))
START_LAT = float(os.environ.get("ROUTE_START_LAT", "35.681236"))
END_LON = float(os.environ.get("ROUTE_END_LON", "139.700464"))
END_LAT = float(os.environ.get("ROUTE_END_LAT", "35.689487"))
COSTING = os.environ.get("ROUTE_COSTING", "auto")
CONFIG_PATH = Path(os.environ.get("TOKYO_VALHALLA_CONFIG", str(DEFAULT_CONFIG)))


def build_request(start_lon, start_lat, end_lon, end_lat, costing):
    return {
        "locations": [
            {"lon": start_lon, "lat": start_lat},
            {"lon": end_lon, "lat": end_lat},
        ],
        "costing": costing,
        "directions_options": {"units": "km"},
    }


def main():
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        print(
            f"[ERROR] Valhalla config not found: {CONFIG_PATH}\n"
            "  Run scripts/110_build_tokyo_valhalla_tiles.sh and "
            "scripts/120_patch_tokyo_valhalla_config.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Config : {CONFIG_PATH}")
    print(f"Start  : ({START_LON}, {START_LAT})  # Tokyo Station")
    print(f"End    : ({END_LON}, {END_LAT})  # Shinjuku")
    print(f"Costing: {COSTING}")

    try:
        import valhalla
    except ImportError as e:
        print(f"[ERROR] Cannot import pyvalhalla: {e}", file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    # Force tile_dir mode
    cfg["mjolnir"]["tile_extract"] = ""

    print("\nInitializing Valhalla Actor...")
    try:
        actor = valhalla.Actor(cfg)
        print("[OK] Actor initialized.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize Actor: {e}", file=sys.stderr)
        meta = {
            "success": False,
            "error": str(e),
            "costing": COSTING,
            "start": [START_LON, START_LAT],
            "end": [END_LON, END_LAT],
            "distance_m": None,
            "time_s": None,
            "runtime_ms": None,
            "valhalla_config": str(CONFIG_PATH),
            "tiles_dir": cfg.get("mjolnir", {}).get("tile_dir", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(OUTPUTS / "tokyo-route-one.meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        sys.exit(1)

    request = build_request(START_LON, START_LAT, END_LON, END_LAT, COSTING)
    print(f"\nRouting Tokyo Station → Shinjuku ...")

    t0 = time.perf_counter()
    try:
        response = actor.route(request)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        print(f"[ERROR] Route failed after {elapsed_ms:.0f} ms: {e}", file=sys.stderr)
        meta = {
            "success": False,
            "error": str(e),
            "costing": COSTING,
            "start": [START_LON, START_LAT],
            "end": [END_LON, END_LAT],
            "distance_m": None,
            "time_s": None,
            "runtime_ms": elapsed_ms,
            "valhalla_config": str(CONFIG_PATH),
            "tiles_dir": cfg.get("mjolnir", {}).get("tile_dir", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(OUTPUTS / "tokyo-route-one.meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        print(f"Failure metadata written to outputs/tokyo-route-one.meta.json")
        sys.exit(1)

    # Extract summary
    summary = response.get("trip", {}).get("summary", {})
    distance_m = round(summary.get("length", 0) * 1000, 1) if summary.get("length") else None
    time_s = summary.get("time")

    meta = {
        "success": True,
        "costing": COSTING,
        "start": [START_LON, START_LAT],
        "end": [END_LON, END_LAT],
        "distance_m": distance_m,
        "time_s": time_s,
        "runtime_ms": elapsed_ms,
        "valhalla_config": str(CONFIG_PATH),
        "tiles_dir": cfg.get("mjolnir", {}).get("tile_dir", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save raw response
    with open(OUTPUTS / "tokyo-route-one.json", "w") as f:
        json.dump(response, f, indent=2)
    print(f"  Saved: outputs/tokyo-route-one.json")

    # Save GeoJSON
    geojson = route_to_geojson(response)
    with open(OUTPUTS / "tokyo-route-one.geojson", "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"  Saved: outputs/tokyo-route-one.geojson")

    # Save meta
    with open(OUTPUTS / "tokyo-route-one.meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Saved: outputs/tokyo-route-one.meta.json")

    print("\n=== Tokyo Route Result ===")
    print(f"  Success     : {meta['success']}")
    print(f"  Distance    : {meta['distance_m']} m")
    print(f"  Time        : {meta['time_s']} s")
    print(f"  Runtime     : {meta['runtime_ms']} ms")


if __name__ == "__main__":
    main()
