# Examples

This repository ships a set of working examples that demonstrate the IndustrialML model, diagram generation, PNG export, and the HTML tree viewer.

## Layout

- `examples/models/`
  - Authoring models in YAML and JSON.
  - Example: `ravenbrook_site.yaml` and `ravenbrook_site.json`.
- `examples/outputs/`
  - Generated artifacts from the models.
  - Mermaid: `diagram_*.mmd`
  - PNG: `diagram_*.png`
  - HTML: `components.html`
  - JSON exports: `tree.json`, `graph.json`

## Ravenbrook Water Plant

- Model: `examples/models/ravenbrook_site.yaml`
- Generated outputs (in `examples/outputs/`):
  - All domains: `diagram_all.mmd` (+ `diagram_all.png` if PNG exported)
  - Electrical only: `diagram_electrical.mmd` and `diagram_electrical.png`
  - Mechanical only: `diagram_mechanical.mmd` and `diagram_mechanical.png`
  - Data + Control: `diagram_data_control.mmd` and `diagram_data_control.png`
  - Tree viewer: `components.html`
  - Structured exports: `tree.json`, `graph.json`

## Regenerating Examples

Use the helper script; it will place outputs in `examples/outputs/`.

```
bash examples/generate_examples.sh --renderer kroki
```

## Comprehensive Water/Wastewater Plant

- Model: `examples/models/water_plant_comprehensive.yaml`
- Includes HV→LV electrical path (TX→ACB→MSB→MCC→VFD→Motor), process equipment (pump, valves, strainers, HX, tank), control system (PLC I/O, HMI, SCADA, transmitters), data network (L3 switch, router, firewall, NAS), and safety devices (FACP, detectors).
- Use the same script to regenerate artifacts; set `MODEL` to this file if you want a targeted run.


Options:

- `--renderer mermaid-cli|kroki`  Choose PNG renderer.
  - `mermaid-cli` requires `mmdc` on PATH.
  - `kroki` uses https://kroki.io (requires network).
- `--skip-png`  Skip PNG export and only write `.mmd`, `.html`, and `.json`.

Examples:

- Use Mermaid CLI for local PNGs:
  - `bash examples/generate_examples.sh --renderer mermaid-cli`
- Use Kroki for PNGs (no local install):
  - `bash examples/generate_examples.sh --renderer kroki`
