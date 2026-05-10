#!/usr/bin/env bash
# 900_build_small_valhalla_tiles_optional.sh
#
# Optional: build a small regional Valhalla tile set (e.g., Tokyo area only)
# using the official Valhalla Docker image. This is NOT needed for the main PoC
# (which uses the planet-scale precomputed tiles), but useful if you want a
# fast-loading local tile set for iteration.
#
# Prerequisites:
#   docker pull ghcr.io/valhalla/valhalla-scripted:latest
#   Download a regional OSM extract, e.g. Kanto from GeoFabrik:
#     wget https://download.geofabrik.de/asia/japan/kanto-latest.osm.pbf
#
# Usage:
#   bash scripts/900_build_small_valhalla_tiles_optional.sh /path/to/kanto-latest.osm.pbf ./data/kanto

set -euo pipefail

PBF_FILE="${1:-}"
OUTPUT_DIR="${2:-./data/small_valhalla_tiles}"

if [[ -z "$PBF_FILE" ]] || [[ ! -f "$PBF_FILE" ]]; then
  echo "Usage: $0 <path-to.osm.pbf> [output-dir]"
  echo ""
  echo "Example:"
  echo "  $0 kanto-latest.osm.pbf ./data/kanto"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Building Valhalla tiles from: $PBF_FILE"
echo "Output dir: $OUTPUT_DIR"
echo ""
echo "Running Valhalla Docker container..."

docker run --rm \
  -v "$(realpath "$PBF_FILE"):/data/input.osm.pbf:ro" \
  -v "$(realpath "$OUTPUT_DIR"):/custom_files" \
  ghcr.io/valhalla/valhalla-scripted:latest \
  valhalla_build_tiles -c /custom_files/valhalla.json /data/input.osm.pbf

echo ""
echo "Done. Tiles are in: $OUTPUT_DIR"
echo "Set VALHALLA_TILES_DIR=$OUTPUT_DIR in your .env to use them."
