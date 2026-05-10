#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOKYO_DIR="$REPO_ROOT/data/tokyo/valhalla"

docker run --rm -it \
  -p 8080:8080 \
  -v "$TOKYO_DIR/valhalla_tiles.tar:/tmp/valhalla/valhalla_tiles.tar:ro" \
  -v "$TOKYO_DIR/valhalla.host.json:/tmp/valhalla/valhalla.json:ro" \
  -e VALHALLA_LOCAL_DIR=/tmp/valhalla \
  -e VALHALLA_LOCAL_TILE_EXTRACT=/tmp/valhalla/valhalla_tiles.tar \
  -e VALHALLA_LOCAL_CONFIG=/tmp/valhalla/valhalla.json \
  -e VALHALLA_ARTIFACT_MODE=tile_extract \
  -e HOME=/tmp \
  poc-cesg-route-search:0.1.0
