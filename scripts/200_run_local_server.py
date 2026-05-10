#!/usr/bin/env python3
"""
200_run_local_server.py — Start the local FastAPI route search server.

Requires: pip install fastapi uvicorn (or pip install -e ".[server]")

Usage:
    TOKYO_VALHALLA_CONFIG=data/tokyo/valhalla/valhalla.host.json \
    .venv/bin/python scripts/200_run_local_server.py

Then test:
    curl -s -X POST http://localhost:8000/route \
      -H 'Content-Type: application/json' \
      -d '{"costing":"auto","start":[139.767125,35.681236],"end":[139.700464,35.689487]}' \
      | python3 -m json.tool
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG = REPO_ROOT / "data" / "tokyo" / "valhalla" / "valhalla.host.json"

if "TOKYO_VALHALLA_CONFIG" not in os.environ:
    os.environ["TOKYO_VALHALLA_CONFIG"] = str(DEFAULT_CONFIG)

if not Path(os.environ["TOKYO_VALHALLA_CONFIG"]).exists():
    print(
        f"[ERROR] Config not found: {os.environ['TOKYO_VALHALLA_CONFIG']}\n"
        "  Run scripts/120_patch_tokyo_valhalla_config.py first.",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import uvicorn
except ImportError:
    print(
        "[ERROR] uvicorn not installed.\n"
        "  Install with: .venv/bin/pip install 'fastapi' 'uvicorn[standard]'",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"Starting server with config: {os.environ['TOKYO_VALHALLA_CONFIG']}")
uvicorn.run(
    "cesg_route_search.server:app",
    host="0.0.0.0",
    port=8000,
    reload=False,
)
