#!/usr/bin/env python3
"""
generate_diagram.py

Render an IndustroML (v0.1) model (JSON or YAML) into a Mermaid flowchart (.mmd).
Stdlib only for JSON; YAML requires PyYAML if you pass a .yaml/.yml file.
Produces subgraphs by containers and styles by domain. Optional PNG export.

Usage:
  python generate.py ravenbrook_site.json --out diagram.mmd
  python generate.py ravenbrook_site.yaml --out diagram.mmd

Optional flags:
  --title "My Plant Diagram"
  --direction LR   (or TB)
  --png diagram.png              (optional) render PNG via Mermaid CLI or Kroki
  --renderer mermaid-cli|kroki   (optional) prefer a renderer
  --html components.html         (optional) also write HTML tree viewer
  --domains electrical,mechanical  (optional) filter domains in diagram/exports
  --catalog catalog/master_catalog.yaml  (optional) use catalog to enrich exports (e.g., icon keys)
  --icon-map catalog/icon_map.yaml       (optional) map icon keys to SVG file paths in graph export
"""
from __future__ import annotations
import argparse, json, sys, re, os, shutil, subprocess, base64
from urllib import request
from collections import defaultdict
from typing import Dict, Any, List, Set, Tuple

DOMAIN_CLASS = {
    "electrical": "elec",
    "mechanical": "mech",
    "data": "data",
    "control": "ctrl",
    "safety": "safe",
}

CONN_LABEL_FIELDS = {
    "cable": ["csa_mm2", "cores", "insulation", "length_m", "method"],
    "pipe": ["material", "dn_mm", "schedule", "length_m", "service", "pressure_bar"],
    "data_link": ["medium", "category", "protocol", "speed_mbps", "vlan"],
    "io_link": ["signal", "range", "logic"],
}
# Also support README standard types for labels
CONN_LABEL_FIELDS.update({
    "low_voltage": CONN_LABEL_FIELDS["cable"],
    "high_voltage": CONN_LABEL_FIELDS["cable"],
    "fluid": CONN_LABEL_FIELDS["pipe"],
    "data": CONN_LABEL_FIELDS["data_link"],
})

# Map connector types to README's standard types for coloring
STD_CONNECTOR_TYPE = {
    "cable": "low_voltage",
    "low_voltage": "low_voltage",
    "high_voltage": "high_voltage",
    "pipe": "fluid",
    "fluid": "fluid",
    "data_link": "data",
    "data": "data",
    "io_link": "data",  # treat control I/O as data/control layer
}

CONNECTOR_COLORS = {
    "low_voltage": "#111827",   # black
    "high_voltage": "#dc2626",  # red
    "data": "#059669",         # green
    "fluid": "#2563eb",        # blue
}

def sanitize_id(s: str) -> str:
    """Mermaid node ids: letters, digits, underscore only."""
    return re.sub(r'[^A-Za-z0-9_]', '_', s)

def short_attrs(attrs: Dict[str, Any], keys: List[str]) -> str:
    chunks = []
    for k in keys:
        if k in attrs:
            chunks.append(f"{k}:{attrs[k]}")
    return ", ".join(chunks)

def load_model(path: str) -> Dict[str, Any]:
    """Load model from JSON or YAML based on extension."""
    _, ext = os.path.splitext(path)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if ext.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except Exception as e:
            print("YAML input requested but PyYAML is not installed.", file=sys.stderr)
            print("Install with: python -m pip install pyyaml", file=sys.stderr)
            sys.exit(2)
        return yaml.safe_load(text)
    else:
        return json.loads(text)

def normalize_model(model: Dict[str, Any]) -> Dict[str, Any]:
    """Accept README naming (elements/connectors) by mapping to assets/connections."""
    if "assets" not in model and "elements" in model:
        model["assets"] = model.get("elements", [])
    if "connections" not in model and "connectors" in model:
        model["connections"] = model.get("connectors", [])
    # No change otherwise
    return model

