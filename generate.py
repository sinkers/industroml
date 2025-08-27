#!/usr/bin/env python3
"""
generate_diagram.py

Render an IndustroML (v0.1) JSON file into a Mermaid flowchart (.mmd).
Stdlib only. Produces subgraphs by containers and styles by domain.

Usage:
  python generate_diagram.py ravenbrook_site.json --out site.mmd

Optional flags:
  --title "My Plant Diagram"
  --direction LR   (or TB)
"""
from __future__ import annotations
import argparse, json, sys, re
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
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def index_by_id(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {it["id"]: it for it in items}

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

    # asset -> container
    for a in model.get("assets", []):
        cid = a.get("container")
        if cid and cid not in conts:
            errs.append(f"Asset {a['id']} container {cid} missing")

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
    tail = "\\n".join(summary[:3])
    return f"{nm}\\n[{kind}/{dom}]{('\\n'+tail) if tail else ''}"

def mermaid_escape(text: str) -> str:
    return text.replace('"','\\"')

def emit_mermaid(model: Dict[str, Any], direction: str = "LR", title: str = "") -> str:
    assets = index_by_id(model.get("assets", []))
    ifaces = index_by_id(model.get("interfaces", []))
    conts = index_by_id(model.get("containers", []))
    root, tree = build_container_tree(conts)

    # group assets by container
    by_container: Dict[str, List[str]] = defaultdict(list)
    for a in model.get("assets", []):
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
    for i, conn in enumerate(model.get("connections", []), start=1):
        ctype = conn.get("type","")
        fr, to = conn["from"], conn["to"]
        fi, ti = ifaces.get(fr), ifaces.get(to)
        if not fi or not ti:
            # skip invalid; validator will have warned
            continue
        fa, ta = assets.get(fi["asset"]), assets.get(ti["asset"])
        if not fa or not ta:
            continue
        f_id, t_id = sanitize_id(fa["id"]), sanitize_id(ta["id"])
        # Build an informative label
        f_name = fi.get("name", fr.split(".")[-1])
        t_name = ti.get("name", to.split(".")[-1])
        fields = CONN_LABEL_FIELDS.get(ctype, [])
        attr_txt = short_attrs(conn.get("attributes", {}), fields)
        label = f"{ctype}:{f_name}→{t_name}" + (f" ({attr_txt})" if attr_txt else "")
        lines.append(f'{f_id} -- "{mermaid_escape(label)}" --> {t_id}')

    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="IndustroML JSON file")
    ap.add_argument("--out", default="diagram.mmd", help="Output Mermaid file")
    ap.add_argument("--direction", default="LR", choices=["LR","TB","RL","BT"], help="Flow direction")
    ap.add_argument("--title", default="", help="Diagram title (comment)")
    args = ap.parse_args()

    model = load_model(args.input)
    errs = validate(model)
    if errs:
        print("Validation issues:", file=sys.stderr)
        for e in errs: print(" -", e, file=sys.stderr)
        # continue anyway to help you see what renders

    mermaid = emit_mermaid(model, direction=args.direction, title=args.title)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(mermaid)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
