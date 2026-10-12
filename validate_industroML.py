#!/usr/bin/env python3
"""
validate_industroML.py
Validates an IndustroML JSON file against JSON Schema (if jsonschema installed)
and runs referential integrity & domain/consistency checks.

Usage:
  python validate_industroML.py model.json --schema industroml.schema.json

Exit codes:
  0 = valid
  1 = schema error(s)
  2 = referential or logical error(s)
"""
from __future__ import annotations
import argparse, json, os, sys, re
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict

def load_model(path: str) -> dict:
    """Read a model from JSON or YAML.

    The examples are authored in YAML, so refusing to read it made the validator
    useless against the very files it ships with. YAML needs PyYAML; JSON never
    needs anything.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError as e:
            raise SystemExit(
                f"{path} is YAML and PyYAML is not installed: {e}\n"
                "  pip install pyyaml   (or convert the model to JSON)"
            )
        return yaml.safe_load(text)
    return json.loads(text)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def try_schema_validate(instance: dict, schema: dict) -> List[str]:
    try:
        import jsonschema
    except Exception as e:
        return [f"jsonschema not available: {e}. Skipping JSON Schema validation step."]
    try:
        jsonschema.validate(instance=instance, schema=schema)
        return []
    except Exception as e:
        # try to extract human-friendly errors
        errs = []
        if hasattr(e, "context") and e.context:
            for sub in e.context:
                errs.append(f"{sub.message} at path: {'/'.join(map(str, sub.path))}")
        errs.append(str(e))
        return errs

ID_RE = re.compile(r'^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$')

# Assets that can hold other assets. A breaker's container is its switchboard.
ENCLOSURE_KINDS = {
    "switchboard", "mcc", "distribution_board", "panelboard",
    "busbar_section", "hmi_panel", "fire_alarm_panel",
}

# Which interface domains each connection type may join. A connection is a
# physical thing crossing a domain boundary far more often than it stays inside
# one: a pipe ends at an inline flow transmitter, a data link ends at a PLC.
ALLOWED_DOMAINS = {
    "cable":     {"electrical", "control", "data", "safety"},
    "pipe":      {"mechanical", "control", "safety"},
    "data_link": {"data", "control", "safety"},
    "io_link":   {"control", "electrical", "mechanical", "safety"},
}

CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "catalog", "master_catalog.yaml")


def load_kind_domains(path: str = CATALOG) -> Optional[Dict[str, Set[str]]]:
    """Asset kind -> the domains the master catalogue allows it in.

    None when the catalogue cannot be read (no PyYAML, or no file), in which
    case the kind/domain check is skipped rather than guessed.
    """
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            cat = yaml.safe_load(f)
    except Exception:
        return None
    out: Dict[str, Set[str]] = defaultdict(set)
    for el in cat.get("elements") or []:
        if el.get("kind") and el.get("domain"):
            out[el["kind"]].add(el["domain"])
    return dict(out)


def ref_validate(model: dict,
                 kind_domains: Optional[Dict[str, Set[str]]] = None) -> List[str]:
    errs: List[str] = []

    # ID uniqueness. Checked on the lists as written: the dicts below keep the
    # last of any repeated id, so a check on their keys can never find one.
    for key, kind in (("containers", "container"), ("assets", "asset"),
                      ("interfaces", "interface"), ("connections", "connection")):
        seen: Set[str] = set()
        for x in model.get(key, []) or []:
            xid = x.get("id")
            if xid in seen:
                errs.append(f"Duplicate {kind} id: {xid}")
            seen.add(xid)

    conts = {c["id"]: c for c in model.get("containers", [])}
    assets = {a["id"]: a for a in model.get("assets", [])}
    ifaces = {i["id"]: i for i in model.get("interfaces", [])}
    conns  = {c["id"]: c for c in model.get("connections", [])}

    # A container and an asset may share an id only if they are the same
    # thing; a route or a containment reference cannot tell them apart.
    for xid in sorted(set(conts) & set(assets)):
        errs.append(f"Id {xid} is both a container and an asset")

    # ID format
    for group, kind in [(conts, "container"), (assets, "asset"), (ifaces, "interface"), (conns, "connection")]:
        for _id in group.keys():
            if not ID_RE.match(_id):
                errs.append(f"{kind} id '{_id}' fails ID pattern")

    # Container parent refs
    for cid, c in conts.items():
        p = c.get("parent")
        if p and p not in conts:
            errs.append(f"Container {cid} references missing parent {p}")

    # Asset -> container.
    #
    # An asset's container is usually a container, but some assets *are*
    # enclosures: a breaker lives inside an MCC, not beside it. Allowing an
    # enclosure asset here is what lets a switchboard be modelled once, as the
    # thing it is, rather than twice as an asset and a shadow cabinet.
    for aid, a in assets.items():
        c = a.get("container")
        if c in conts:
            continue
        host = assets.get(c)
        if host is None:
            errs.append(f"Asset {aid} container {c} not found")
        elif host.get("kind") not in ENCLOSURE_KINDS:
            errs.append(
                f"Asset {aid} is contained by asset {c} of kind "
                f"'{host.get('kind')}', which is not an enclosure. "
                f"Enclosures are: {', '.join(sorted(ENCLOSURE_KINDS))}"
            )
        elif c == aid:
            errs.append(f"Asset {aid} contains itself")

    # Asset kind -> domain, as the master catalogue defines it. A pump in the
    # electrical domain is a typo that every later check trusts.
    if kind_domains:
        for aid, a in assets.items():
            allowed = kind_domains.get(a.get("kind"))
            if allowed and a.get("domain") not in allowed:
                errs.append(
                    f"Asset {aid} is kind '{a.get('kind')}' in domain "
                    f"'{a.get('domain')}'; the catalogue has that kind in "
                    f"{', '.join(sorted(allowed))}"
                )

    # Interface -> asset
    for iid, i in ifaces.items():
        a = i.get("asset")
        if a not in assets:
            errs.append(f"Interface {iid} references missing asset {a}")

    # Connections endpoints
    for cid, c in conns.items():
        fr, to = c.get("from"), c.get("to")
        if fr not in ifaces:
            errs.append(f"Connection {cid} 'from' interface {fr} not found")
        if to not in ifaces:
            errs.append(f"Connection {cid} 'to' interface {to} not found")

    # Route waypoints are trays, conduits, racks: containers or assets.
    for cid, c in conns.items():
        for r in c.get("route") or []:
            if r not in conts and r not in assets:
                errs.append(f"Connection {cid} route via {r} not found")

    for cid, c in conns.items():
        ctype = c.get("type")
        fr, to = c.get("from"), c.get("to")
        fi, ti = ifaces.get(fr), ifaces.get(to)
        if not fi or not ti: 
            continue
        # Bridges are the normal case, not the exception, so they are part of
        # the rule rather than an afterthought appended below it. A data link
        # runs from a PLC (control) to a switch (data); an I/O link runs from a
        # controller to a transmitter that is also a process device; and a pipe
        # runs through an inline instrument whose process port is mechanical.
        # The previous version appended the error first and then "allowed" the
        # bridge with a `pass`, so every bridge was reported.
        allowed = ALLOWED_DOMAINS.get(ctype)
        if allowed is None:
            # Without this the referential pass silently accepts any string as a
            # connection type, and the model only fails later against the schema
            # — or not at all, if nobody has jsonschema installed.
            errs.append(
                f"Connection {cid} has unknown type '{ctype}'; "
                f"expected one of {', '.join(sorted(ALLOWED_DOMAINS))}"
            )
        else:
            fd, td = fi.get("domain"), ti.get("domain")
            if fd not in allowed or td not in allowed:
                errs.append(
                    f"Connection {cid} type {ctype} connects {fd} -> {td}; "
                    f"permitted domains are {', '.join(sorted(allowed))}"
                )

    # Mechanical continuity hint: DN or material mismatches on directly-connected flanged pipes
    for cid, c in conns.items():
        if c.get("type") == "pipe":
            fr, to = c["from"], c["to"]
            fi, ti = ifaces.get(fr), ifaces.get(to)
            if not fi or not ti: 
                continue
            fdn = (fi.get("attributes") or {}).get("dn_mm")
            tdn = (ti.get("attributes") or {}).get("dn_mm")
            if fdn and tdn and fdn != tdn:
                errs.append(f"Pipe {cid} DN mismatch: {fdn} != {tdn} between {fr} and {to}")

    return errs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", help="IndustroML JSON file")
    ap.add_argument("--schema", default="industroml.schema.json", help="Schema file path")
    args = ap.parse_args()

    try:
        model = load_model(args.model)
    except Exception as e:
        print(f"Failed to read model: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        schema = load_json(args.schema)
    except Exception as e:
        print(f"Failed to read schema: {e}", file=sys.stderr)
        schema = None

    # JSON Schema validation (optional if jsonschema missing or schema failed to load)
    if schema is not None:
        schema_errs = try_schema_validate(model, schema)
        # Filter out the "not available" info message; report but don't fail with code 1 for that.
        real_schema_errs = [e for e in schema_errs if not e.startswith("jsonschema not available")]
        info_msgs = [e for e in schema_errs if e.startswith("jsonschema not available")]
        for msg in info_msgs:
            print(f"INFO: {msg}", file=sys.stderr)
        if real_schema_errs:
            print("Schema validation errors:", file=sys.stderr)
            for e in real_schema_errs:
                print(" -", e, file=sys.stderr)
            # keep going to also report referential issues
            schema_failed = True
        else:
            schema_failed = False
    else:
        schema_failed = False

    # Referential & logical checks
    kind_domains = load_kind_domains()
    if kind_domains is None:
        print("INFO: master catalogue unreadable (PyYAML missing?); "
              "skipping the asset kind/domain check.", file=sys.stderr)
    ref_errs = ref_validate(model, kind_domains)
    if ref_errs:
        print("Referential/logic errors:", file=sys.stderr)
        for e in ref_errs:
            print(" -", e, file=sys.stderr)

    if (schema_failed) and ref_errs:
        sys.exit(1)  # both failed; use 1
    if schema_failed and not ref_errs:
        sys.exit(1)
    if ref_errs:
        sys.exit(2)

    print("Valid IndustroML ✅")
    sys.exit(0)

if __name__ == "__main__":
    main()