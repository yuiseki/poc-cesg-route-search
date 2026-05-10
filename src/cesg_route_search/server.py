"""
server.py — FastAPI route search service backed by pyvalhalla.

Environment variables:
    TOKYO_VALHALLA_CONFIG   path to valhalla.host.json (required)

Usage:
    uvicorn cesg_route_search.server:app --host 0.0.0.0 --port 8000
"""

import json
import os
import time
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError as e:
    raise ImportError(
        "FastAPI and pydantic are required. "
        "Install with: pip install fastapi uvicorn pyvalhalla"
    ) from e

try:
    import valhalla
except ImportError as e:
    raise ImportError("pyvalhalla is required. Install with: pip install pyvalhalla") from e

# ---------------------------------------------------------------------------
# Startup: load Valhalla Actor once
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(
    os.environ.get(
        "TOKYO_VALHALLA_CONFIG",
        "/data/valhalla/valhalla.host.json",
    )
)

if not CONFIG_PATH.exists():
    raise FileNotFoundError(
        f"Valhalla config not found: {CONFIG_PATH}\n"
        "Set TOKYO_VALHALLA_CONFIG env var to the path of valhalla.host.json"
    )

with open(CONFIG_PATH) as _f:
    _cfg = json.load(_f)

# Force tile_dir mode
_cfg["mjolnir"]["tile_extract"] = ""

print(f"[startup] Loading Valhalla Actor from: {CONFIG_PATH}")
_actor = valhalla.Actor(_cfg)
print("[startup] Actor ready.")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CESG Route Search",
    description="Cloud-Native Geospatial route search using pyvalhalla",
    version="0.1.0",
)


class RouteRequest(BaseModel):
    costing: str = "auto"
    start: list[float]  # [lon, lat]
    end: list[float]    # [lon, lat]


class RouteMetadata(BaseModel):
    engine: str
    costing: str
    runtime_ms: float


class RouteResponse(BaseModel):
    distance_m: float | None
    time_s: float | None
    geometry: dict
    metadata: RouteMetadata


@app.post("/route", response_model=RouteResponse)
def route(req: RouteRequest) -> RouteResponse:
    """Compute a route between two points."""
    if len(req.start) != 2 or len(req.end) != 2:
        raise HTTPException(status_code=400, detail="start and end must be [lon, lat] pairs")

    request_body = {
        "locations": [
            {"lon": req.start[0], "lat": req.start[1]},
            {"lon": req.end[0], "lat": req.end[1]},
        ],
        "costing": req.costing,
        "directions_options": {"units": "km"},
    }

    t0 = time.perf_counter()
    try:
        response = _actor.route(request_body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Valhalla route error: {e}")
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    # Extract summary
    summary = response.get("trip", {}).get("summary", {})
    distance_m = round(summary.get("length", 0) * 1000, 1) if summary.get("length") else None
    time_s = summary.get("time")

    # Build GeoJSON LineString from first leg
    coords: list[list[float]] = []
    legs = response.get("trip", {}).get("legs", [])
    if legs:
        from cesg_route_search.geojson import decode_polyline6
        shape = legs[0].get("shape", "")
        if shape:
            coords = decode_polyline6(shape)

    geometry = {"type": "LineString", "coordinates": coords}

    return RouteResponse(
        distance_m=distance_m,
        time_s=time_s,
        geometry=geometry,
        metadata=RouteMetadata(
            engine="valhalla",
            costing=req.costing,
            runtime_ms=elapsed_ms,
        ),
    )


@app.get("/health")
def health():
    return {"status": "ok"}
