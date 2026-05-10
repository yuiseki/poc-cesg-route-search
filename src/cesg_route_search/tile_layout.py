"""Survey the Valhalla tile directory layout."""

import os
import statistics
from pathlib import Path


def survey_tile_dir(tiles_dir: str, sample_n: int | None = None) -> dict:
    """
    Walk tiles_dir and return layout stats.

    Args:
        tiles_dir: Path to valhalla_tiles directory.
        sample_n: If set, stop after collecting this many file entries.

    Returns:
        dict with counts, sizes, samples, level breakdown.
    """
    tiles_path = Path(tiles_dir)
    files_by_level: dict[int, list[int]] = {}
    sample_paths: list[str] = []
    total_files = 0
    total_size = 0
    all_sizes: list[int] = []

    for root, dirs, files in os.walk(tiles_path):
        dirs.sort()
        rel_root = Path(root).relative_to(tiles_path)
        depth = len(rel_root.parts)

        for fname in sorted(files):
            fpath = Path(root) / fname
            try:
                size = fpath.stat().st_size
            except OSError:
                continue

            level = depth  # 0 = top-level, 1 = one subdir, etc.
            files_by_level.setdefault(level, []).append(size)
            total_files += 1
            total_size += size
            all_sizes.append(size)

            if len(sample_paths) < 20:
                sample_paths.append(str(fpath.relative_to(tiles_path)))

            if sample_n is not None and total_files >= sample_n:
                break

        if sample_n is not None and total_files >= sample_n:
            break

    level_summary = {}
    for level, sizes in sorted(files_by_level.items()):
        level_summary[str(level)] = {
            "file_count": len(sizes),
            "total_size_bytes": sum(sizes),
            "min_size_bytes": min(sizes) if sizes else 0,
            "max_size_bytes": max(sizes) if sizes else 0,
            "median_size_bytes": statistics.median(sizes) if sizes else 0,
        }

    return {
        "tiles_dir": str(tiles_dir),
        "sampled": sample_n is not None,
        "sample_limit": sample_n,
        "total_files": total_files,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024**2, 2),
        "min_size_bytes": min(all_sizes) if all_sizes else 0,
        "max_size_bytes": max(all_sizes) if all_sizes else 0,
        "median_size_bytes": statistics.median(all_sizes) if all_sizes else 0,
        "level_summary": level_summary,
        "sample_paths": sample_paths,
    }


def layout_to_markdown(summary: dict) -> str:
    lines = [
        "# Valhalla Tile Layout Summary",
        "",
        f"- **Tiles dir**: `{summary['tiles_dir']}`",
        f"- **Sampled**: {summary['sampled']} (limit={summary['sample_limit']})",
        f"- **Total files**: {summary['total_files']:,}",
        f"- **Total size**: {summary['total_size_mb']:.2f} MB",
        f"- **Min file size**: {summary['min_size_bytes']:,} bytes",
        f"- **Max file size**: {summary['max_size_bytes']:,} bytes",
        f"- **Median file size**: {summary['median_size_bytes']:,} bytes",
        "",
        "## Files by directory level",
        "",
        "| Level | File count | Total size MB | Min bytes | Max bytes | Median bytes |",
        "|-------|-----------|--------------|-----------|-----------|--------------|",
    ]
    for level, ldata in summary["level_summary"].items():
        lines.append(
            f"| {level} | {ldata['file_count']:,} | "
            f"{ldata['total_size_bytes']/1024**2:.2f} | "
            f"{ldata['min_size_bytes']:,} | "
            f"{ldata['max_size_bytes']:,} | "
            f"{ldata['median_size_bytes']:,} |"
        )

    lines += [
        "",
        "## Sample paths",
        "",
    ]
    for p in summary["sample_paths"]:
        lines.append(f"- `{p}`")

    return "\n".join(lines) + "\n"
