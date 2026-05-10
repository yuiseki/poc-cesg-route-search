"""Inspect Valhalla tar archive without extracting."""

import tarfile
from pathlib import Path


def sample_tar_entries(tar_path: str, max_entries: int = 1000) -> list[dict]:
    """
    Iterate tar entries (without extraction) and return metadata.

    Returns list of dicts with: name, offset, size.
    """
    entries = []
    with tarfile.open(tar_path, "r:") as tf:
        for member in tf:
            if len(entries) >= max_entries:
                break
            entries.append(
                {
                    "name": member.name,
                    "offset": member.offset_data,
                    "size": member.size,
                }
            )
    return entries


def build_tar_manifest(tar_path: str, max_entries: int | None = None) -> dict:
    """
    Build a byte-range manifest from tar entries.

    Returns dict with artifact name, entry_count, and entries list.
    Each entry has: name, offset (== range_start), size, range_start, range_end.
    """
    artifact_name = Path(tar_path).name
    entries = []
    total = 0

    with tarfile.open(tar_path, "r:") as tf:
        for member in tf:
            if max_entries is not None and total >= max_entries:
                break
            if member.isfile():
                range_start = member.offset_data
                range_end = member.offset_data + member.size - 1
                entries.append(
                    {
                        "name": member.name,
                        "offset": member.offset_data,
                        "size": member.size,
                        "range_start": range_start,
                        "range_end": range_end,
                    }
                )
            total += 1

    return {
        "artifact": artifact_name,
        "entry_count": len(entries),
        "entries": entries,
    }


def summarize_tar_sample(entries: list[dict]) -> dict:
    """Summarize a list of tar entry dicts."""
    if not entries:
        return {"entry_count": 0}

    sizes = [e["size"] for e in entries]
    file_entries = [e for e in entries if e["size"] > 0]

    return {
        "entry_count": len(entries),
        "file_entry_count": len(file_entries),
        "min_size_bytes": min(sizes),
        "max_size_bytes": max(sizes),
        "total_size_bytes": sum(sizes),
        "sample_names": [e["name"] for e in entries[:10]],
    }
