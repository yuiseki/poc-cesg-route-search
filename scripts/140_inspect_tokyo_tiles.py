#!/usr/bin/env python3
"""
140_inspect_tokyo_tiles.py — Survey data/tokyo/valhalla/valhalla_tiles/.

Counts files by level, reports size statistics.

Usage:
    .venv/bin/python scripts/140_inspect_tokyo_tiles.py [--sample N]

Outputs:
    outputs/tokyo-tile-layout-summary.json
    outputs/tokyo-tile-layout-summary.md
"""

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

TILES_DIR = REPO_ROOT / "data" / "tokyo" / "valhalla" / "valhalla_tiles"
OUTPUTS = REPO_ROOT / "outputs"


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect Tokyo Valhalla tiles.")
    parser.add_argument("--sample", type=int, default=0, help="Limit to N files (0=all)")
    return parser.parse_args()


def main():
    args = parse_args()

    if not TILES_DIR.exists():
        print(
            f"[ERROR] Tiles directory not found: {TILES_DIR}\n"
            "  Run scripts/110_build_tokyo_valhalla_tiles.sh first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Surveying: {TILES_DIR}")
    print(f"Sample limit: {args.sample if args.sample > 0 else 'all'}")

    # Collect all .gph files
    all_files = sorted(TILES_DIR.rglob("*.gph"))
    total_found = len(all_files)

    if args.sample > 0:
        files = all_files[: args.sample]
    else:
        files = all_files

    print(f"Total .gph files found: {total_found}")
    print(f"Analyzing: {len(files)} files ...")

    # Group by level (first path component under valhalla_tiles)
    by_level: dict[str, list[int]] = {}
    sizes: list[int] = []
    sample_paths: list[str] = []

    for fp in files:
        rel = fp.relative_to(TILES_DIR)
        parts = rel.parts
        level = parts[0] if parts else "unknown"
        sz = fp.stat().st_size
        by_level.setdefault(level, []).append(sz)
        sizes.append(sz)
        if len(sample_paths) < 10:
            sample_paths.append(str(rel))

    total_size = sum(sizes)
    level_stats = {}
    for lvl, szs in sorted(by_level.items()):
        level_stats[lvl] = {
            "count": len(szs),
            "total_bytes": sum(szs),
            "min_bytes": min(szs),
            "max_bytes": max(szs),
            "median_bytes": int(statistics.median(szs)),
        }

    summary = {
        "tiles_dir": str(TILES_DIR),
        "total_files_found": total_found,
        "files_analyzed": len(files),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "min_size_bytes": min(sizes) if sizes else 0,
        "max_size_bytes": max(sizes) if sizes else 0,
        "median_size_bytes": int(statistics.median(sizes)) if sizes else 0,
        "levels": level_stats,
        "sample_paths": sample_paths,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    OUTPUTS.mkdir(parents=True, exist_ok=True)

    json_out = OUTPUTS / "tokyo-tile-layout-summary.json"
    with open(json_out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Saved: {json_out}")

    # Markdown summary
    md_lines = [
        "# Tokyo Valhalla Tile Layout Summary",
        "",
        f"_Generated: {summary['generated_at']}_",
        "",
        "## Overview",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Tiles directory | `{TILES_DIR}` |",
        f"| Total .gph files | {total_found:,} |",
        f"| Files analyzed | {len(files):,} |",
        f"| Total size | {summary['total_size_mb']} MB |",
        f"| Min file size | {summary['min_size_bytes']:,} bytes |",
        f"| Max file size | {summary['max_size_bytes']:,} bytes |",
        f"| Median file size | {summary['median_size_bytes']:,} bytes |",
        "",
        "## By Level",
        "",
        "| Level | Files | Total (MB) | Min (bytes) | Max (bytes) | Median (bytes) |",
        "|---|---|---|---|---|---|",
    ]
    for lvl, stats in sorted(level_stats.items()):
        total_mb = round(stats["total_bytes"] / 1024 / 1024, 2)
        md_lines.append(
            f"| {lvl} | {stats['count']:,} | {total_mb} | "
            f"{stats['min_bytes']:,} | {stats['max_bytes']:,} | "
            f"{stats['median_bytes']:,} |"
        )

    md_lines += [
        "",
        "## Sample Paths",
        "",
        "```",
    ] + sample_paths + ["```", ""]

    md_out = OUTPUTS / "tokyo-tile-layout-summary.md"
    with open(md_out, "w") as f:
        f.write("\n".join(md_lines))
    print(f"  Saved: {md_out}")

    print("\n=== Tokyo Tile Layout ===")
    print(f"  Total files : {total_found:,}")
    print(f"  Total size  : {summary['total_size_mb']} MB")
    print(f"  Levels      : {list(sorted(by_level.keys()))}")
    for lvl, stats in sorted(level_stats.items()):
        print(
            f"    Level {lvl}: {stats['count']:,} files, "
            f"median={stats['median_bytes']:,} bytes"
        )


if __name__ == "__main__":
    main()
