# Tokyo Valhalla Tile Reproduction Pipeline

## Why reproduce Tokyo tiles?

The planet-scale tiles at `/everything/src/github.com/yuiseki/osm-planet-in-da-house/data/valhalla/`
are read-only and cannot be moved or copied. They total ~90 GB and are not suitable
for embedding in a container image or portable deployment artifact.

Reproducing regional tiles for the Kanto/Tokyo area gives us:

1. **Portability** — a ~1–5 GB tile set that can be bundled or served independently
2. **Reproducibility** — the full build pipeline is versioned in this repo
3. **Knative-readiness** — a service that loads ~few-hundred-MB tiles can cold-start
   in <30 s vs. several minutes for the full planet set

---

## Kanto PBF rationale

The Kanto PBF (`kanto-260423.osm.pbf`, 443 MB, dated 2026-04-23) covers:

- Tokyo-to (23 wards + Tama area)
- Kanagawa, Saitama, Chiba, Ibaraki, Tochigi, Gunma, Yamanashi prefectures

Using the full Kanto extract (rather than a tight Tokyo bbox) preserves **road
connectivity across prefecture boundaries**. Routes that naturally extend through
Saitama or Chiba are correctly resolved.

### Warning: narrow bbox cuts = disconnected road graph

If you use `USE_OSMIUM_EXTRACT=true` with a very tight bbox (e.g., 23-ward Tokyo
only), Valhalla may fail to resolve routes near the border because the road graph
is severed at the bbox edge. The buffered bbox `TOKYO_BBOX_BUFFERED=139.20,35.25,140.20,36.10`
covers the full metropolitan area and is the recommended default.

---

## Docker Valhalla scripted image approach

`ghcr.io/valhalla/valhalla-scripted:latest` is a convenience image that runs the
full tile-build pipeline automatically when invoked:

```bash
docker run \
  --rm \
  -e serve_tiles=False \
  -e use_tiles_ignore_pbf=False \
  -e force_rebuild=True \
  -v "$TOKYO_VALHALLA_DIR:/custom_files" \
  ghcr.io/valhalla/valhalla-scripted:latest
```

The image:
1. Scans `/custom_files/` for `*.osm.pbf` files
2. Runs `valhalla_build_config` to generate `valhalla.json`
3. Runs `valhalla_build_admins` → `admins.sqlite`
4. Runs `valhalla_build_timezones` → `timezones.sqlite`
5. Runs `valhalla_build_tiles` → `valhalla_tiles/`

All output lands in `/custom_files/`, which maps to `data/tokyo/valhalla/` on the host.

**Expected build time:** 15–45 minutes for 443 MB Kanto PBF on a modern workstation.

---

## Why valhalla.json needs patching for host-side pyvalhalla

The Docker image writes `valhalla.json` with all paths referencing `/custom_files/`,
e.g.:

```json
{
  "mjolnir": {
    "tile_dir": "/custom_files/valhalla_tiles",
    "admin": "/custom_files/admins.sqlite",
    "timezone": "/custom_files/timezones.sqlite"
  }
}
```

When `valhalla.Actor()` is called from the host (outside Docker), these paths do not
exist. `scripts/120_patch_tokyo_valhalla_config.py` rewrites them to absolute host
paths and saves the result as `valhalla.host.json`. This is the file used by all
subsequent route-search scripts.

---

## Pipeline steps

```
Step 1: bash scripts/100_prepare_tokyo_data.sh
        → Creates symlink data/tokyo/input/kanto-260423.osm.pbf → /data/...

Step 2: bash scripts/110_build_tokyo_valhalla_tiles.sh
        → Runs Docker build (15–45 min); outputs to data/tokyo/valhalla/

Step 3: .venv/bin/python scripts/120_patch_tokyo_valhalla_config.py
        → Patches /custom_files/ paths → writes valhalla.host.json

Step 4: .venv/bin/python scripts/130_route_tokyo_one.py
        → Tokyo Station → Shinjuku route; outputs to outputs/tokyo-route-one.*

Step 5: .venv/bin/python scripts/140_inspect_tokyo_tiles.py
        → Tile stats; outputs to outputs/tokyo-tile-layout-summary.*
```
