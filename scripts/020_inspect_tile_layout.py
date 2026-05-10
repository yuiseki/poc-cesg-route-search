#!/usr/bin/env python3
"""
020_inspect_tile_layout.py — Survey valhalla_tiles directory layout.

Outputs:
    outputs/tile-layout-summary.json
    outputs/tile-layout-summary.md

Usage:
    python scripts/020_inspect_tile_layout.py [--sample N]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cesg_route_search.config import get_env_paths
from cesg_route_search.tile_layout import layout_to_markdown, survey_tile_dir

OUTPUTS = Path(__file__).parent.parent / "outputs"


def main():
    parser = argparse.ArgumentParser(description="Survey Valhalla tiles directory layout")
    parser.add_argument("--sample", type=int, default=None, metavar="N",
                        help="Stop after N files (for faster sampling)")
    args = parser.parse_args()

    paths = get_env_paths()
    tiles_dir = paths["tiles_dir"]

    if not Path(tiles_dir).exists():
        print(f"[ERROR] VALHALLA_TILES_DIR does not exist: {tiles_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Surveying tile dir: {tiles_dir}")
    if args.sample:
        print(f"  (sampling up to {args.sample} files)")

    summary = survey_tile_dir(tiles_dir, sample_n=args.sample)

    OUTPUTS.mkdir(parents=True, exist_ok=True)

    out_json = OUTPUTS / "tile-layout-summary.json"
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved: {out_json}")

    out_md = OUTPUTS / "tile-layout-summary.md"
    with open(out_md, "w") as f:
        f.write(layout_to_markdown(summary))
    print(f"Saved: {out_md}")

    print("\n=== Tile Layout Summary ===")
    print(f"  Total files     : {summary['total_files']:,}")
    print(f"  Total size      : {summary['total_size_mb']:.2f} MB")
    print(f"  Min file size   : {summary['min_size_bytes']:,} bytes")
    print(f"  Max file size   : {summary['max_size_bytes']:,} bytes")
    print(f"  Median file size: {summary['median_size_bytes']:,} bytes")
    print("\n  Level breakdown:")
    for level, ldata in summary["level_summary"].items():
        print(
            f"    Level {level}: {ldata['file_count']:,} files, "
            f"{ldata['total_size_bytes']/1024**2:.2f} MB"
        )
    print("\n  Sample paths:")
    for p in summary["sample_paths"][:5]:
        print(f"    {p}")


if __name__ == "__main__":
    main()
