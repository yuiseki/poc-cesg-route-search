#!/usr/bin/env python3
"""
040_build_tar_manifest.py — Build a byte-range manifest from tar entries.

The manifest maps tile names → (range_start, range_end) so a client can
fetch any tile with a single HTTP Range Request against a static tar file.

Outputs:
    outputs/tar-manifest-sample.json  first 1000 file entries

Usage:
    python scripts/040_build_tar_manifest.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cesg_route_search.config import get_env_paths
from cesg_route_search.tar_index import build_tar_manifest

OUTPUTS = Path(__file__).parent.parent / "outputs"
MAX_ENTRIES = 1000


def main():
    paths = get_env_paths()
    tar_path = paths["tiles_tar"]

    if not Path(tar_path).exists():
        print(f"[ERROR] VALHALLA_TILES_TAR does not exist: {tar_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Building tar manifest (first {MAX_ENTRIES} file entries): {tar_path}")

    try:
        manifest = build_tar_manifest(tar_path, max_entries=MAX_ENTRIES * 2)
        # build_tar_manifest only counts files; cap at MAX_ENTRIES
        manifest["entries"] = manifest["entries"][:MAX_ENTRIES]
        manifest["entry_count"] = len(manifest["entries"])
    except Exception as e:
        print(f"[ERROR] Failed to build manifest: {e}", file=sys.stderr)
        sys.exit(1)

    OUTPUTS.mkdir(parents=True, exist_ok=True)

    out = OUTPUTS / "tar-manifest-sample.json"
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved: {out}")

    entries = manifest["entries"]
    print(f"\n=== Tar Manifest Summary ===")
    print(f"  Artifact    : {manifest['artifact']}")
    print(f"  Entry count : {manifest['entry_count']:,}")
    if entries:
        e0 = entries[0]
        print(f"\n  First entry :")
        print(f"    name        : {e0['name']}")
        print(f"    offset      : {e0['offset']:,}")
        print(f"    size        : {e0['size']:,}")
        print(f"    range_start : {e0['range_start']:,}")
        print(f"    range_end   : {e0['range_end']:,}")
        print(f"\n  → Range Request header: bytes={e0['range_start']}-{e0['range_end']}")

    print("\n[Feasibility assessment]")
    print("  Each tile can be fetched with a single HTTP Range Request.")
    print("  The manifest (JSON) can be hosted alongside the tar on object storage.")
    print("  Client workflow: lookup tile path → manifest → HTTP GET Range → decode tile.")


if __name__ == "__main__":
    main()
