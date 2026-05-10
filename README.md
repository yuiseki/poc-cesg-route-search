# poc-cesg-route-search

Proof-of-concept for Cloud-Native Geospatial (CESG) route search using precomputed Valhalla routing graph tiles.

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

## Notes

- Do NOT copy `valhalla_tiles/`, `valhalla_tiles.tar`, or `planet-latest.osm.pbf`
- The original `valhalla.json` uses Docker `/custom_files/` paths — always use the runtime-patched `outputs/valhalla_local.json`
- Use `.venv/bin/python` (not system Python) for all script runs
