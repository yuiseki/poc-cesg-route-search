# Findings: CESG Route Search PoC

_Last updated: 2026-05-10_

---

## 1. Can precomputed routing graph be queried from Python?

**Status: YES — confirmed working**

pyvalhalla 3.7.0 successfully loaded the planet-scale precomputed Valhalla tile graph
and returned a valid route. The `Actor` class accepts a config dict or path and exposes
a `route()` method compatible with the Valhalla HTTP API request format.

**Key detail:** The original `valhalla.json` uses Docker `/custom_files/` paths.
Runtime patching via `scripts/001_check_env.py` replaces these before calling
`valhalla.Actor()`. The Actor initialized using `tile_dir` mode (directory), not
`tile_extract` (tar), to avoid mmap errors on the 90 GB tar.

---

## 2. Current Valhalla artifact layout

### 2a. Tile directory (`valhalla_tiles/`)

| Metric | Value |
|---|---|
| Directory levels | 0, 1, 2 |
| Level 0 files | 1,191 tiles |
| Level 1 files | 12,826 tiles |
| Level 2 files | 886 subdirs (sample: 5000 files) |
| Min file size | 464 bytes |
| Max file size | 83,925,232 bytes (~80 MB) |
| Median file size (sample) | 125,936 bytes (~123 KB) |
| Sample total (5000 files) | 5,559 MB |

Level 2 has by far the most tiles and the largest ones (street-level routing graph for
the whole planet). The 886 subdirectories × ~N tiles each implies hundreds of thousands
of Level 2 tiles total.

### 2b. Tar archive (`valhalla_tiles.tar`)

| Metric | Value |
|---|---|
| Total size | 90 GB |
| Estimated total entries | ~23,000 |
| Sampled entries (first 1000) | 1,000 |
| First entry | `index.bin` at offset 512 (size 3,338,848 bytes) |
| Min entry size (sample) | 464 bytes |
| Max entry size (sample) | 83,925,232 bytes |
| Total size of 1000-entry sample | ~3.96 GB |

The tar contains an `index.bin` file as its first entry — this is Valhalla's internal
tile index for fast offset lookup in `tile_extract` mode.

---

## 3. Is directory layout object-storage friendly?

**Verdict: Partially yes, with caveats**

**Pros:**
- Each tile is an independent file → single GET per tile
- Path structure (`0/000/529.gph`) maps directly to S3/GCS object keys
- Fine-grained access: only tiles for the query route are needed
- Tile sizes are manageable: median ~123 KB, small enough for individual fetches

**Cons:**
- Very large file count: ~14,000+ tiles at levels 0+1 alone, hundreds of thousands at level 2
- S3 LIST operations are expensive for millions of small files (~$0.005/1000 requests)
- No built-in index: need an external manifest to know which tiles exist without listing
- Ocean/uninhabited tiles are tiny (464 bytes) but plentiful — many unnecessary objects

**Conclusion:** Direct S3 mapping works for serving, but a **tile existence manifest**
is essential for cold-start efficiency.

---

## 4. Is tar layout Range Request friendly?

**Verdict: YES — fully feasible**

Python's `tarfile` module exposes `member.offset_data` for each entry, giving the exact
byte position of each tile within the 90 GB tar. A JSON manifest mapping
`tile_name → {offset, size}` enables:

```
GET /valhalla_tiles.tar
Range: bytes=<offset>-<offset+size-1>
```

This is compatible with S3, GCS, Azure Blob, CloudFront, and any HTTP/1.1 server
supporting `Accept-Ranges: bytes`.

**Sample manifest entry (index.bin):**
```json
{
  "name": "index.bin",
  "offset": 512,
  "size": 3338848,
  "range_start": 512,
  "range_end": 3339359
}
```

**Manifest size estimate:** ~23,000 entries × ~120 bytes/entry (JSON) ≈ 2.8 MB.
Gzipped: ~300–500 KB. This is trivially downloadable at cold start.

**Verdict:** The tar + manifest pattern is the **most practical cloud-native deployment**
for Valhalla routing graphs. The manifest is small, and each tile can be fetched with a
single Range Request.

---

## 5. What would a Cloud Native Routing Graph artifact look like?

Based on this PoC, the ideal CESG routing graph artifact is:

```
cesg-routing-graph/
  valhalla_tiles.tar          (90 GB) ← hosted on object storage
  valhalla_tiles.manifest.json         ← tile name → {offset, size}  (~2.8 MB)
  valhalla.json                        ← Valhalla config
  stac-item.json                       ← STAC descriptor for discovery
```

**Client workflow:**
1. Download `valhalla_tiles.manifest.json` (~2.8 MB, once per session)
2. Receive routing query with waypoints
3. Determine which tiles are needed (Valhalla tile selection: ~5–20 tiles per city route)
4. Fetch each tile via HTTP Range Request against `valhalla_tiles.tar`
5. Write tiles to local temp dir → configure `tile_dir` pointing to temp dir
6. Initialize `valhalla.Actor(cfg)` → call `actor.route(request)`
7. Return route response

**Alternative: Tile proxy FUSE layer** — intercepts Valhalla tile reads and translates
them into Range Requests. Valhalla runs unmodified; no temp dir needed.

---

## 6. Route search results

### Single route: Tokyo Station → Shinjuku

| Field | Value |
|---|---|
| Origin | Tokyo Station (139.767125, 35.681236) |
| Destination | Shinjuku (139.700464, 35.689487) |
| Costing | auto |
| Distance | **7,618 m** (7.6 km) |
| Travel time | **934 s** (~15.6 min) |
| Runtime | **469 ms** (cold, tile_dir mode) |
| Success | YES |

The route successfully traversed Tokyo's urban road network using the planet-scale
precomputed graph. The 469 ms runtime includes tile loading (cold cache).

---

## 7. Next experiments

1. **Full tar manifest**: Build the complete planet manifest (not 1000-entry sample)
   and measure actual manifest file size vs. estimate.

2. **Range Request prototype**: Implement a Python FUSE or socket proxy that intercepts
   Valhalla tile reads and fetches via HTTP Range from S3.

3. **Warm route latency**: Run multiple routes in the same region to measure warm-cache
   routing latency (expected: <50 ms).

4. **Knative deployment**: Package pyvalhalla + tile-fetch proxy as a Knative service.
   On cold start: download manifest, prefetch bbox tiles, route.

5. **STAC integration**: Describe the routing graph artifact with a STAC item for
   discovery via STAC API (bbox, datetime, costing profile).

6. **Benchmark**: Run `050_benchmark_routes.py` to measure latency distribution across
   5 Tokyo-area routes.
