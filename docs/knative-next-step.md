# Knative Routing Service — Design Memo

## API contract

```
POST /route
Content-Type: application/json

{
  "costing": "auto",
  "start": [139.767125, 35.681236],
  "end":   [139.700464, 35.689487]
}

→ 200 OK
{
  "distance_m": 7618.0,
  "time_s": 934,
  "geometry": {
    "type": "LineString",
    "coordinates": [[139.767125, 35.681236], ..., [139.700464, 35.689487]]
  },
  "metadata": {
    "engine": "valhalla",
    "costing": "auto",
    "runtime_ms": 120
  }
}
```

---

## Architecture options

### Option A: Mounted tile_dir volume (current approach)

The Knative pod mounts a volume containing `valhalla_tiles/`, `admins.sqlite`,
`timezones.sqlite`, and `valhalla.host.json`.

**Pros:**
- Works today with pyvalhalla 3.7.0
- No network I/O during routing
- Sub-second latency once tiles are loaded

**Cons:**
- Large PVC required (1–5 GB for Tokyo, ~90 GB for planet)
- Cold-start dominated by tile index load (~500 ms–5 s)
- Volume must be pre-populated before pod starts

**When to use:** Development, single-region deployments, on-prem Kubernetes.

---

### Option B: tar + manifest + Range Request fetcher (future)

On cold start, the service:
1. Downloads `valhalla_tiles.manifest.json` (~few MB) from object storage
2. Receives route query; determines needed tiles from Valhalla tile selection logic
3. Fetches each tile via `Range: bytes=<offset>-<offset+size-1>` against the tar on S3/GCS
4. Writes tiles to a ramdisk or tmpfs directory
5. Initializes `valhalla.Actor(cfg)` pointing to tmpfs
6. Returns route result

**Pros:**
- No large PVC; tiles live in object storage
- Stateless pods; any pod can serve any query
- Pay-per-use: only fetch tiles the route actually needs

**Cons:**
- Cold-start latency: N tile fetches × ~50 ms each = 250–1000 ms overhead
- More complex implementation (Range fetcher, ramdisk management)
- Object storage egress costs for cold routes

**When to use:** Cloud-native production, auto-scaling, serverless deployments.

---

### Option C: PMTiles-like single-file archive (future)

Design a Valhalla-specific single-file tile archive with:
- A header + tile-existence bitmap
- Per-tile offset/size table (seekable)
- Tiles stored in Valhalla-native binary format

Clients fetch only the header (~few KB) on startup, then individual tiles
via Range Requests as needed.

**Pros:**
- Single object in storage (easy to replicate, cache, CDN-serve)
- No tar overhead (no 512-byte tar header padding)
- Can add compression per tile (zstd)

**Cons:**
- Requires custom reader (no existing Valhalla support)
- More engineering effort than Options A/B

**When to use:** Long-term, after validating Option B end-to-end.

---

## Recommended path

1. **Now:** Option A with Tokyo tiles (scripts 100–140 in this repo)
2. **Next:** Implement Option B with the existing tar manifest (script 040)
   and a FastAPI proxy server (see `src/cesg_route_search/server.py`)
3. **Future:** Option C as a CESG artifact spec proposal

---

## Knative service configuration sketch

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: valhalla-tokyo-router
spec:
  template:
    spec:
      containers:
      - image: ghcr.io/yuiseki/cesg-route-search:latest
        env:
        - name: TOKYO_VALHALLA_CONFIG
          value: /data/valhalla/valhalla.host.json
        volumeMounts:
        - name: valhalla-tiles
          mountPath: /data/valhalla
        resources:
          requests:
            memory: "4Gi"
            cpu: "1"
          limits:
            memory: "8Gi"
      volumes:
      - name: valhalla-tiles
        persistentVolumeClaim:
          claimName: tokyo-valhalla-tiles-pvc
```

## Cold-start optimization

- Pre-load tile index at container startup (not on first request)
- Use `GOMAXPROCS` / worker threads tuned for pyvalhalla
- Keep one warm replica (Knative `minScale: 1`) to eliminate cold-start for
  production traffic
