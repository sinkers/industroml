"""Model in, drawing set out: DXF for CAD, PDF to issue, PNG to review.

  python3 -m drawings MODEL.yaml --out DIR [--sld] [--pid] [--no-plot]

The title block is filled from the model's ``meta.drawing`` (client,
project, numbers, people, status) and ``meta.revisions``; anything missing
is left blank rather than invented. Each drawing carries a note giving the
model file and its hash, so a sheet can be traced back to the model that
made it.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from typing import Dict, List, Optional

from . import pid, sld
from .canvas import Canvas
from .model import Model, digest
from .sheet import compose
from .symbols import library

VERSION = "0.1.0"

KINDS = {
    "sld": {"title": "ELECTRICAL SINGLE LINE DIAGRAM", "suffix": "E-SLD",
            "module": sld,
            "notes": [
                "Symbols to IEC 60617 (AS/NZS 1102). Single line "
                "representation: one line is a three phase circuit.",
                "Protective devices at boards are drawn from each port's "
                "device and rating attributes in the model.",
                "Cable text: connection id, construction and route length.",
            ]},
    "pid": {"title": "PIPING AND INSTRUMENTATION DIAGRAM", "suffix": "M-PID",
            "module": pid,
            "notes": [
                "Symbols to ISO 10628-2; instrument bubbles to ISA-5.1.",
                "Line numbers: DN-service-line, or the line_number the model gives.",
                "Valves and strainers on a line are drawn in the order "
                "the model connects them.",
            ]},
}


def _info(m: Model, kind: str, sheet_no: str, model_path: str) -> Dict:
    d = dict(m.meta.get("drawing") or {})
    num = (d.get("numbers") or {}).get(kind) or d.get("number")
    if num and kind not in (d.get("numbers") or {}):
        num = f"{num}-{KINDS[kind]['suffix']}"
    revs = m.meta.get("revisions") or []
    rev = revs[-1].get("rev") if revs else d.get("revision", "")
    return {
        "client": d.get("client", ""),
        "project": d.get("project", ""),
        "site": m.meta.get("site_name", ""),
        "title": d.get("title") or m.meta.get("site_name", ""),
        "subtitle": KINDS[kind]["title"],
        "number": num or "",
        "revision": rev,
        "revisions": revs,
        "sheet": sheet_no,
        "date": d.get("date") or (revs[-1].get("date") if revs else ""),
        "drawn": d.get("drawn", "IndustroML"),
        "checked": d.get("checked", ""),
        "approved": d.get("approved", ""),
        "status": d.get("status", "Preliminary - not for construction"),
    }


def draw(model_path: str, out_dir: str, kinds=("sld", "pid"),
         plot: bool = True, mono: bool = False, flat: bool = False) -> Dict:
    """Write each drawing in kinds for the model. Returns a report."""
    from .dxf import plot as plot_dxf
    from .dxf import write

    data = Model_load(model_path)
    m = Model(data)
    blocks = library()
    sha = digest(data)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(model_path))[0]
    report = {"model": os.path.basename(model_path), "sha256": sha,
              "generator": f"industroml drawings {VERSION}", "drawings": []}
    for i, kind in enumerate(kinds, 1):
        spec = KINDS[kind]
        diagram, plan = spec["module"].layout(m, blocks)
        entry = {"kind": kind, "warnings": plan.warnings,
                 "nodes": len(plan.nodes)}
        if not diagram.prims:
            entry["skipped"] = "nothing to draw"
            report["drawings"].append(entry)
            continue
        notes = spec["notes"] + [
            f"Generated from {os.path.basename(model_path)} "
            f"(sha256 {sha[:12]}) by industroml drawings {VERSION}. Edit "
            "the model and regenerate rather than editing this drawing.",
        ]
        info = _info(m, kind, f"{i} OF {len(kinds)}", model_path)
        sheet, meta = compose(diagram, blocks, info,
                              spec["module"].legend_items(diagram, blocks),
                              notes)
        base = os.path.join(out_dir, f"{stem}_{kind}")
        write(sheet, blocks, base + ".dxf", paper=meta["paper_mm"], props={
            "industroml_model": os.path.basename(model_path),
            "industroml_sha256": sha, "industroml_drawing": kind},
            flat=flat)
        entry.update(meta, dxf=os.path.basename(base) + ".dxf")
        if plot:
            plot_dxf(base + ".dxf", meta["paper_mm"], pdf=base + ".pdf",
                     png=base + ".png", mono=mono)
            entry.update(pdf=os.path.basename(base) + ".pdf",
                         png=os.path.basename(base) + ".png")
        report["drawings"].append(entry)
    with open(os.path.join(out_dir, f"{stem}_drawings.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    return report


def Model_load(path):
    from .model import load
    return load(path)
