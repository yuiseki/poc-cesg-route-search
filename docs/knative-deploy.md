# Knative Deployment Guide: poc-cesg-route-search

## Overview

The FastAPI route search service wraps pyvalhalla and exposes three endpoints:
- `GET /healthz` — liveness probe
- `GET /readyz` — readiness probe (true once Actor is initialized)
- `POST /route` — route search

## Prerequisites

- Docker installed and running
- kubectl with Knative Serving installed (namespace: `knative-pool`)
- Tokyo Valhalla tiles built (`data/tokyo/valhalla/valhalla_tiles.tar`, 819 MB)

## Artifact modes

### tile_extract (recommended for Knative)

Valhalla loads the `.tar` archive directly via mmap. Faster init, no disk extraction needed.
The 819 MB tar must be accessible at `VALHALLA_LOCAL_TILE_EXTRACT`.

```
VALHALLA_ARTIFACT_MODE=tile_extract
VALHALLA_LOCAL_TILE_EXTRACT=/tmp/valhalla/valhalla_tiles.tar
```

Cold start time is dominated by the 819 MB tar download (~30–120s depending on bandwidth).
Requires `ephemeral-storage: 2Gi` in the Knative pod spec.

### tile_dir (fallback)

If tile_extract init fails (e.g. mmap issues), the Actor falls back to a directory of
individual tile files. When `VALHALLA_FALLBACK_EXTRACT_TO_TILE_DIR=true` and a tar exists,
it will be extracted automatically. Extraction takes ~10–30s additional time.

## Docker build

```bash
docker build -f docker/Dockerfile -t poc-cesg-route-search:0.1.0 .
# or
bash scripts/210_build_route_server_image.sh
```

pyvalhalla requires libprotobuf and libsqlite3. These are installed via apt in the Dockerfile.

## Local server test (uvicorn directly)

```bash
# Install deps
.venv/bin/pip install -e .

# Start server (uses local Tokyo tiles)
.venv/bin/python scripts/200_run_local_server.py

# Or manually with env vars:
VALHALLA_LOCAL_TILE_EXTRACT_SOURCE=data/tokyo/valhalla/valhalla_tiles.tar \
VALHALLA_LOCAL_CONFIG_SOURCE=data/tokyo/valhalla/valhalla.host.json \
VALHALLA_LOCAL_DIR=/tmp/valhalla \
VALHALLA_LOCAL_TILE_EXTRACT=/tmp/valhalla/valhalla_tiles.tar \
VALHALLA_LOCAL_CONFIG=/tmp/valhalla/valhalla.json \
VALHALLA_ARTIFACT_MODE=tile_extract \
.venv/bin/uvicorn cesg_route_search.app:app --host 0.0.0.0 --port 8080
```

## Local server test (Docker)

```bash
bash scripts/220_run_route_server_container.sh
```

This bind-mounts the local tar and config read-only into the container.

## curl test

```bash
# Liveness
curl http://localhost:8080/healthz

# Readiness (ready: true once Actor initialized)
curl http://localhost:8080/readyz

# Route: Tokyo Station → Shinjuku
curl -X POST http://localhost:8080/route \
  -H 'Content-Type: application/json' \
  -d '{"costing": "auto", "start": [139.767125, 35.681236], "end": [139.700464, 35.689487]}' \
  | python3 -m json.tool
```

Expected response:
```json
{
  "distance_m": 7618.0,
  "time_s": 878.4,
  "runtime_ms": 97.3,
  "geometry": {"type": "LineString", "coordinates": [...]},
  "metadata": {"engine": "valhalla", "binding": "pyvalhalla", "costing": "auto", "artifact_mode": "tile_extract"}
}
```

## Knative ksvc apply

```bash
kubectl apply -f k8s/ksvc.yaml
```

The ksvc downloads the tar and config from `https://z.yuiseki.net/static/cesg/tokyo/`
on cold start. Upload those files before deploying.

### Cold start implications

- 819 MB tar download at cold start
- tile_extract mode: no extraction step, ~30–120s for download only
- `timeoutSeconds: 300` allows up to 5 minutes for cold start
- `ephemeral-storage: 2Gi` request covers the 819 MB tar + config + overhead
- Scale-to-zero is supported (`min-scale: "0"`)

## Future: Range Request tile fetcher

The next step is a per-tile Range Request fetcher that avoids downloading the full 819 MB
on cold start:

1. Download the 2.8 MB manifest (`valhalla_tiles.manifest.json`) at startup
2. For each routing query, determine which tiles are needed
3. Fetch only those tiles via HTTP Range Request against `valhalla_tiles.tar`
4. Write to a temp dir and initialize `valhalla.Actor` with `tile_dir`

This would reduce cold start data to ~2.8 MB + query-time tile fetches (~5–20 tiles per
city-scale route, ~123 KB median tile size → ~0.6–2.5 MB per query).

See `docs/findings.md` section 4 for the Range Request manifest format.
