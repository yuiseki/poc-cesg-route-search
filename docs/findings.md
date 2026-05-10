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

## 8. Tokyo Valhalla tile reproduction

_Run date: 2026-05-10_

### Build pipeline

| Step | Script | Result |
|---|---|---|
| Prepare data | `100_prepare_tokyo_data.sh` | Symlink created to Kanto PBF (443 MB) |
| Build tiles | `110_build_tokyo_valhalla_tiles.sh` | Docker build completed in ~4 minutes |
| Patch config | `120_patch_tokyo_valhalla_config.py` | 8 `/custom_files/` refs patched; 2 missing pyvalhalla fields added |
| Route search | `130_route_tokyo_one.py` | Tokyo Station → Shinjuku: 7,618 m / 878 s / 249 ms |
| Tile survey | `140_inspect_tokyo_tiles.py` | 272 tiles, 818 MB total |

### Docker build details

- Image: `ghcr.io/valhalla/valhalla-scripted:latest`
- Input: `kanto-260423.osm.pbf` (443 MB), Kanto region, dated 2026-04-23
- Output: `valhalla_tiles/` (272 tiles), `admins.sqlite` (7.9 MB), `timezones.sqlite` (115 MB), `valhalla_tiles.tar` (819 MB)
- Build time: ~4 minutes
- Key fix: PBF must be bind-mounted directly into `/custom_files/` (symlinks across volume boundaries don't resolve inside Docker)

### Config patching (script 120)

The Docker image produces `valhalla.json` with all paths as `/custom_files/...`.
pyvalhalla 3.7.0 also requires `loki.service_defaults.mvt_min_zoom_road_class` and
`mvt_cache_min_zoom` which the newer Docker image omits. The patch script adds both.

### Tile layout

| Metric | Value |
|---|---|
| Total tiles | 272 |
| Total size | 818 MB |
| Level 0 tiles | 8 (highway-level graph) |
| Level 1 tiles | 14 (arterial roads) |
| Level 2 tiles | 250 (local streets) |
| Level 2 median size | 392 bytes (sparse Kanto coverage) |
| Level 1 median size | 183,044 bytes |

The Kanto region generates only 272 tiles vs. ~14,000+ for the planet at levels 0+1
alone. This is ideal for container embedding or object-storage serving.

### Route search results (Tokyo tiles)

| Field | Value |
|---|---|
| Origin | Tokyo Station (139.767125, 35.681236) |
| Destination | Shinjuku (139.700464, 35.689487) |
| Costing | auto |
| Distance | **7,618 m** |
| Travel time | **878 s** (~14.6 min) |
| Runtime | **249 ms** (cold, tile_dir mode) |
| Success | YES |

Routing against regional tiles is ~2x faster than the planet-scale tiles (249 ms vs.
469 ms cold start) due to the smaller tile index to load.

---

## 11. GitHub Pages + Knative route demo

_Deployed: 2026-05-10_

- Knative endpoint: https://poc-cesg-route-search.yuiseki.com
- Frontend: https://yuiseki.github.io/poc-cesg-route-search/
- Default route: Shibuya Station → Shinjuku Station
- Background map: https://tile.yuiseki.net/styles/osm-fiord/style.json
- Interaction: draggable start/end markers trigger POST /route
- Runtime mode: pyvalhalla Actor inside FastAPI, tile_extract mode
- Artifact: Tokyo valhalla_tiles.tar, 819 MB

> Note: This demo does not yet implement true remote Range Request routing.
> The 819 MB valhalla_tiles.tar is currently used as a local tile_extract artifact inside the container/runtime.

---

## 9. Next experiments

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

---

## 10. FastAPI / Knative Route Search Service

_Run date: 2026-05-10_

### pyvalhalla works inside FastAPI

pyvalhalla 3.7.0 integrates cleanly with FastAPI. The `valhalla.Actor` is initialized
once at startup (via `lifespan` context) and reused across all requests. No separate
Valhalla HTTP server process is needed — the Python binding calls the routing engine
directly in-process.

### tile_extract mode confirmed working

The 819 MB Tokyo tar (`valhalla_tiles.tar`) loads successfully in `tile_extract` mode
via mmap. Actor initialization takes ~7 ms. First route call: ~97 ms (cold). Subsequent
calls would be faster as tiles are cached in memory.

### Route search results (FastAPI, tile_extract mode)

| Field | Value |
|---|---|
| Origin | Tokyo Station (139.767125, 35.681236) |
| Destination | Shinjuku (139.700464, 35.689487) |
| Costing | auto |
| Distance | **7,618.0 m** |
| Travel time | **878.4 s** (~14.6 min) |
| Runtime | **97.3 ms** (first request, tile_extract mode) |
| Artifact mode | tile_extract |
| Success | YES |

### Artifact size comparison

| Service | Artifact | Size |
|---|---|---|
| poc-cesg-poi-search | DuckDB file | ~50 MB |
| poc-cesg-route-search | Valhalla tar (Kanto) | 819 MB |
| poc-cesg-route-search | Valhalla tar (planet) | ~90 GB |

The route search artifact is ~16× larger than the POI search DuckDB. This has direct
implications for cold start time on Knative (see `docs/knative-deploy.md`).

### Cold start implications

At `tile_extract` mode cold start on Knative:
- Download `valhalla.json` config: ~1 KB, negligible
- Download `valhalla_tiles.tar` (819 MB): ~30–120s at 10–30 MB/s
- Actor init: ~7 ms
- Total: ~30–120s depending on network throughput

`timeoutSeconds: 300` is set in the ksvc to accommodate this. The next step is a
per-tile Range Request fetcher to reduce cold start data to ~2.8 MB manifest +
query-time tile fetches (~0.6–2.5 MB per route).

### Valhalla still needs local file access

Valhalla's Actor requires tiles to be accessible as local files (tile_dir mode) or a
local tar (tile_extract mode via mmap). It cannot read tiles directly from HTTP URLs.
A tile proxy that intercepts file reads and fetches via HTTP Range Requests would
remove this constraint (see `docs/findings.md` section 4).

### Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/healthz` | GET | Liveness probe |
| `/readyz` | GET | Readiness probe (actor_initialized, mode) |
| `/route` | POST | Route search (start, end, costing) |
