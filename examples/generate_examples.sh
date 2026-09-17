#!/usr/bin/env bash
set -euo pipefail

# Generate example diagrams, PNGs, HTML, and JSON exports.
# Usage:
#   bash examples/generate_examples.sh [--renderer mermaid-cli|kroki] [--skip-png]

RENDERER=""
SKIP_PNG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --renderer)
      RENDERER="${2:-}"
      shift 2
      ;;
    --skip-png)
      SKIP_PNG=1
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--renderer mermaid-cli|kroki] [--skip-png]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
MODEL_DIR="$ROOT_DIR/examples/models"
OUT_DIR="$ROOT_DIR/examples/outputs"
GEN="$ROOT_DIR/generate.py"
PY=python3
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PY="$ROOT_DIR/.venv/bin/python"
fi

mkdir -p "$OUT_DIR"

MODEL="$MODEL_DIR/ravenbrook_site.yaml"
if [[ -n "${MODEL_OVERRIDE:-}" ]]; then MODEL="$MODEL_OVERRIDE"; fi

echo "Model: $MODEL"
echo "Generating Mermaid diagrams..."
"$PY" "$GEN" "$MODEL" --out "$OUT_DIR/diagram_all.mmd" --title "Ravenbrook (All Domains)" --catalog "$ROOT_DIR/catalog/master_catalog.yaml" --icon-map "$ROOT_DIR/catalog/icon_map.yaml"
"$PY" "$GEN" "$MODEL" --out "$OUT_DIR/diagram_electrical.mmd" --title "Ravenbrook (Electrical)" --domains electrical --catalog "$ROOT_DIR/catalog/master_catalog.yaml" --icon-map "$ROOT_DIR/catalog/icon_map.yaml"
"$PY" "$GEN" "$MODEL" --out "$OUT_DIR/diagram_mechanical.mmd" --title "Ravenbrook (Mechanical)" --domains mechanical --catalog "$ROOT_DIR/catalog/master_catalog.yaml" --icon-map "$ROOT_DIR/catalog/icon_map.yaml"
"$PY" "$GEN" "$MODEL" --out "$OUT_DIR/diagram_data_control.mmd" --title "Ravenbrook (Data+Control)" --domains data,control --catalog "$ROOT_DIR/catalog/master_catalog.yaml" --icon-map "$ROOT_DIR/catalog/icon_map.yaml"

if [[ $SKIP_PNG -eq 0 ]]; then
  echo "Generating PNGs (${RENDERER:-auto})..."
  RENDER_ARGS=()
  if [[ -n "$RENDERER" ]]; then RENDER_ARGS=(--renderer "$RENDERER"); fi
  "$PY" "$GEN" "$MODEL" --out "$OUT_DIR/diagram_all.mmd" --png "$OUT_DIR/diagram_all.png" "${RENDER_ARGS[@]}" --title "Ravenbrook (All Domains)" --catalog "$ROOT_DIR/catalog/master_catalog.yaml"
  "$PY" "$GEN" "$MODEL" --out "$OUT_DIR/diagram_electrical.mmd" --png "$OUT_DIR/diagram_electrical.png" "${RENDER_ARGS[@]}" --domains electrical --title "Ravenbrook (Electrical)" --catalog "$ROOT_DIR/catalog/master_catalog.yaml"
  "$PY" "$GEN" "$MODEL" --out "$OUT_DIR/diagram_mechanical.mmd" --png "$OUT_DIR/diagram_mechanical.png" "${RENDER_ARGS[@]}" --domains mechanical --title "Ravenbrook (Mechanical)" --catalog "$ROOT_DIR/catalog/master_catalog.yaml"
  "$PY" "$GEN" "$MODEL" --out "$OUT_DIR/diagram_data_control.mmd" --png "$OUT_DIR/diagram_data_control.png" "${RENDER_ARGS[@]}" --domains data,control --title "Ravenbrook (Data+Control)" --catalog "$ROOT_DIR/catalog/master_catalog.yaml"
fi

echo "Generating HTML tree and JSON exports..."
"$PY" "$GEN" "$MODEL" --html "$OUT_DIR/components.html" --title "Ravenbrook Components"
"$PY" "$GEN" "$MODEL" --export-tree-json "$OUT_DIR/tree.json" --export-graph-json "$OUT_DIR/graph.json" --title "Ravenbrook" --catalog "$ROOT_DIR/catalog/master_catalog.yaml" --icon-map "$ROOT_DIR/catalog/icon_map.yaml"

echo "Done. Outputs in: $OUT_DIR"
