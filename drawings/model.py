"""Read an IndustroML model into something drawings can walk.

Plain indexes over the four lists, plus the text a drawing puts beside a
symbol: an asset's tag, name and rating, and a cable's specification. Nothing
here knows about sheets or DXF.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def load(path: str) -> dict:
    from validate_industroML import load_model
    return load_model(path)


def digest(model: dict) -> str:
    return hashlib.sha256(json.dumps(model, sort_keys=True,
                                     default=str).encode()).hexdigest()


def _num(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _si(v, unit):
    """1000 V -> '1 kV' only where it reads better: 11000 V -> '11 kV'."""
    v = _num(v)
    if isinstance(v, (int, float)) and unit in ("V", "VA") and v >= 1000:
        k = _num(v / 1000)
        return f"{k:g} k{unit}" if isinstance(k, float) else f"{k} k{unit}"
    return f"{v:g} {unit}" if isinstance(v, float) else f"{v} {unit}"


class Model:
    def __init__(self, data: dict):
        self.data = data
        self.meta = data.get("meta") or {}
        self.containers = {c["id"]: c for c in data.get("containers") or []}
        self.assets = {a["id"]: a for a in data.get("assets") or []}
        self.interfaces = {i["id"]: i for i in data.get("interfaces") or []}
        self.connections: List[dict] = list(data.get("connections") or [])
        self.order = {a["id"]: k for k, a in
                      enumerate(data.get("assets") or [])}

    def asset_of(self, iface: str) -> Optional[str]:
        i = self.interfaces.get(iface)
        if i:
            return i.get("asset")
        # tolerate a model that names an asset port without declaring it
        head = iface.split(".")[0]
        return head if head in self.assets else None

    def attrs(self, obj_id: str) -> dict:
        o = self.assets.get(obj_id) or self.interfaces.get(obj_id) or {}
        return o.get("attributes") or {}

    def kind(self, asset_id: str) -> str:
        return (self.assets.get(asset_id) or {}).get("kind", "")

    def name(self, asset_id: str) -> str:
        return (self.assets.get(asset_id) or {}).get("name", asset_id)

    def tag(self, asset_id: str) -> str:
        a = self.assets.get(asset_id) or {}
        return str((a.get("attributes") or {}).get("tag") or asset_id)


def rating(attrs: dict) -> str:
    """The rating a drawing writes under a symbol, most telling first."""
    a = attrs
    parts = []
    if "power_kva" in a:
        parts.append(f"{_num(a['power_kva'])} kVA")
    if "power_kw" in a:
        parts.append(f"{_num(a['power_kw'])} kW")
    if "capacity_kw" in a:
        parts.append(f"{_num(a['capacity_kw'])} kW")
    if "current_a" in a or "rating_a" in a:
        parts.append(f"{_num(a.get('rating_a', a.get('current_a')))} A")
    if "breaking_capacity_ka" in a or "fault_ka" in a:
        parts.append(f"{_num(a.get('breaking_capacity_ka', a.get('fault_ka')))} kA")
    if "flow_m3h" in a:
        parts.append(f"{_num(a['flow_m3h'])} m³/h")
    if "flow_ls" in a:
        parts.append(f"{_num(a['flow_ls'])} L/s")
    if "head_m" in a:
        parts.append(f"{_num(a['head_m'])} m")
    if "volume_m3" in a:
        parts.append(f"{_num(a['volume_m3'])} m³")
    return ", ".join(parts)


def volts(attrs: dict) -> str:
    a = attrs
    if "primary_voltage_v" in a and "secondary_voltage_v" in a:
        return (f"{_si(a['primary_voltage_v'], 'V')} / "
                f"{_si(a['secondary_voltage_v'], 'V')}")
    if "voltage_v" in a:
        return _si(a["voltage_v"], "V")
    return ""


def cable_spec(conn: dict) -> List[str]:
    """Lines of text for a cable: id, construction, length."""
    a = conn.get("attributes") or {}
    lines = [conn["id"]]
    csa = a.get("csa_mm2")
    if csa is not None:
        cores = a.get("cores")
        core = f"{_num(cores)}C " if cores else ""
        mat = a.get("conductor") or a.get("material") or ""
        ins = a.get("insulation") or ""
        body = f"{core}{_num(csa)}mm² {mat} {ins}".replace("  ", " ").strip()
        runs = a.get("runs") or a.get("parallel_runs")
        if runs and runs > 1:
            body = f"{_num(runs)} x ({body})"
        if a.get("earth_mm2"):
            body += f" + E {_num(a['earth_mm2'])}mm²"
        lines.append(body)
    elif a.get("description"):
        lines.append(str(a["description"]))
    tail = []
    if a.get("length_m") is not None:
        tail.append(f"L = {_num(a['length_m'])} m")
    if a.get("method"):
        tail.append(str(a["method"]))
    if tail:
        lines.append(", ".join(tail))
    return lines


def pipe_line_number(conn: dict) -> str:
    """ISO-style line number: DN-SERVICE-NUMBER-SPEC, from what is known."""
    a = conn.get("attributes") or {}
    if a.get("line_number"):
        return str(a["line_number"])
    parts = []
    dn = a.get("dn_mm") or a.get("dn")
    if dn:
        parts.append(f"DN{_num(dn)}")
    if a.get("service"):
        parts.append(str(a["service"]).upper())
    parts.append(conn["id"])
    return "-".join(parts)
