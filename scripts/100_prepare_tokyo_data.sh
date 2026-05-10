#!/usr/bin/env bash
set -euo pipefail

ROUTE_PBF_SOURCE=${ROUTE_PBF_SOURCE:-/data/www/html/static/openstreetmap/region/kanto-260423.osm.pbf}
USE_OSMIUM_EXTRACT=${USE_OSMIUM_EXTRACT:-false}
TOKYO_BBOX_BUFFERED=${TOKYO_BBOX_BUFFERED:-139.20,35.25,140.20,36.10}
TOKYO_DATA_DIR=${TOKYO_DATA_DIR:-$PWD/data/tokyo}

mkdir -p "$TOKYO_DATA_DIR/input" "$TOKYO_DATA_DIR/valhalla"

if [[ ! -f "$ROUTE_PBF_SOURCE" ]]; then
    echo "ERROR: ROUTE_PBF_SOURCE not found: $ROUTE_PBF_SOURCE"; exit 1
fi

PBF_BASENAME=$(basename "$ROUTE_PBF_SOURCE")
INPUT_PBF="$TOKYO_DATA_DIR/input/$PBF_BASENAME"

if [[ "$USE_OSMIUM_EXTRACT" == "true" ]]; then
    echo "Extracting bbox $TOKYO_BBOX_BUFFERED from $ROUTE_PBF_SOURCE"
    osmium extract --bbox "$TOKYO_BBOX_BUFFERED" "$ROUTE_PBF_SOURCE" -o "$TOKYO_DATA_DIR/input/tokyo-buffered.osm.pbf" --overwrite
    INPUT_PBF="$TOKYO_DATA_DIR/input/tokyo-buffered.osm.pbf"
else
    echo "Creating symlink: $INPUT_PBF -> $ROUTE_PBF_SOURCE"
    ln -sf "$ROUTE_PBF_SOURCE" "$INPUT_PBF"
fi

echo "Done. Input PBF: $INPUT_PBF"
ls -lh "$TOKYO_DATA_DIR/input/"
