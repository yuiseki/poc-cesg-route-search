# poc-cesg-route-search

Proof-of-concept for Cloud-Native Geospatial (CESG) route search using precomputed Valhalla routing graph tiles.

## Live demo

- **Knative endpoint:** https://poc-cesg-route-search.yuiseki.com
- **GitHub Pages frontend:** https://yuiseki.github.io/poc-cesg-route-search/

The frontend shows a MapLibre GL JS map with draggable start (green) and end (red) markers.
Dragging either marker triggers a POST /route request and renders the route as a blue line.
Default route: Shibuya Station → Shinjuku Station.

## Knative deploy

```bash
# Apply ksvc (downloads valhalla_tiles.tar from object storage on cold start)
kubectl apply -f k8s/ksvc.yaml

# Check status
kubectl get ksvc -n knative-pool poc-cesg-route-search
kubectl get pods -n knative-pool | grep route-search
```

Cold start downloads 819 MB tar from `https://z.yuiseki.net/static/cesg/tokyo/valhalla_tiles.tar`.
`timeoutSeconds: 300` is set to accommodate this.

## API usage

```bash
# Service info / health
curl -sS https://poc-cesg-route-search.yuiseki.com/
curl -sS https://poc-cesg-route-search.yuiseki.com/health

# Liveness probe
curl -sS https://poc-cesg-route-search.yuiseki.com/healthz

# Readiness probe
curl -sS https://poc-cesg-route-search.yuiseki.com/readyz

# Route: Shibuya Station → Shinjuku Station
curl -sS https://poc-cesg-route-search.yuiseki.com/route \
  -H 'Content-Type: application/json' \
  -d '{"costing": "auto", "start": [139.701238, 35.658034], "end": [139.700464, 35.689487]}' \
  | python3 -m json.tool
```

## GitHub Pages

The `docs/index.html` frontend is served via GitHub Pages from the `main` branch `/docs` directory.

Features:
- Background map: `https://tile.yuiseki.net/styles/osm-fiord/style.json`
- Two draggable markers: green (start), red (end)
- Route rendered as blue LineString (width 4, opacity 0.8)
- Info panel: Distance, Time, API latency, Status
- API URL configurable via `?api=` query parameter

## Purpose

This PoC investigates whether a precomputed Valhalla routing graph can be:

1. **Queried from Python** using pyvalhalla's Actor API against planet-scale tiles
2. **Served cloud-natively** via object storage (S3/GCS) using HTTP Range Requests
3. **Described as a CESG artifact** — a portable, self-describing routing data product

## Data source

Precomputed Valhalla planet tiles from `osm-planet-in-da-house`:

```
/everything/src/github.com/yuiseki/osm-planet-in-da-house/data/valhalla/
  valhalla.json           ← config (Docker paths, patched at runtime)
  valhalla_tiles/         ← precomputed routing graph (directory mode)
  valhalla_tiles.tar      ← same tiles as a tar archive (90 GB)
  admins.sqlite           ← administrative boundaries
  timezones.sqlite        ← timezone data
```

## Quick start

```bash
# 1. Clone and set up venv
python3 -m venv .venv
.venv/bin/pip install pyvalhalla requests

# 2. Set environment (copy and edit .env.example)
cp .env.example .env
source .env

# 3. Check environment and create patched config
.venv/bin/python scripts/001_check_env.py

# 4. Run a route search (Tokyo Station → Shinjuku)
.venv/bin/python scripts/010_route_one.py

# 5. Inspect tile layout
.venv/bin/python scripts/020_inspect_tile_layout.py --sample 5000

# 6. Inspect tar index
.venv/bin/python scripts/030_inspect_tar_index.py

# 7. Build tar manifest
.venv/bin/python scripts/040_build_tar_manifest.py

# 8. Benchmark multiple routes
.venv/bin/python scripts/050_benchmark_routes.py
```

## Repository layout