def load_catalog(catalog_path: str | None) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Load catalog and return mapping (domain, kind) -> element spec."""
    if not catalog_path:
        return {}
    try:
        import yaml  # type: ignore
    except Exception as e:
        print(f"Catalog '{catalog_path}' requested but PyYAML is missing.", file=sys.stderr)
        return {}
    try:
        with open(catalog_path, 'r', encoding='utf-8') as f:
            cat = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to read catalog: {e}", file=sys.stderr)
        return {}
    mapping: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for el in cat.get('elements', []) or []:
        dom = el.get('domain'); kind = el.get('kind')
        if dom and kind:
            mapping[(dom, kind)] = el
    return mapping

def index_by_id(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {it["id"]: it for it in items}

# Assets that can hold other assets. Must match validate_industroML.py.
ENCLOSURE_KINDS = {
    "switchboard", "mcc", "distribution_board", "panelboard",
    "busbar_section", "hmi_panel", "fire_alarm_panel",
}


def validate(model: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    assets = index_by_id(model.get("assets", []))
    ifaces = index_by_id(model.get("interfaces", []))
    conts = index_by_id(model.get("containers", []))

    # container parent refs
    for c in model.get("containers", []):
        pid = c.get("parent")
        if pid and pid not in conts:
            errs.append(f"Container {c['id']} parent {pid} missing")

    # interface -> asset
    for iface in model.get("interfaces", []):
        aid = iface.get("asset")
        if aid not in assets:
            errs.append(f"Interface {iface['id']} references missing asset {aid}")

    # asset -> container, which may be an enclosure asset rather than a
    # container: a breaker lives inside its MCC. Kept in step with
    # validate_industroML.py's ENCLOSURE_KINDS.
    for a in model.get("assets", []):
        cid = a.get("container")
        if not cid or cid in conts:
            continue
        host = assets.get(cid)
        if host is None:
            errs.append(f"Asset {a['id']} container {cid} missing")
        elif host.get("kind") not in ENCLOSURE_KINDS:
            errs.append(
                f"Asset {a['id']} is contained by asset {cid} of kind "
                f"'{host.get('kind')}', which is not an enclosure"
            )

    # connections from/to
    for c in model.get("connections", []):
        fr, to = c.get("from"), c.get("to")
        if fr not in ifaces:
            errs.append(f"Connection {c['id']} from {fr} missing interface")
        if to not in ifaces:
            errs.append(f"Connection {c['id']} to {to} missing interface")

    return errs

def build_container_tree(conts: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, List[str]]]:
    """Return root container id and children mapping."""
    by_parent: Dict[str, List[str]] = defaultdict(list)
    root_candidates: Set[str] = set(conts.keys())
    for cid, c in conts.items():
        pid = c.get("parent")
        if pid:
            by_parent[pid].append(cid)
            if cid in root_candidates:
                root_candidates.remove(cid)
    # pick a root: prefer 'SITE' if present, else any without parent
    root = "SITE" if "SITE" in root_candidates else (next(iter(root_candidates)) if root_candidates else "")
    return root, by_parent

BR = "<br/>"   # line break inside a Mermaid label


def label_for_asset(a: Dict[str, Any]) -> str:
    nm = a.get("name", a["id"])
    dom = a.get("domain", "")
    kind = a.get("kind", "")
    attrs = a.get("attributes", {})
    # a tight summary per domain
    summary = []
    if dom == "electrical":
        for k in ("voltage_v","current_a","power_kw","power_kva","switching"):
            if k in attrs: summary.append(f"{k.split('_')[0]}:{attrs[k]}")
    elif dom == "mechanical":
        for k in ("flow_m3h","head_m","dn_mm","volume_m3","material","rating_pressure_bar"):
            if k in attrs: summary.append(f"{k.split('_')[0]}:{attrs[k]}")
    elif dom in ("data","control","safety"):
        for k in ("protocol","speed_mbps","speed_gbps","interfaces","ports","slots","channels"):
            if k in attrs: summary.append(f"{k}:{attrs[k]}")
    # Mermaid 10+ does not accept a literal \n inside a node label; it wants an
    # HTML break. The old form emitted the two characters backslash-n, which
    # showed up verbatim in every rendered diagram.
    tail = BR.join(summary[:3])
    suffix = (BR + tail) if tail else ""
    return f"{nm}{BR}[{kind}/{dom}]" + suffix

def mermaid_escape(text: str) -> str:
    return text.replace('"','\\"')

def emit_mermaid(model: Dict[str, Any], direction: str = "LR", title: str = "", domains_filter: Set[str] | None = None) -> str:
    assets = index_by_id(model.get("assets", []))
    ifaces = index_by_id(model.get("interfaces", []))
    conts = index_by_id(model.get("containers", []))
    root, tree = build_container_tree(conts)

    # group assets by container
    by_container: Dict[str, List[str]] = defaultdict(list)
    for a in model.get("assets", []):
        if domains_filter and a.get("domain") not in domains_filter:
            continue
        by_container[a.get("container", "")].append(a["id"])

    lines: List[str] = []
    lines.append(f"flowchart {direction}")
    if title:
        lines.append(f'%% {mermaid_escape(title)}')

    # class defs (styles) — tweak as you like
    lines += [
        "classDef elec stroke-width:2px,stroke:#6b5cff,fill:#efefff;",
        "classDef mech stroke-width:2px,stroke:#1b7f2a,fill:#eefaf0;",
        "classDef data stroke-width:2px,stroke:#0b6a8b,fill:#eaf7fb;",
        "classDef ctrl stroke-width:2px,stroke:#b26b00,fill:#fff5e6;",
        "classDef safe stroke-width:2px,stroke:#b00020,fill:#fdecef;",
    ]

    # recursively emit subgraphs
    def walk_container(cid: str, depth: int = 0):
        c = conts[cid]
        sub_label = f"{c.get('name','') or cid} ({c.get('type','container')})"
        lines.append(f"subgraph {sanitize_id(cid)}[\"{mermaid_escape(sub_label)}\"]")
        # assets in this container
        for aid in by_container.get(cid, []):
            a = assets[aid]
            nid = sanitize_id(aid)
            lbl = label_for_asset(a)
            lines.append(f'{nid}["{mermaid_escape(lbl)}"]')
            # assign class
            dom = a.get("domain","")
            cls = DOMAIN_CLASS.get(dom)
            if cls:
                lines.append(f"class {nid} {cls};")
        # children
        for child in tree.get(cid, []):
            walk_container(child, depth+1)
        lines.append("end")

    if root:
        walk_container(root)
    else:
        # fallback: dump all assets flat
        for a in model.get("assets", []):
            nid = sanitize_id(a["id"])
            lbl = label_for_asset(a)
            lines.append(f'{nid}["{mermaid_escape(lbl)}"]')
            dom = a.get("domain","")
            cls = DOMAIN_CLASS.get(dom)
            if cls:
                lines.append(f"class {nid} {cls};")

    # edges: connect asset nodes (we can’t target ports in Mermaid, so label edge with interface names & key attrs)
    edge_index = -1
    edge_styles: List[Tuple[int, str]] = []  # (edge_index, std_type)
    for conn in model.get("connections", []):
        ctype = conn.get("type","")
        fr, to = conn["from"], conn["to"]
        fi, ti = ifaces.get(fr), ifaces.get(to)
        if not fi or not ti:
            # skip invalid; validator will have warned
            continue
        fa, ta = assets.get(fi["asset"]), assets.get(ti["asset"])
        if not fa or not ta:
            continue
        if domains_filter and (fa.get("domain") not in domains_filter or ta.get("domain") not in domains_filter):
            continue
        f_id, t_id = sanitize_id(fa["id"]), sanitize_id(ta["id"])
        # Build an informative label
        f_name = fi.get("name", fr.split(".")[-1])
        t_name = ti.get("name", to.split(".")[-1])
        fields = CONN_LABEL_FIELDS.get(ctype, [])
        attr_txt = short_attrs(conn.get("attributes", {}), fields)
        std_type = STD_CONNECTOR_TYPE.get(ctype, ctype or "")
        # Label with the schema's own connection type, not the legacy display
        # class. std_type still drives the colour, which is the README's
        # convention (black LV, red HV, blue fluid, green data).
        label = f"{ctype or std_type}:{f_name}→{t_name}" + (f" ({attr_txt})" if attr_txt else "")
        lines.append(f'{f_id} -- "{mermaid_escape(label)}" --> {t_id}')
        edge_index += 1
        if std_type in CONNECTOR_COLORS:
            edge_styles.append((edge_index, std_type))

    # Color edges by type per README
    for idx, std_type in edge_styles:
        color = CONNECTOR_COLORS[std_type]
        lines.append(f'linkStyle {idx} stroke:{color},stroke-width:2px,color:{color}')

    return "\n".join(lines)

def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )

def emit_tree_html(model: Dict[str, Any], title: str = "") -> str:
    assets = index_by_id(model.get("assets", []))
    ifaces = index_by_id(model.get("interfaces", []))
    conts = index_by_id(model.get("containers", []))
    root, tree = build_container_tree(conts)

    by_container: Dict[str, List[str]] = defaultdict(list)
    for a in model.get("assets", []):
        by_container[a.get("container", "")].append(a["id"])

    by_asset_ifaces: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for iface in model.get("interfaces", []):
        by_asset_ifaces[iface["asset"]].append(iface)

    def asset_label(a: Dict[str, Any]) -> str:
        nm = html_escape(a.get("name", a["id"]))
        kind = html_escape(a.get("kind", ""))
        dom = html_escape(a.get("domain", ""))
        return f"{nm} <span class=muted>[{kind}/{dom}]</span> <code>{html_escape(a['id'])}</code>"

    def iface_label(i: Dict[str, Any]) -> str:
        nm = html_escape(i.get("name", i["id"]))
        dom = html_escape(i.get("domain", ""))
        med = html_escape(i.get("medium", ""))
        return f"{nm} <span class=muted>[{dom}/{med}]</span> <code>{html_escape(i['id'])}</code>"

    def render_container(cid: str) -> str:
        c = conts[cid]
        cname = html_escape(c.get("name", cid))
        ctype = html_escape(c.get("type", "container"))
        label = f"{cname} <span class=muted>({ctype})</span> <code>{html_escape(cid)}</code>"
        parts: List[str] = []
        parts.append(f"<li class=container><details open><summary>{label}</summary>")
        # Assets
        assets_here = by_container.get(cid, [])
        if assets_here:
            parts.append("<ul class=assets>")
            for aid in sorted(assets_here):
                a = assets[aid]
                dom = a.get("domain", "")
                parts.append(f"<li class=asset domain-{html_escape(dom)}>")
                parts.append(asset_label(a))
                ifaces_here = by_asset_ifaces.get(aid, [])
                if ifaces_here:
                    parts.append("<ul class=interfaces>")
                    for i in sorted(ifaces_here, key=lambda x: x.get("name", x["id"])):
                        parts.append(f"<li class=interface>{iface_label(i)}</li>")
                    parts.append("</ul>")
                parts.append("</li>")
            parts.append("</ul>")
        # Children
        children = tree.get(cid, [])
        if children:
            parts.append("<ul class=containers>")
            for child in sorted(children):
                parts.append(render_container(child))
            parts.append("</ul>")
        parts.append("</details></li>")
        return "".join(parts)

    root_html = render_container(root) if root else ""

    # Minimal, self-contained HTML with search and expand/collapse
    doc_template = """<!doctype html>
