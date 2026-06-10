from __future__ import annotations

import sys
import types
from unittest.mock import patch

from fastapi.testclient import TestClient

valhalla = types.ModuleType("valhalla")


class Actor:
    def __init__(self, *args, **kwargs):
        pass


valhalla.Actor = Actor
sys.modules.setdefault("valhalla", valhalla)

from cesg_route_search.app import app


def test_root_returns_service_info():
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "poc-cesg-route-search"
    assert data["endpoints"]["health"] == "/health"
    assert data["endpoints"]["healthz"] == "/healthz"
    assert data["endpoints"]["readyz"] == "/readyz"


def test_health_alias():
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["status"] == "ok"
    assert data["service"] == "poc-cesg-route-search"


def test_healthz():
    with patch("cesg_route_search.app._actor_ready", return_value=True), \
         patch("cesg_route_search.app.get_artifact_mode", return_value="tile_extract"):
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["status"] == "ok"
    assert data["service"] == "poc-cesg-route-search"
    assert data["actor_initialized"] is True
    assert data["artifact_mode"] == "tile_extract"


def test_healthz_returns_ng_when_actor_not_initialized():
    with patch("cesg_route_search.app._actor_ready", return_value=False):
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/healthz")
    assert r.status_code == 503
    data = r.json()
    assert data["ok"] is False
    assert data["status"] == "ng"
    assert data["service"] == "poc-cesg-route-search"
    assert data["actor_initialized"] is False
