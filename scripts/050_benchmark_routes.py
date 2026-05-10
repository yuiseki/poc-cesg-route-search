#!/usr/bin/env python3
"""
050_benchmark_routes.py — Benchmark multiple route queries through Valhalla.

Outputs:
    outputs/benchmark-routes.json  per-query results + aggregate stats

Usage:
    python scripts/050_benchmark_routes.py [--n N]
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cesg_route_search.route import build_route_request, extract_meta, run_route

OUTPUTS = Path(__file__).parent.parent / "outputs"
LOCAL_CONFIG = OUTPUTS / "valhalla_local.json"

# A set of Tokyo-area origin/dest pairs
ROUTES = [
    {"name": "Tokyo→Shinjuku",         "origin": (139.767125, 35.681236), "dest": (139.700464, 35.689487)},
    {"name": "Shibuya→Akihabara",      "origin": (139.701238, 35.658671), "dest": (139.773415, 35.700857)},
    {"name": "Ikebukuro→Ueno",         "origin": (139.711377, 35.728926), "dest": (139.777043, 35.713768)},
    {"name": "Shinagawa→Harajuku",     "origin": (139.739521, 35.628471), "dest": (139.703116, 35.669510)},
    {"name": "Yokohama→TokyoSt",       "origin": (139.638031, 35.443708), "dest": (139.767125, 35.681236)},
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=None, help="Max routes to run")
    args = parser.parse_args()

    if not LOCAL_CONFIG.exists():
        print(f"[ERROR] {LOCAL_CONFIG} not found. Run 001_check_env.py first.", file=sys.stderr)
        sys.exit(1)

    try:
        import valhalla
    except ImportError as e:
        print(f"[ERROR] Cannot import pyvalhalla: {e}", file=sys.stderr)
        sys.exit(1)

    with open(LOCAL_CONFIG) as f:
        cfg = json.load(f)
    cfg["mjolnir"]["tile_extract"] = ""

    print("Initializing Valhalla Actor...")
    try:
        actor = valhalla.Actor(cfg)
        print("[OK] Actor ready.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize Actor: {e}", file=sys.stderr)
        sys.exit(1)

    routes_to_run = ROUTES[:args.n] if args.n else ROUTES
    results = []

    for route_def in routes_to_run:
        req = build_route_request(
            origin_lon=route_def["origin"][0], origin_lat=route_def["origin"][1],
            dest_lon=route_def["dest"][0], dest_lat=route_def["dest"][1],
            costing="auto",
        )
        try:
            response, elapsed_ms = run_route(actor, req)
            meta = extract_meta(response, elapsed_ms)
        except Exception as e:
            meta = {"success": False, "error": str(e), "runtime_ms": 0}

        result = {
            "name": route_def["name"],
            "origin": route_def["origin"],
            "dest": route_def["dest"],
            **meta,
        }
        results.append(result)
        status = "OK" if meta["success"] else "FAIL"
        print(
            f"  [{status}] {route_def['name']:30s}"
            f"  {meta.get('distance_m', 'N/A'):>8} m"
            f"  {meta.get('time_s', 'N/A'):>6} s"
            f"  {meta.get('runtime_ms', 0):>7.1f} ms"
        )

    runtimes = [r["runtime_ms"] for r in results if r.get("success")]
    aggregate = {}
    if runtimes:
        aggregate = {
            "success_count": len(runtimes),
            "total_count": len(results),
            "min_ms": round(min(runtimes), 2),
            "max_ms": round(max(runtimes), 2),
            "mean_ms": round(statistics.mean(runtimes), 2),
            "median_ms": round(statistics.median(runtimes), 2),
        }

    output = {"routes": results, "aggregate": aggregate}
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUTS / "benchmark-routes.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {out_path}")

    if aggregate:
        print("\n=== Aggregate Stats ===")
        print(f"  Success : {aggregate['success_count']}/{aggregate['total_count']}")
        print(f"  Min ms  : {aggregate['min_ms']}")
        print(f"  Max ms  : {aggregate['max_ms']}")
        print(f"  Mean ms : {aggregate['mean_ms']}")
        print(f"  Median ms: {aggregate['median_ms']}")


if __name__ == "__main__":
    main()
