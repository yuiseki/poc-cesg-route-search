"""Route search helpers wrapping the pyvalhalla Actor API."""

import json
import time
from typing import Any


def build_route_request(
    origin_lon: float,
    origin_lat: float,
    dest_lon: float,
    dest_lat: float,
    costing: str = "auto",
    units: str = "km",
) -> dict:
    return {
        "locations": [
            {"lon": origin_lon, "lat": origin_lat},
            {"lon": dest_lon, "lat": dest_lat},
        ],
        "costing": costing,
        "directions_options": {"units": units},
    }


def run_route(actor: Any, request: dict) -> tuple[dict, float]:
    """
    Run a route request through the pyvalhalla Actor.

    Returns (response_dict, elapsed_ms).
    """
    t0 = time.perf_counter()
    result = actor.route(request)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if isinstance(result, str):
        result = json.loads(result)

    return result, elapsed_ms


def extract_meta(response: dict, elapsed_ms: float) -> dict:
    """Extract distance_m, time_s, runtime_ms from a Valhalla route response."""
    try:
        summary = response["trip"]["summary"]
        distance_km = summary.get("length", 0.0)
        time_s = summary.get("time", 0.0)
        success = True
    except (KeyError, TypeError):
        distance_km = 0.0
        time_s = 0.0
        success = False

    return {
        "success": success,
        "distance_m": round(distance_km * 1000, 1),
        "time_s": round(time_s, 1),
        "runtime_ms": round(elapsed_ms, 2),
    }
