"""FastAPI route search service backed by pyvalhalla."""

import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .geojson import decode_polyline6
from .valhalla_actor import get_actor, get_artifact_mode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up Actor on startup
    try:
        get_actor()
        logger.info("Valhalla Actor initialized at startup")
    except Exception as e:
        logger.error("Actor init failed at startup: %s", e)
    yield


app = FastAPI(title="poc-cesg-route-search", lifespan=lifespan)


class RouteRequest(BaseModel):
    costing: str = "auto"
    start: list[float]  # [lon, lat]
    end: list[float]    # [lon, lat]


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "poc-cesg-route-search"}


@app.get("/readyz")
def readyz():
    from .valhalla_actor import _actor

    initialized = _actor is not None
    return {
        "ready": initialized,
        "actor_initialized": initialized,
        "mode": get_artifact_mode() if initialized else "not_initialized",
    }


@app.post("/route")
def route(req: RouteRequest):
    actor = get_actor()
    valhalla_req = {
        "locations": [
            {"lon": req.start[0], "lat": req.start[1]},
            {"lon": req.end[0], "lat": req.end[1]},
        ],
        "costing": req.costing,
        "directions_options": {"units": "km"},
    }
    t0 = time.monotonic()
    try:
        raw = actor.route(json.dumps(valhalla_req))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    runtime_ms = (time.monotonic() - t0) * 1000

    result = json.loads(raw)
    trip = result.get("trip", {})
    summary = trip.get("summary", {})
    legs = trip.get("legs", [])

    # Decode shape from first leg
    coordinates = []
    if legs:
        shape = legs[0].get("shape", "")
        if shape:
            coordinates = decode_polyline6(shape)

    distance_m = round(summary.get("length", 0) * 1000, 1)  # km → m
    time_s = round(summary.get("time", 0), 1)

    return {
        "distance_m": distance_m,
        "time_s": time_s,
        "runtime_ms": round(runtime_ms, 1),
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates,
        },
        "metadata": {
            "engine": "valhalla",
            "binding": "pyvalhalla",
            "costing": req.costing,
            "artifact_mode": get_artifact_mode(),
        },
    }
