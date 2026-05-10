# Valhalla Data Layout Notes

## Source data

Location: `/everything/src/github.com/yuiseki/osm-planet-in-da-house/data/valhalla/`

| File / Dir | Size | Notes |
|---|---|---|
| `valhalla.json` | ~10 KB | Valhalla config (Docker paths, needs patching) |
| `valhalla_tiles/` | ~large | Precomputed routing graph tiles |
| `valhalla_tiles.tar` | 90 GB | All tiles in a single tar archive |
| `admins.sqlite` | ~MB | Administrative boundaries database |
| `timezones.sqlite` | ~MB | Timezone database |

## valhalla.json Docker path issue

The original `valhalla.json` uses `/custom_files/` prefix because it was generated
inside a Docker container (the `ghcr.io/valhalla/valhalla-scripted` image mounts
data at `/custom_files/`).

Key paths that need patching at runtime:

```json
{
  "mjolnir": {
    "tile_dir":     "/custom_files/valhalla_tiles",   → VALHALLA_TILES_DIR
    "tile_extract": "/custom_files/valhalla_tiles.tar", → VALHALLA_TILES_TAR
    "admin":        "/custom_files/admins.sqlite",    → $DATA_DIR/admins.sqlite
    "timezone":     "/custom_files/timezones.sqlite", → $DATA_DIR/timezones.sqlite
  }
}
```

The runtime patch is done by `scripts/001_check_env.py` which writes
`outputs/valhalla_local.json`.

## Valhalla tile structure

Valhalla tiles are organized in a 3-level hierarchy:

```
valhalla_tiles/
  0/          ← Level 0: coarsest (planet-scale, ~4 degree cells)
    000/
      000.gph
      ...
  1/          ← Level 1: medium (city-scale, ~1 degree cells)
    001/
      ...
  2/          ← Level 2: finest (street-level, ~0.25 degree cells)
    ...
```

Each tile file (`*.gph`) is a binary Protocol Buffer containing:
- Road graph edges for the region
- Turn restrictions
- Administrative boundaries (via admins.sqlite)
- Edge elevation data (if available)

## pyvalhalla Actor tile loading modes

### tile_dir mode (directory)
```python
cfg["mjolnir"]["tile_dir"] = "/path/to/valhalla_tiles"
cfg["mjolnir"]["tile_extract"] = ""
actor = valhalla.Actor(cfg)
```
- Reads tiles individually from disk as needed
- No upfront loading of the entire dataset
- Compatible with NFS/network filesystems
- Tile index built from directory listing on startup

### tile_extract mode (tar)
```python
cfg["mjolnir"]["tile_extract"] = "/path/to/valhalla_tiles.tar"
cfg["mjolnir"]["tile_dir"] = ""
actor = valhalla.Actor(cfg)
```
- mmaps the entire tar file
- Fast random access via precomputed offset table inside the tar
- Requires the full 90 GB tar to be locally accessible
- Not suitable for remote (HTTP) fetching without a proxy

## Object storage considerations

### Problems with tile_dir → direct S3 mapping
- S3 LIST calls are expensive for millions of small files
- No atomic "list all tiles in bbox" operation
- Each tile fetch = 1 HTTP GET (acceptable latency per tile, ~5–50 ms)
- Cold start requires listing all keys → slow

### Problems with tile_extract → single S3 object
- Can use Range Requests to fetch individual tiles
- Need a companion manifest file to know which offset each tile is at
- Valhalla's mmap-based tar reader doesn't support HTTP Range natively
- Would need a FUSE layer or custom tile reader to intercept reads

## Tar format details

Standard POSIX tar format:
- Each entry: 512-byte header + data (padded to 512-byte boundary)
- Header contains: name, size, modification time, permissions
- `member.offset_data` in Python's tarfile module = byte position of data start
- Range Request: `bytes=offset_data-(offset_data+size-1)`

No modification to the tar file is needed — the manifest is purely metadata.
