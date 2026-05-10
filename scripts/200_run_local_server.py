#!/usr/bin/env python3
"""Launch local FastAPI server for testing.

Usage:
    .venv/bin/python scripts/200_run_local_server.py

Or with explicit env overrides:
    VALHALLA_ARTIFACT_MODE=tile_dir .venv/bin/python scripts/200_run_local_server.py

Then test:
    curl -s http://localhost:8080/healthz
    curl -s http://localhost:8080/readyz
    curl -s -X POST http://localhost:8080/route \\
      -H 'Content-Type: application/json' \\
      -d '{"costing":"auto","start":[139.767125,35.681236],"end":[139.700464,35.689487]}' \\
      | python3 -m json.tool
"""

import os
import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
data_dir = repo_root / "data" / "tokyo" / "valhalla"

os.environ.setdefault("VALHALLA_LOCAL_TILE_EXTRACT_SOURCE", str(data_dir / "valhalla_tiles.tar"))
os.environ.setdefault("VALHALLA_LOCAL_CONFIG_SOURCE", str(data_dir / "valhalla.host.json"))
os.environ.setdefault("VALHALLA_LOCAL_DIR", "/tmp/valhalla")
os.environ.setdefault("VALHALLA_LOCAL_TILE_EXTRACT", "/tmp/valhalla/valhalla_tiles.tar")
os.environ.setdefault("VALHALLA_LOCAL_CONFIG", "/tmp/valhalla/valhalla.json")
os.environ.setdefault("VALHALLA_ARTIFACT_MODE", "tile_extract")

sys.path.insert(0, str(repo_root / "src"))

try:
    import uvicorn
except ImportError:
    print(
        "[ERROR] uvicorn not installed.\n"
        "  Install with: .venv/bin/pip install -e .",
        file=sys.stderr,
    )
    sys.exit(1)

uvicorn.run("cesg_route_search.app:app", host="0.0.0.0", port=8080, reload=False)
