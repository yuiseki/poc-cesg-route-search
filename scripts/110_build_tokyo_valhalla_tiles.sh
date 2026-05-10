#!/usr/bin/env bash
set -euo pipefail

TOKYO_DATA_DIR=${TOKYO_DATA_DIR:-$PWD/data/tokyo}
TOKYO_VALHALLA_DIR=${TOKYO_VALHALLA_DIR:-$TOKYO_DATA_DIR/valhalla}
ROUTE_PBF_SOURCE=${ROUTE_PBF_SOURCE:-/data/www/html/static/openstreetmap/region/kanto-260423.osm.pbf}
VALHALLA_DOCKER_MEMORY=${VALHALLA_DOCKER_MEMORY:-64g}
VALHALLA_DOCKER_MEMORY_SWAP=${VALHALLA_DOCKER_MEMORY_SWAP:-64g}
VALHALLA_DOCKER_SHM_SIZE=${VALHALLA_DOCKER_SHM_SIZE:-16g}
VALHALLA_DOCKER_NAME=${VALHALLA_DOCKER_NAME:-valhalla_tokyo}

# Find the PBF to use (prefer extracted, fall back to kanto symlink)
PBF_BASENAME=$(basename "$ROUTE_PBF_SOURCE")
RESOLVED_PBF="$TOKYO_DATA_DIR/input/$PBF_BASENAME"
if [[ -f "$TOKYO_DATA_DIR/input/tokyo-buffered.osm.pbf" ]]; then
    RESOLVED_PBF="$TOKYO_DATA_DIR/input/tokyo-buffered.osm.pbf"
fi

echo "=== Building Tokyo Valhalla tiles ==="
echo "Input PBF : $RESOLVED_PBF"
echo "Output dir: $TOKYO_VALHALLA_DIR"

# Resolve the actual PBF path (follow symlinks so Docker can bind-mount it)
REAL_PBF="$(realpath "$RESOLVED_PBF")"
echo "Resolved PBF (real path): $REAL_PBF"

# Mount the real PBF directly into /custom_files inside Docker.
# We do NOT symlink across the volume boundary — Docker bind-mounts don't
# follow symlinks that point outside the mounted directory.
docker run \
  --memory="$VALHALLA_DOCKER_MEMORY" \
  --memory-swap="$VALHALLA_DOCKER_MEMORY_SWAP" \
  --shm-size="$VALHALLA_DOCKER_SHM_SIZE" \
  --ulimit nofile=1048576:1048576 \
  --rm \
  --name "$VALHALLA_DOCKER_NAME" \
  -e serve_tiles=False \
  -e use_tiles_ignore_pbf=False \
  -e force_rebuild=True \
  -v "$TOKYO_VALHALLA_DIR:/custom_files" \
  -v "$REAL_PBF:/custom_files/tokyo.osm.pbf:ro" \
  ghcr.io/valhalla/valhalla-scripted:latest

echo "=== Build complete ==="
sudo chown -R "$(id -u):$(id -g)" "$TOKYO_VALHALLA_DIR" 2>/dev/null || true
ls -lh "$TOKYO_VALHALLA_DIR/"