<html lang=en>
<head>
  <meta charset=utf-8>
  <meta name=viewport content="width=device-width, initial-scale=1">
  <title>TITLE_HERE – Components</title>
  <style>
    :root {
      --elec: #6b5cff; --mech: #1b7f2a; --data: #0b6a8b; --ctrl: #b26b00; --safe: #b00020;
      --muted: #6b7280; --bg: #ffffff; --fg: #111827; --border: #e5e7eb;
    }
    body { font: 14px/1.45 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; color: var(--fg); }
    header { padding: 12px 16px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--bg); z-index: 10; }
    h1 { font-size: 18px; margin: 0 0 8px; }
    .toolbar { display: flex; gap: 8px; align-items: center; }
    input[type="search"] { flex: 1; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
    button { padding: 6px 10px; border: 1px solid var(--border); background: #f9fafb; border-radius: 6px; cursor: pointer; }
    main { padding: 12px 16px; }
    ul { list-style: none; padding-left: 18px; margin: 6px 0; }
    li.container > details > summary { cursor: pointer; font-weight: 600; }
    .muted { color: var(--muted); font-weight: 400; }
    code { background: #f3f4f6; padding: 1px 4px; border-radius: 4px; font-size: 12px; }
    .asset.domain-electrical > :first-child { border-left: 3px solid var(--elec); padding-left: 6px; }
    .asset.domain-mechanical > :first-child { border-left: 3px solid var(--mech); padding-left: 6px; }
    .asset.domain-data > :first-child { border-left: 3px solid var(--data); padding-left: 6px; }
    .asset.domain-control > :first-child { border-left: 3px solid var(--ctrl); padding-left: 6px; }
    .asset.domain-safety > :first-child { border-left: 3px solid var(--safe); padding-left: 6px; }
  </style>
  <script>
    function expandAll(open) {
      document.querySelectorAll('details').forEach(d => d.open = open);
    }
    function onSearch(ev) {
      const q = ev.target.value.trim();
      // Show all by default
      document.querySelectorAll('li').forEach(li => li.style.display = '');
      if (!q) return;
      // Expand for visibility
      expandAll(true);
      const items = document.querySelectorAll('li');
      const needle = q.toLowerCase();
      items.forEach(li => {
        const txt = li.textContent.toLowerCase();
        if (!txt.includes(needle)) { li.style.display = 'none'; }
      });
      // Ensure containers with visible descendants remain visible
      document.querySelectorAll('li.container').forEach(li => {
        const anyVisible = li.querySelector('li:not([style*="display: none"])');
        if (anyVisible) li.style.display = '';
      });
    }
    function applyDomainFilters() {
      const enabled = new Set(Array.from(document.querySelectorAll('.domf')).filter(cb => cb.checked).map(cb => cb.getAttribute('data-domain')));
      document.querySelectorAll('li.asset').forEach(li => {
        const m = li.className.match(/domain-([a-z]+)/); const dom = m? m[1] : '';
        li.style.display = enabled.has(dom) ? '' : 'none';
      });
      document.querySelectorAll('li.container').forEach(li => {
        const anyVisible = li.querySelector('li:not([style*="display: none"])');
        if (anyVisible) li.style.display = '';
      });
    }
    window.addEventListener('DOMContentLoaded', () => {
      document.getElementById('search').addEventListener('input', onSearch);
      document.getElementById('expand').addEventListener('click', () => expandAll(true));
      document.getElementById('collapse').addEventListener('click', () => expandAll(false));
      document.querySelectorAll('.domf').forEach(cb => cb.addEventListener('change', applyDomainFilters));
      applyDomainFilters();
    });
  </script>
</head>
<body>
  <header>
    <h1>TITLE_HERE – Components</h1>
    <div class=toolbar>
      <input id=search type=search placeholder="Filter by name, kind, domain, id..."/>
      <label><input type=checkbox class=domf data-domain=electrical checked> Electrical</label>
      <label><input type=checkbox class=domf data-domain=mechanical checked> Mechanical</label>
      <label><input type=checkbox class=domf data-domain=data checked> Data</label>
      <label><input type=checkbox class=domf data-domain=control checked> Control</label>
      <label><input type=checkbox class=domf data-domain=safety checked> Safety</label>
      <button id=expand title="Expand all">Expand</button>
      <button id=collapse title="Collapse all">Collapse</button>
    </div>
  </header>
  <main>
    <ul class=tree>
      ROOT_HTML_HERE
    </ul>
  </main>
</body>
</html>
"""
    page_title = html_escape(title or model.get('meta',{}).get('site_name','Components'))
    doc = doc_template.replace("TITLE_HERE", page_title).replace("ROOT_HTML_HERE", root_html)
    return doc

def render_png_from_mermaid(mermaid_path: str, png_path: str, renderer_preference: str | None = None) -> str:
    """Try to render PNG from Mermaid using available tooling.

    Strategy:
      1) If renderer_preference == 'mermaid-cli' or unspecified, and `mmdc` is in PATH, use it.
      2) If renderer_preference == 'kroki' or mmdc not found, try Kroki (network required).
    Returns a short status string describing what was used.
    """
    # Option 1: Mermaid CLI (mmdc)
    if renderer_preference in (None, "mermaid-cli"):
        mmdc = shutil.which("mmdc")
        if mmdc:
            cmd = [mmdc, "-i", mermaid_path, "-o", png_path]
            subprocess.check_call(cmd)
            return "Rendered via mermaid-cli (mmdc)"

    # Option 2: Kroki
    if renderer_preference in (None, "kroki"):
        with open(mermaid_path, "rb") as f:
            code = f.read()
        # Kroki supports POST /mermaid/png with encoded content
        url = "https://kroki.io/mermaid/png"
        req = request.Request(url, data=code, headers={"Content-Type": "text/plain"})
        with request.urlopen(req) as resp:
            img = resp.read()
        with open(png_path, "wb") as out:
            out.write(img)
        return "Rendered via Kroki"

    raise RuntimeError("No renderer available for PNG export")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="IndustroML JSON file")
    ap.add_argument("--out", default="diagram.mmd", help="Output Mermaid file")
    ap.add_argument("--direction", default="LR", choices=["LR","TB","RL","BT"], help="Flow direction")
    ap.add_argument("--title", default="", help="Diagram title (comment)")
    ap.add_argument("--png", default="", help="Optional: also render PNG to this path")
    ap.add_argument("--renderer", default="", choices=["", "mermaid-cli", "kroki"], help="Renderer preference for PNG")
    ap.add_argument("--html", default="", help="Optional: also write a components HTML tree to this path")
    ap.add_argument("--domains", default="", help="Comma-separated list of domains to include (electrical,mechanical,data,control,safety)")
    ap.add_argument("--export-tree-json", default="", help="Optional: write tree JSON to this path")
    ap.add_argument("--export-graph-json", default="", help="Optional: write nodes/edges JSON to this path")
    ap.add_argument("--catalog", default="", help="Optional: path to master catalog to enrich node metadata (e.g., icon)")
    ap.add_argument("--icon-map", default="", help="Optional: icon map YAML (icon key -> file path) to add icon_file in graph export")
    args = ap.parse_args()

    model = load_model(args.input)
    model = normalize_model(model)
    errs = validate(model)
    if errs:
        print("Validation issues:", file=sys.stderr)
        for e in errs: print(" -", e, file=sys.stderr)
        # continue anyway to help you see what renders

    doms = set([d.strip() for d in args.domains.split(',') if d.strip()]) or None
    catalog_map = load_catalog(args.catalog) if args.catalog else {}
    icon_map: Dict[str, str] = {}
    if args.icon_map:
        try:
            import yaml  # type: ignore
            with open(args.icon_map, 'r', encoding='utf-8') as f:
                im = yaml.safe_load(f) or {}
                icon_map = im.get('icons', {}) or {}
        except Exception as e:
            print(f"Failed to load icon map: {e}", file=sys.stderr)
    mermaid = emit_mermaid(model, direction=args.direction, title=args.title, domains_filter=doms)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(mermaid)
    print(f"Wrote {args.out}")

    if args.png:
        try:
            status = render_png_from_mermaid(args.out, args.png, renderer_preference=(args.renderer or None))
            print(f"Wrote {args.png} ({status})")
        except Exception as e:
            print(f"PNG export failed: {e}", file=sys.stderr)
            print("Tip: install Mermaid CLI (mmdc) or enable network for Kroki.", file=sys.stderr)
    if args.html:
        html = emit_tree_html(model, title=args.title)
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Wrote {args.html}")

    if args.export_tree_json:
        conts = index_by_id(model.get("containers", []))
        root, tree = build_container_tree(conts)
        assets = index_by_id(model.get("assets", []))
        ifaces = index_by_id(model.get("interfaces", []))
        by_container: Dict[str, List[str]] = defaultdict(list)
        for a in model.get("assets", []):
            if doms and a.get("domain") not in doms:
                continue
            by_container[a.get("container", "")].append(a["id"])
        by_asset_ifaces: Dict[str, List[str]] = defaultdict(list)
        for i in model.get("interfaces", []):
            by_asset_ifaces[i["asset"]].append(i["id"])
        def build_node(cid: str) -> Dict[str, Any]:
            c = conts[cid]
            return {
                "id": cid,
                "name": c.get("name", cid),
                "type": c.get("type", "container"),
                "assets": [
                    {"id": aid, "name": assets[aid].get("name", aid), "domain": assets[aid].get("domain"), "kind": assets[aid].get("kind"), "interfaces": by_asset_ifaces.get(aid, [])}
                    for aid in by_container.get(cid, [])
                ],
                "children": [build_node(child) for child in tree.get(cid, [])]
            }
        tree_json = build_node(root) if root else {}
        with open(args.export_tree_json, "w", encoding="utf-8") as f:
            json.dump(tree_json, f, indent=2)
        print(f"Wrote {args.export_tree_json}")

    if args.export_graph_json:
        assets = index_by_id(model.get("assets", []))
        ifaces = index_by_id(model.get("interfaces", []))
        nodes = []
        for a in model.get("assets", []):
            if doms and a.get("domain") not in doms:
                continue
            node = {"id": a["id"], "name": a.get("name", a["id"]), "domain": a.get("domain"), "kind": a.get("kind"), "container": a.get("container")}
            # Enrich with icon key from catalog if available
            icon = catalog_map.get((a.get("domain"), a.get("kind")), {}).get("icon") if catalog_map else None
            if icon:
                node["icon"] = icon
                if icon_map and icon in icon_map:
                    node["icon_file"] = icon_map[icon]
            nodes.append(node)
        edges = []
        for c in model.get("connections", []):
            fi, ti = ifaces.get(c.get("from")), ifaces.get(c.get("to"))
            if not fi or not ti:
                continue
            fa, ta = fi.get("asset"), ti.get("asset")
            if doms and (assets.get(fa, {}).get("domain") not in doms or assets.get(ta, {}).get("domain") not in doms):
                continue
            std_type = STD_CONNECTOR_TYPE.get(c.get("type"), c.get("type"))
            edges.append({"id": c.get("id"), "type": std_type, "from": fa, "to": ta, "attributes": c.get("attributes", {})})
        with open(args.export_graph_json, "w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "edges": edges}, f, indent=2)
        print(f"Wrote {args.export_graph_json}")

if __name__ == "__main__":
    main()
