#!/usr/bin/env bash
set -euo pipefail

# Optional helper to fetch external icon packs referenced in the README.
# This script does not change icon_map.yaml; it downloads assets into
# catalog/icons/external/ for manual curation to avoid licensing surprises.

ROOT=$(cd "$(dirname "$0")" && pwd)
DEST="$ROOT/icons/external"
mkdir -p "$DEST"

echo "Fetching networking icons (ntwrk-clean-and-flat)..."
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

git clone --depth 1 https://github.com/DukeNuke3D/ntwrk-clean-and-flat "$TMP/ntwrk" >/dev/null 2>&1 || {
  echo "Failed to fetch ntwrk-clean-and-flat (check network)." >&2
  exit 1
}
mkdir -p "$DEST/ntwrk-clean-and-flat"
cp -R "$TMP/ntwrk"/* "$DEST/ntwrk-clean-and-flat/"
echo "Saved to $DEST/ntwrk-clean-and-flat"

echo "NOTE: Mechanical & Electrical symbol references in README are web pages, not downloadable packs."
echo "      Curate appropriate SVGs and place them under catalog/icons/ then update catalog/icon_map.yaml."

