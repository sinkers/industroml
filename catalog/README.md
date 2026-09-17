# Catalog

This directory contains the IndustrialML master catalogue and icon assets.

- `master_catalog.yaml` — base element and connector types, with default attributes and typical interfaces.
- `icon_map.yaml` — mapping from logical icon keys to SVG files under `icons/`.
- `icons/` — domain-specific SVG icons used by renderers/editors.

Notes:

- The current icon set includes simple, custom SVG placeholders for each domain.
- The README references external sources for symbols; those assets are not bundled here due to licensing. You can replace or extend the icons by updating `icon_map.yaml` and adding SVGs under `icons/`.
- Suggested sources (see root README):
  - Mechanical P&ID symbols
  - Electrical SLD symbols
  - Networking equipment icons

