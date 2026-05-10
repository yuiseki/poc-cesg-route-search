#!/usr/bin/env python3
"""
030_inspect_tar_index.py — Read tar entries from valhalla_tiles.tar without extracting.

Outputs:
    outputs/tar-index-sample.json   first 1000 entries with name/offset/size
    outputs/tar-index-summary.json  summary statistics

Usage:
    python scripts/030_inspect_tar_index.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cesg_route_search.config import get_env_paths
from cesg_route_search.tar_index import sample_tar_entries, summarize_tar_sample

OUTPUTS = Path(__file__).parent.parent / "outputs"
MAX_ENTRIES = 1000


def main():
    paths = get_env_paths()
    tar_path = paths["tiles_tar"]

    if not Path(tar_path).exists():
        print(f"[ERROR] VALHALLA_TILES_TAR does not exist: {tar_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading tar index (first {MAX_ENTRIES} entries): {tar_path}")
    print("  (This iterates the tar header — no extraction performed)")

    try:
        entries = sample_tar_entries(tar_path, max_entries=MAX_ENTRIES)
    except Exception as e:
        print(f"[ERROR] Failed to read tar: {e}", file=sys.stderr)
        sys.exit(1)

    OUTPUTS.mkdir(parents=True, exist_ok=True)

    out_sample = OUTPUTS / "tar-index-sample.json"
    with open(out_sample, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"Saved: {out_sample}")

    summary = summarize_tar_sample(entries)
    out_summary = OUTPUTS / "tar-index-summary.json"
    with open(out_summary, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved: {out_summary}")

    print("\n=== Tar Index Summary ===")
    print(f"  Entries sampled : {summary.get('entry_count', 0):,}")
    print(f"  File entries    : {summary.get('file_entry_count', 0):,}")
    print(f"  Min size        : {summary.get('min_size_bytes', 0):,} bytes")
    print(f"  Max size        : {summary.get('max_size_bytes', 0):,} bytes")
    print(f"  Total size (sample): {summary.get('total_size_bytes', 0)/1024**2:.2f} MB")
    print("\n  Sample names:")
    for name in summary.get("sample_names", [])[:5]:
        print(f"    {name}")

    # Feasibility check
    if entries:
        offsets = [e["offset"] for e in entries if e["size"] > 0]
        if offsets:
            print(f"\n  First offset    : {min(offsets):,} bytes")
            print(f"  Offset feasible for Range Requests: YES (byte offsets available)")


if __name__ == "__main__":
    main()