```
poc-cesg-route-search/
  README.md
  LICENSE                   MIT
  .env.example              environment variable template
  .gitignore
  pyproject.toml
  src/
    cesg_route_search/
      __init__.py
      config.py             load & patch valhalla.json
      route.py              route request helpers
      geojson.py            polyline6 decode → GeoJSON
      tile_layout.py        tile directory survey
      tar_index.py          tar entry inspection
  scripts/
    001_check_env.py        verify paths, write valhalla_local.json
    010_route_one.py        single route: Tokyo Station → Shinjuku
    020_inspect_tile_layout.py  survey tile dir (file count, sizes, levels)
    030_inspect_tar_index.py    read tar headers without extracting
    040_build_tar_manifest.py   build offset manifest for Range Requests
    050_benchmark_routes.py     benchmark multiple routes
    900_build_small_valhalla_tiles_optional.sh  build regional tiles with Docker
  docs/
    hypothesis.md           research hypotheses
    data-layout-notes.md    Valhalla data format notes
    findings.md             experimental results
  outputs/                  gitignored; created by scripts
  outputs-samples/          committed sample outputs
```

## Key questions

1. Can pyvalhalla query planet-scale precomputed tiles from Python? → See script 010
2. Is Valhalla's tile directory layout object-storage friendly? → See script 020
3. Can tiles be fetched via HTTP Range Requests against the tar? → See scripts 030/040
4. What would a production CESG routing artifact look like? → See docs/findings.md

## pyvalhalla Actor API

```python
import valhalla, json

# Load patched config (created by 001_check_env.py)
actor = valhalla.Actor("outputs/valhalla_local.json")

result = actor.route({
    "locations": [
        {"lon": 139.767125, "lat": 35.681236},  # Tokyo Station
        {"lon": 139.700464, "lat": 35.689487},  # Shinjuku
    ],
    "costing": "auto",
    "directions_options": {"units": "km"},
})
print(result["trip"]["summary"])
```

## Tokyo Valhalla tile reproduction

Reproduce a Tokyo routing graph from the Kanto PBF without touching the planet-scale tiles.

### Prerequisites

- Docker installed and running
- Kanto PBF at `/data/www/html/static/openstreetmap/region/kanto-260423.osm.pbf` (443 MB)
- pyvalhalla 3.7.0 in `.venv/`

### Pipeline

```bash
# Step 1: Prepare input data (symlink Kanto PBF)
bash scripts/100_prepare_tokyo_data.sh

# Step 2: Build tiles with Docker (15–45 minutes)
bash scripts/110_build_tokyo_valhalla_tiles.sh

# Step 3: Patch valhalla.json for host-side use
.venv/bin/python scripts/120_patch_tokyo_valhalla_config.py

# Step 4: Run a route: Tokyo Station → Shinjuku
.venv/bin/python scripts/130_route_tokyo_one.py

# Step 5: Inspect tile layout
.venv/bin/python scripts/140_inspect_tokyo_tiles.py
```

Outputs land in `outputs/tokyo-*`. See `docs/tokyo-valhalla-pipeline.md` for details.

### Local server

```bash
# Install all deps (fastapi, uvicorn, httpx included in main deps)
.venv/bin/pip install -e .

# Start server (uses local Tokyo tiles via env vars)
.venv/bin/python scripts/200_run_local_server.py
```

### curl test

```bash
# Liveness
curl http://localhost:8080/healthz

# Readiness
curl http://localhost:8080/readyz

# Route: Tokyo Station → Shinjuku
curl -X POST http://localhost:8080/route \
  -H 'Content-Type: application/json' \
  -d '{"costing":"auto","start":[139.767125,35.681236],"end":[139.700464,35.689487]}' \
  | python3 -m json.tool
```

### Docker build and run

```bash
# Build image
bash scripts/210_build_route_server_image.sh
# or: docker build -f docker/Dockerfile -t poc-cesg-route-search:0.1.0 .

# Run container with local tiles bind-mounted
bash scripts/220_run_route_server_container.sh
```

### Knative deploy

```bash
# Apply ksvc (downloads tiles from object storage on cold start)
kubectl apply -f k8s/ksvc.yaml
```

See `docs/knative-deploy.md` for cold start details, tile_extract vs tile_dir mode,
and the future Range Request tile fetcher design.

---

## Notes

- Do NOT copy `valhalla_tiles/`, `valhalla_tiles.tar`, or `planet-latest.osm.pbf`
- The original `valhalla.json` uses Docker `/custom_files/` paths — always use the runtime-patched `outputs/valhalla_local.json` (planet) or `data/tokyo/valhalla/valhalla.host.json` (Tokyo)
- Use `.venv/bin/python` (not system Python) for all script runs
