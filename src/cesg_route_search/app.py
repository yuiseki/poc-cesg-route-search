"""FastAPI route search service backed by pyvalhalla."""

import json
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .geojson import decode_polyline6
from .valhalla_actor import get_actor, get_artifact_mode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _warm_up():
    """Initialize Valhalla Actor in a background thread so uvicorn starts immediately."""
    try:
        get_actor()
        logger.info("Valhalla Actor initialized (background)")
    except Exception as e:
        logger.error("Actor init failed (background): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Actor initialization in background — do NOT block uvicorn startup.
    # Knative readiness probes hit /healthz (TCP or HTTP) immediately after the
    # port opens. Blocking here would cause "Initial scale was never achieved".
    t = threading.Thread(target=_warm_up, daemon=True)
    t.start()
    yield


app = FastAPI(title="poc-cesg-route-search", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # PoC only
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class RouteRequest(BaseModel):
    costing: str = "auto"
    start: list[float]  # [lon, lat]
    end: list[float]    # [lon, lat]


def _health_payload() -> dict:
    return {
        "ok": True,
        "status": "ok",
        "service": "poc-cesg-route-search",
    }


@app.get("/")
def root():
    return {
        **_health_payload(),
        "endpoints": {
            "health": "/health",
            "healthz": "/healthz",
            "readyz": "/readyz",
            "route": "/route",
        },
    }


@app.get("/health")
def health():
    return _health_payload()


@app.get("/healthz")
def healthz():
    return _health_payload()


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
    from .valhalla_actor import _actor as _current_actor
    if _current_actor is None:
        raise HTTPException(status_code=503, detail="Actor not yet initialized — retry in a moment")
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
