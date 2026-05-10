# Hypotheses: Cloud-Native Geospatial Routing Graph

## H1 — Tile directory layout is object-storage friendly

**Hypothesis:** Valhalla's `valhalla_tiles/` directory uses a hierarchical structure
(level/tile_id.gph) that maps naturally to object storage keys (e.g., S3/GCS paths).
Each tile is an independent file, so it can be fetched individually without downloading
the entire dataset.

**Expected finding:**
- 3 levels (0 = coarsest, 2 = finest)
- File sizes vary by region density (large urban tiles, tiny ocean tiles)
- Total file count in the hundreds of thousands for planet-scale data
- Median file size probably 10–200 KB — small enough for individual object fetches

**Challenge:**
- Planet-scale datasets contain millions of tiny files, which is expensive to list on S3
- Cold-start latency from listing all tiles would be high
- Solution needed: a tile manifest (JSON or SQLite) describing which tiles exist

---

## H2 — tar + byte-range manifest is HTTP Range Request friendly

**Hypothesis:** The `valhalla_tiles.tar` file is a flat byte stream where each tile
occupies a contiguous range. If we build a manifest mapping `tile_name → (offset, size)`,
a client can fetch any tile with a single HTTP Range Request:

```
GET /valhalla_tiles.tar
Range: bytes=<offset>-<offset+size-1>
```

This is compatible with any static HTTP server, S3, GCS, Azure Blob, or CDN that
supports `Accept-Ranges: bytes`.

**Expected finding:**
- Tar entries have stable, predictable byte offsets
- The manifest (JSON, ~tens of MB for planet scale) can be hosted as a companion file
- Client downloads manifest once, then fetches individual tiles on demand

**Challenge:**
- Tar format pads blocks to 512-byte boundaries — client must handle this
- A planet-scale manifest might be large; consider binary format or SQLite
- pyvalhalla's `tile_extract` mode mmaps the whole tar — not useful for remote fetches

---

## H3 — A Cloud Native Routing Graph artifact looks like

**Hypothesis:** The ideal CESG routing artifact consists of:

1. `valhalla_tiles.tar` — all tiles in a single flat file, hosted on object storage
2. `valhalla_tiles.manifest.json` (or `.sqlite`) — maps each tile path to byte offset + size
3. `valhalla.json` — Valhalla configuration, with tile_extract URL pointing to the tar
4. `stac-item.json` — STAC descriptor for discovery (bbox, datetime, version)
5. A lightweight proxy server that translates Valhalla tile reads into HTTP Range Requests

**The proxy pattern:**
- Valhalla's tile reader opens a tile by path
- Proxy intercepts the read, looks up the manifest, issues a Range Request, returns bytes
- This allows pyvalhalla to run against remote tiles without modification
- Alternatively: pre-fetch tiles for the bounding box of a query before routing

---

## H4 — pyvalhalla Actor can run against precomputed planet tiles

**Hypothesis:** pyvalhalla 3.7.0 can load planet-scale Valhalla tiles from either:
- `tile_dir` (directory mode): loads tile index, reads tiles on demand
- `tile_extract` (tar mode): mmaps the tar file and reads tiles at offset

**Expected finding:**
- tile_dir mode works but requires the full directory to be locally mounted
- tile_extract mode works but requires the full 90 GB tar to be locally accessible
- Neither mode natively supports remote (HTTP) tile fetching
- The PoC will verify local tile_dir works on the planet-scale dataset

---

## H5 — Route search latency is dominated by tile loading, not computation

**Hypothesis:** For a short route (e.g., Tokyo Station → Shinjuku, ~7 km),
the routing computation itself is fast (<100 ms). The bottleneck for a cloud-native
service would be tile fetching latency (disk I/O or HTTP round-trips).

**Expected finding:**
- Cold query (first route): higher latency due to disk cache warming
- Warm query (subsequent routes in the same region): <50 ms
- Tile fetch over HTTP (if implemented): depends on CDN/S3 latency + tile size

---

## Summary table

| Hypothesis | Metric | Expected verdict |
|---|---|---|
| H1: tile_dir is object-storage friendly | File count, size distribution | Partially yes — but million-file listing is a problem |
| H2: tar + manifest is Range Request friendly | Offset availability, manifest size | Yes — offsets are stable and predictable |
| H3: CESG artifact design | N/A | tar + manifest + proxy is most practical path |
| H4: pyvalhalla works on planet tiles | Route success | Yes (tile_dir mode) |
| H5: route latency is fast | runtime_ms | <500 ms warm |
