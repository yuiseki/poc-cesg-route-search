#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -f docker/Dockerfile -t poc-cesg-route-search:0.1.0 .
echo "Built: poc-cesg-route-search:0.1.0"
