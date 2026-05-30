#!/usr/bin/env bash
set -euo pipefail

MAP_DIR="data/input/maps"
MAP_NAME="ne_50m_admin_0_countries"
MAP_URL="https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip"

mkdir -p "$MAP_DIR"

rm -rf "$MAP_DIR/$MAP_NAME"
mkdir -p "$MAP_DIR/$MAP_NAME"

curl -L -o "$MAP_DIR/$MAP_NAME.zip" "$MAP_URL"

unzip -q -o "$MAP_DIR/$MAP_NAME.zip" -d "$MAP_DIR/$MAP_NAME"

rm "$MAP_DIR/$MAP_NAME.zip"

if [ ! -f "$MAP_DIR/$MAP_NAME/$MAP_NAME.shp" ]; then
  echo "Map download failed: missing $MAP_DIR/$MAP_NAME/$MAP_NAME.shp"
  exit 1
fi

echo "Map data ready at $MAP_DIR/$MAP_NAME"
